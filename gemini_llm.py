"""Use Google's free Gemini API tier directly, paced to its per-minute limit.

The key is sent in a header, never in a URL, so it cannot appear in error text
(LiteLLM's Gemini transport puts it in the query string of failed requests).

Google Search grounding has no free-tier allowance on this account (every model
answers 429), so research is built from two keyless sources instead:
dated headlines from Google News RSS, and pages the question names (its
resolution source) read through Gemini's url_context tool. The researcher fails
rather than forecasting from the model's memory when neither yields evidence.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx
from forecasting_tools import GeneralLlm

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
URL_PATTERN = re.compile(r"https?://[^\s)\]>\"'`,]+")


class GeminiQuotaError(RuntimeError):
    """The daily free-tier quota is spent; retrying today cannot help."""


class _Pacer:
    """One request at a time across every Gemini model in this process."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.last = 0.0
        self.requests = 0

    async def wait(self) -> None:
        cap = int(os.getenv("GEMINI_MAX_REQUESTS_PER_RUN", "250"))
        if self.requests >= cap:
            raise GeminiQuotaError(
                f"Gemini request cap for this run reached ({cap}); quota left for later runs.")
        interval = float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "4.6"))  # ~13/min of 15
        delay = self.last + interval - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self.last = time.monotonic()
        self.requests += 1


PACER = _Pacer()


def _redact(text: str) -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    text = re.sub(r"key=[A-Za-z0-9._-]+", "key=REDACTED", text)
    return text.replace(key, "REDACTED") if key else text


def _retry_seconds(error: dict) -> float | None:
    for detail in error.get("details", []):
        delay = detail.get("retryDelay")
        if delay and delay.endswith("s"):
            return float(delay[:-1])
    return None


def _is_daily_quota(error: dict) -> bool:
    for detail in error.get("details", []):
        for violation in detail.get("violations", []):
            if "PerDay" in violation.get("quotaId", ""):
                return True
    return False


class GeminiLlm(GeneralLlm):
    """Keep forecasting-tools' parsing and validation, replace its transport."""

    def __init__(self, model: str, *, search: bool = False):
        if not os.getenv("GEMINI_API_KEY", "").strip():
            raise ValueError("A gemini/ model was selected but GEMINI_API_KEY is not set.")
        super().__init__(model=model, allowed_tries=1)
        self._gemini_model = model.removeprefix("gemini/")
        self._search = search
        self.request_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.sources: list[str] = []

    async def invoke(self, prompt, system_prompt: str | None = None) -> str:
        if not isinstance(prompt, str):
            prompt = "\n\n".join(m.get("content", "") for m in self.model_input_to_message(prompt))
        if self._search:
            return await self._research(prompt)
        return await self._generate(prompt, system_prompt=system_prompt)

    async def _generate(self, prompt: str, *, system_prompt: str | None = None,
                        urls: list[str] | None = None) -> str:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if urls:
            body["tools"] = [{"url_context": {}}]
        data = await self._post(body)
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data.get('promptFeedback')}")
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        answer = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if not answer:
            raise RuntimeError(f"Gemini returned no text (finishReason={candidate.get('finishReason')}).")
        if urls:
            for item in (candidate.get("urlContextMetadata") or {}).get("urlMetadata", []):
                if item.get("urlRetrievalStatus") == "URL_RETRIEVAL_STATUS_SUCCESS":
                    self.sources.append(item.get("retrievedUrl", ""))
        usage = data.get("usageMetadata", {})
        self.input_tokens += usage.get("promptTokenCount", 0)
        self.output_tokens += usage.get("candidatesTokenCount", 0)
        return answer

    async def _post(self, body: dict) -> dict:
        url = f"{API_ROOT}/{self._gemini_model}:generateContent"
        headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"].strip()}
        for attempt in range(1, 6):
            await PACER.wait()
            self.request_count += 1
            try:
                async with httpx.AsyncClient(timeout=240) as client:
                    response = await client.post(url, headers=headers, json=body)
            except httpx.HTTPError as error:
                if attempt == 5:
                    raise RuntimeError(f"Gemini request failed: {_redact(type(error).__name__)}") from None
                await asyncio.sleep(10 * attempt)
                continue
            if response.status_code == 200:
                return response.json()
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {"message": response.text[:300]}
            message = _redact(str(error.get("message", ""))[:300])
            if response.status_code == 429:
                if _is_daily_quota(error):
                    raise GeminiQuotaError(f"Gemini daily quota exhausted: {message}")
                wait = _retry_seconds(error) or 20 * attempt
                print(f"Gemini 429 (rate limit); waiting {wait:.0f}s before retry {attempt}.")
                await asyncio.sleep(min(wait + 1, 90))
                continue
            if response.status_code >= 500 and attempt < 5:
                await asyncio.sleep(10 * attempt)
                continue
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {message}")
        raise GeminiQuotaError("Gemini kept answering 429 (quota) after 5 attempts.")

    ##################################### RESEARCH #####################################

    async def _research(self, prompt: str) -> str:
        self.sources = []
        named_urls = list(dict.fromkeys(u.rstrip(".;:") for u in URL_PATTERN.findall(prompt)))
        plan = await self._plan_queries(prompt)
        queries = plan["queries"] or [prompt.split("Question:")[-1].strip().splitlines()[0][:120]]
        urls = list(dict.fromkeys(named_urls + plan["urls"]))[:5]
        headlines = []
        seen = set()
        for query in queries[:3]:
            for item in await google_news(query):
                if item["link"] not in seen:
                    seen.add(item["link"])
                    headlines.append(item)
        headlines.sort(key=lambda h: h["date"], reverse=True)
        headlines = headlines[:25]
        if not headlines and not urls:
            raise RuntimeError("Research found no current sources; refusing a memory-only forecast.")
        news_block = "\n".join(
            f"- [{h['date'][:10]}] {h['title']} ({h['source']}) {h['link']}" for h in headlines
        ) or "(no news headlines found)"
        pages = "\n".join(urls) or "(none)"
        answer = await self._generate(
            f"{prompt}\n\n"
            "Use only the evidence below. Read these pages with the URL tool when they are "
            f"relevant to the resolution:\n{pages}\n\n"
            f"Recent news headlines found by search (date, title, outlet, link):\n{news_block}\n\n"
            "Cite each fact with its outlet/page and date. Headlines give only the headline, "
            "so do not invent details beyond them. Label anything else as unverified "
            "background from memory.",
            urls=urls,
        )
        if not headlines and not self.sources:
            raise RuntimeError("No news found and no named page could be read; refusing.")
        listing = [f"- {u} (page read)" for u in self.sources]
        listing += [f"- [{h['date'][:10]}] {h['source']}: {h['title']} {h['link']}" for h in headlines[:12]]
        return f"{answer}\n\nSources retrieved for this research:\n" + "\n".join(listing)

    async def _plan_queries(self, prompt: str) -> dict:
        reply = await self._generate(
            "You prepare web research for a forecasting question. Return only JSON: "
            '{"queries": [up to 3 short news search queries], '
            '"urls": [up to 2 official pages that publish the resolution data, only if you are sure of the exact URL]}.'
            f"\n\n{prompt}")
        match = re.search(r"\{.*\}", reply, re.S)
        try:
            plan = json.loads(match.group(0)) if match else {}
        except ValueError:
            plan = {}
        queries = [q for q in plan.get("queries", []) if isinstance(q, str) and q.strip()]
        urls = [u for u in plan.get("urls", []) if isinstance(u, str) and URL_PATTERN.fullmatch(u)]
        return {"queries": queries[:3], "urls": urls[:2]}

    def usage_summary(self) -> dict:
        return {"model": self.model, "web_research": self._search,
                "requests": self.request_count, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cost_usd": 0.0}

    def to_dict(self) -> dict:
        return {"model": self.model, "provider": "gemini-direct", "research": self._search}


async def google_news(query: str, limit: int = 10) -> list[dict]:
    """Dated headlines for a query; no key needed. Failures yield no headlines."""
    url = ("https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
           + urllib.parse.quote(query))
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 forecasting-bot"})
        root = ET.fromstring(response.text)
    except (httpx.HTTPError, ET.ParseError):
        return []
    items = []
    for item in root.findall(".//item")[:limit]:
        try:
            date = parsedate_to_datetime(item.findtext("pubDate", "")).date().isoformat()
        except (TypeError, ValueError):
            date = "undated"
        items.append({"date": date, "title": item.findtext("title", "").strip(),
                      "source": item.findtext("source", "").strip(),
                      "link": item.findtext("link", "").strip()})
    return items
