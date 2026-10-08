"""Use an existing loopback Responses service without exporting its credentials."""
from __future__ import annotations

from urllib.parse import urlsplit

from forecasting_tools import GeneralLlm
from openai import AsyncOpenAI


class LocalResponsesLlm(GeneralLlm):
    """Keep the SDK's output validation, bypass its incompatible LiteLLM transport."""

    def __init__(self, model: str, base_url: str, *, search: bool = False):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("LOCAL_MODEL_BASE_URL must be a credential-free loopback URL.")
        if model.startswith(("metaculus/", "openrouter/", "anthropic/")):
            raise ValueError("Use the model ID served by your local Responses service.")
        super().__init__(model=model, responses_api=True, allowed_tries=1)
        self._response_model = model.removeprefix("openai/")
        self._search = search
        self._client = AsyncOpenAI(
            base_url=base_url.rstrip("/"), api_key="local-proxy",
            timeout=240, max_retries=1,
        )
        self.request_count = 0
        self.search_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    async def invoke(self, prompt, system_prompt: str | None = None) -> str:
        messages = self.model_input_to_message(prompt, system_prompt)
        kwargs = {}
        if self._search:
            kwargs = {"tools": [{"type": "web_search"}], "tool_choice": "required"}
        response = await self._client.responses.create(
            model=self._response_model, input=messages, store=False,
            reasoning={"effort": "medium"}, **kwargs,
        )
        if response.status != "completed":
            raise RuntimeError(f"Local model response was {response.status}, not completed.")
        completed_searches = sum(
            item.type == "web_search_call" and getattr(item, "status", None) == "completed"
            for item in response.output
        )
        if self._search and not completed_searches:
            raise RuntimeError("Research response did not complete a web search.")
        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("Local model returned no answer text.")
        citations = []
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    for annotation in getattr(part, "annotations", []):
                        if annotation.type == "url_citation" and annotation.url not in citations:
                            citations.append(annotation.url)
        if citations:
            answer += "\n\nVerified source URLs:\n" + "\n".join(citations)
        self.request_count += 1
        self.search_calls += completed_searches
        if response.usage:
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
        return answer

    def to_dict(self) -> dict:
        return {"model": self.model, "responses_api": True, "web_search": self._search}

    def usage_summary(self) -> dict:
        return {**self.to_dict(), "requests": self.request_count,
                "web_search_calls": self.search_calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cost_usd": None}
