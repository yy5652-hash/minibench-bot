"""Combine independent web researchers, a gap-filling search and prediction-market prices."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

import httpx
from forecasting_tools import GeneralLlm

from prompts import gap_fill_prompt, research_prompt

_STOP = set("""a an and are as at be been before between by did do does during for from has have how in is it its
least many more most much of on or over than that the their there this to under was were what when which who
will with would according report reported reports""".split())


class ResearchTeam(GeneralLlm):
    """Several researchers answering one brief; each failure leaves the others standing."""

    def __init__(self, members: list[GeneralLlm]):
        super().__init__(model="+".join(m.model for m in members), allowed_tries=1)
        self.members = members

    async def invoke(self, prompt, system_prompt: str | None = None) -> str:
        replies = await asyncio.gather(*(m.invoke(prompt, system_prompt) for m in self.members),
                                       return_exceptions=True)
        reports = []
        for member, reply in zip(self.members, replies):
            if isinstance(reply, BaseException):
                print(f"Researcher {member.model} failed: {type(reply).__name__}")
            else:
                reports.append(f"### Research report from {member.model}\n{reply}")
        if not reports:
            raise RuntimeError("Every researcher failed; refusing a memory-only forecast.")
        return "\n\n".join(reports)

    def to_dict(self) -> dict:
        return {"model": self.model, "provider": "research-team"}

    def usage_summary(self) -> dict:
        return {"model": self.model, "members": [m.usage_summary() for m in self.members
                                                 if hasattr(m, "usage_summary")]}


async def gather_research(question, researcher: GeneralLlm) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    research = await researcher.invoke(research_prompt(question, today))
    gap_researcher = researcher.members[0] if isinstance(researcher, ResearchTeam) else researcher
    try:
        gaps = await gap_researcher.invoke(gap_fill_prompt(question, research, today))
        research += f"\n\n### Follow-up search on gaps and conflicts\n{gaps}"
    except Exception as error:  # The first pass still stands.
        print(f"Gap-filling search failed: {type(error).__name__}")
    markets = await market_snapshot(question.question_text)
    if markets:
        research += ("\n\n### Prediction market search (closest titles, matched by keyword; "
                     f"check each really measures this question)\n{markets}")
    return research


def _search_terms(text: str, limit: int = 7) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-']+", text)
    kept = [w for w in words if w.lower() not in _STOP]
    return " ".join(kept[:limit])


async def market_snapshot(question_text: str) -> str:
    """Open markets from public, keyless endpoints. A failure here only drops the section."""
    terms = _search_terms(question_text)
    if not terms:
        return ""
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "forecasting-bot"}) as client:
        found = await asyncio.gather(_polymarket(client, terms), _manifold(client, terms),
                                     return_exceptions=True)
    return "\n".join(line for lines in found if not isinstance(lines, BaseException) for line in lines)


async def _polymarket(client: httpx.AsyncClient, terms: str) -> list[str]:
    response = await client.get("https://gamma-api.polymarket.com/public-search",
                                params={"q": terms, "limit_per_type": 4, "events_status": "active"})
    response.raise_for_status()
    lines = []
    for event in response.json().get("events") or []:
        for market in (event.get("markets") or [])[:4]:
            if market.get("closed") or not market.get("active", True):
                continue
            try:
                outcomes = json.loads(market.get("outcomes") or "[]")
                prices = [float(p) for p in json.loads(market.get("outcomePrices") or "[]")]
            except (TypeError, ValueError):
                continue
            if outcomes and len(outcomes) == len(prices):
                shown = ", ".join(f"{o} {p:.0%}" for o, p in zip(outcomes, prices))
                volume = float(market.get("volumeNum") or market.get("volume") or 0)
                lines.append(f"- Polymarket: {market.get('question')} | {shown} | volume ${volume:,.0f} "
                             f"| ends {str(market.get('endDate'))[:10]}")
    return lines[:8]


async def _manifold(client: httpx.AsyncClient, terms: str) -> list[str]:
    response = await client.get("https://api.manifold.markets/v0/search-markets",
                                params={"term": terms, "limit": 5, "filter": "open"})
    response.raise_for_status()
    lines = []
    for market in response.json():
        if market.get("probability") is not None:
            lines.append(f"- Manifold (play money): {market.get('question')} | Yes {market['probability']:.0%} "
                         f"| {market.get('uniqueBettorCount', 0)} traders")
    return lines
