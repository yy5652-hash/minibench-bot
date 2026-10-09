"""OpenAI-compatible client for an open model served by vLLM on AMD GPUs.

One request asks for ``n`` samples of the same prompt, so vLLM prefills the
prompt once and decodes the samples together. Responses are stored in a
SQLite cache keyed by the full request, which lets backtests be re-scored and
the demo be replayed without spending GPU time again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Protocol

DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """The endpoint cannot be reached, or the client is in offline (replay) mode."""


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:8000/v1"
    model: str = DEFAULT_MODEL
    api_key: str = "EMPTY"
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 1024
    timeout: float = 180.0
    json_schema: bool = True
    enable_thinking: bool | None = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        def _bool(name: str) -> bool | None:
            v = os.getenv(name)
            return None if v in (None, "") else v.strip().lower() in ("1", "true", "yes", "on")

        cfg = cls(
            base_url=os.getenv("SHELFCAST_LLM_BASE_URL", cls.base_url),
            model=os.getenv("SHELFCAST_LLM_MODEL", cls.model),
            api_key=os.getenv("SHELFCAST_LLM_API_KEY", cls.api_key),
            temperature=float(os.getenv("SHELFCAST_LLM_TEMPERATURE", cls.temperature)),
            max_tokens=int(os.getenv("SHELFCAST_LLM_MAX_TOKENS", cls.max_tokens)),
            enable_thinking=_bool("SHELFCAST_LLM_ENABLE_THINKING"),
        )
        js = _bool("SHELFCAST_LLM_JSON_SCHEMA")
        if js is not None:
            cfg.json_schema = js
        return cfg


@dataclass
class Completion:
    texts: list[str]
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class LLMClient(Protocol):
    model: str

    async def complete(self, messages: list[dict], n: int = 1, schema: dict | None = None) -> Completion: ...


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Drop ``<think>`` blocks that reasoning models may leave in the content."""
    text = _THINK.sub("", text or "")
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


class ResponseCache:
    """Request-keyed store of completions (SQLite, safe across processes)."""

    def __init__(self, path: str | os.PathLike):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS completions (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    @staticmethod
    def key(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, key: str) -> Completion | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT value FROM completions WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        c = Completion(**json.loads(row[0]))
        c.cached = True
        return c

    def put(self, key: str, completion: Completion) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO completions (key, value) VALUES (?, ?)",
                       (key, json.dumps(completion.to_dict())))

    def __len__(self) -> int:
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT COUNT(*) FROM completions").fetchone()[0]


@dataclass
class OpenAICompatibleLLM:
    config: LLMConfig = field(default_factory=LLMConfig.from_env)
    cache: ResponseCache | None = None
    offline: bool = False

    def __post_init__(self) -> None:
        self.model = self.config.model
        self._client = None
        self._client_loop = None
        self._schema_supported = self.config.json_schema

    def _get_client(self):
        # The HTTP pool belongs to one event loop; make a new client if the loop changed.
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            from openai import AsyncOpenAI

            self._client_loop = loop
            self._client = AsyncOpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=2,
            )
        return self._client

    def _cache_key(self, messages: list[dict], n: int, schema: dict | None) -> str:
        c = self.config
        return ResponseCache.key({
            "model": c.model, "messages": messages, "n": n, "temperature": c.temperature,
            "top_p": c.top_p, "max_tokens": c.max_tokens, "schema": schema,
            "enable_thinking": c.enable_thinking,
        })

    async def complete(self, messages: list[dict], n: int = 1, schema: dict | None = None) -> Completion:
        key = self._cache_key(messages, n, schema)
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        if self.offline:
            raise LLMUnavailable("offline mode and no cached response for this request")

        c = self.config
        kwargs: dict = dict(model=c.model, messages=messages, n=n, temperature=c.temperature,
                            top_p=c.top_p, max_tokens=c.max_tokens)
        extra: dict = {}
        if c.enable_thinking is not None:
            extra["chat_template_kwargs"] = {"enable_thinking": c.enable_thinking}
        if extra:
            kwargs["extra_body"] = extra
        if schema is not None and self._schema_supported:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "forecast_adjustment", "schema": schema},
            }

        from openai import APIConnectionError, APITimeoutError, BadRequestError

        client = self._get_client()
        t0 = time.perf_counter()
        try:
            resp = await client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            msg = str(e).lower()
            if "response_format" not in kwargs or not any(
                    k in msg for k in ("response_format", "json_schema", "guided", "structured")):
                raise
            # Server without guided decoding: fall back to plain JSON prompting for the rest of the run.
            logger.warning("endpoint rejected response_format (%s); continuing without guided JSON", str(e)[:200])
            self._schema_supported = False
            kwargs.pop("response_format")
            resp = await client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            raise LLMUnavailable(f"{c.base_url}: {e}") from e
        latency = time.perf_counter() - t0

        usage = getattr(resp, "usage", None)
        out = Completion(
            texts=[strip_reasoning(ch.message.content or "") for ch in resp.choices],
            model=getattr(resp, "model", c.model) or c.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_s=round(latency, 3),
        )
        if self.cache is not None:
            self.cache.put(key, out)
        return out

    async def list_models(self) -> list[str]:
        if self.offline:
            raise LLMUnavailable("offline mode")
        from openai import APIConnectionError, APITimeoutError

        try:
            page = await self._get_client().models.list()
        except (APIConnectionError, APITimeoutError) as e:
            raise LLMUnavailable(f"{self.config.base_url}: {e}") from e
        return [m.id for m in page.data]


class FakeLLM:
    """Deterministic stand-in for tests: ``responder(messages, n)`` returns n texts."""

    def __init__(self, responder: Callable[[list[dict], int], list[str]], model: str = "fake-llm"):
        self.responder = responder
        self.model = model
        self.calls: list[dict] = []

    async def complete(self, messages: list[dict], n: int = 1, schema: dict | None = None) -> Completion:
        self.calls.append({"messages": messages, "n": n, "schema": schema})
        await asyncio.sleep(0)
        texts = self.responder(messages, n)
        return Completion(texts=texts, model=self.model, prompt_tokens=100, completion_tokens=50 * n, latency_s=0.01)
