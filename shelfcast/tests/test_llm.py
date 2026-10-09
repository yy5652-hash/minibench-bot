"""The real OpenAI-compatible client against a local mock of vLLM's chat API."""

import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shelfcast.agent import OUTPUT_SCHEMA, ForecastAgent
from shelfcast.llm import LLMConfig, LLMUnavailable, OpenAICompatibleLLM, ResponseCache, strip_reasoning

ANSWER = {"analysis": "promo week", "drivers": [{"name": "promo", "effect_pct": 25, "evidence": "x"}],
          "median_multiplier": 1.25, "downside_spread": 1.0, "upside_spread": 1.3, "confidence": "high"}


def _mock_vllm(state: dict) -> FastAPI:
    app = FastAPI()

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": "mock/model", "object": "model", "owned_by": "vllm"}]}

    @app.post("/v1/chat/completions")
    async def chat(req: Request):
        body = await req.json()
        state["requests"].append(body)
        if state.get("reject_schema") and "response_format" in body:
            return JSONResponse({"object": "error", "message": "response_format not supported",
                                 "type": "BadRequestError", "code": 400}, status_code=400)
        n = body.get("n", 1)
        content = "<think>hmm</think>" + json.dumps(ANSWER)
        return {
            "id": "cmpl-1", "object": "chat.completion", "created": int(time.time()), "model": body["model"],
            "choices": [{"index": i, "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"} for i in range(n)],
            "usage": {"prompt_tokens": 900, "completion_tokens": 120 * n, "total_tokens": 900 + 120 * n},
        }

    return app


@pytest.fixture
def mock_server():
    state = {"requests": []}
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(_mock_vllm(state), host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/v1", state
    server.should_exit = True
    th.join(timeout=5)


def _cfg(url):
    return LLMConfig(base_url=url, model="mock/model", api_key="k", enable_thinking=False)


def test_client_sends_n_and_schema(mock_server, tmp_path):
    url, state = mock_server
    llm = OpenAICompatibleLLM(_cfg(url), cache=ResponseCache(tmp_path / "c.sqlite"))
    msgs = [{"role": "user", "content": "hi"}]
    comp = asyncio.run(llm.complete(msgs, n=4, schema=OUTPUT_SCHEMA))
    assert len(comp.texts) == 4 and json.loads(comp.texts[0]) == ANSWER
    assert comp.prompt_tokens == 900 and comp.completion_tokens == 480 and not comp.cached
    body = state["requests"][0]
    assert body["n"] == 4 and body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == OUTPUT_SCHEMA
    assert body["chat_template_kwargs"] == {"enable_thinking": False}

    again = asyncio.run(llm.complete(msgs, n=4, schema=OUTPUT_SCHEMA))
    assert again.cached and len(state["requests"]) == 1

    offline = OpenAICompatibleLLM(_cfg(url), cache=ResponseCache(tmp_path / "c.sqlite"), offline=True)
    assert asyncio.run(offline.complete(msgs, n=4, schema=OUTPUT_SCHEMA)).cached
    with pytest.raises(LLMUnavailable):
        asyncio.run(offline.complete([{"role": "user", "content": "new"}], n=4, schema=OUTPUT_SCHEMA))
    assert asyncio.run(llm.list_models()) == ["mock/model"]


def test_client_falls_back_without_guided_decoding(mock_server):
    url, state = mock_server
    state["reject_schema"] = True
    llm = OpenAICompatibleLLM(_cfg(url))
    comp = asyncio.run(llm.complete([{"role": "user", "content": "hi"}], n=2, schema=OUTPUT_SCHEMA))
    assert len(comp.texts) == 2
    assert "response_format" in state["requests"][0] and "response_format" not in state["requests"][1]
    asyncio.run(llm.complete([{"role": "user", "content": "again"}], n=1, schema=OUTPUT_SCHEMA))
    assert "response_format" not in state["requests"][2]


def test_unreachable_endpoint_is_reported():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cfg = LLMConfig(base_url=f"http://127.0.0.1:{port}/v1", model="m", timeout=2)
    llm = OpenAICompatibleLLM(cfg)
    with pytest.raises(LLMUnavailable):
        asyncio.run(llm.complete([{"role": "user", "content": "x"}]))


def test_agent_end_to_end_over_http(mock_server, synthetic):
    url, _ = mock_server
    agent = ForecastAgent(OpenAICompatibleLLM(_cfg(url)), n_samples=3)
    s = synthetic.get("SNK-001")
    fc = asyncio.run(agent.forecast(s, s.last_known_index()))
    assert fc.llm_ok and fc.adjustment.median_multiplier == 1.25 and fc.usage["prompt_tokens"] == 900


def test_strip_reasoning():
    assert strip_reasoning("<think>a\nb</think>\n{\"x\": 1}") == '{"x": 1}'
    assert strip_reasoning("reasoning without opener</think>{}") == "{}"
    assert strip_reasoning(None) == ""


def test_bench_against_mock_server(mock_server, synthetic):
    from shelfcast.bench import run_bench

    url, state = mock_server
    res = asyncio.run(run_bench(OpenAICompatibleLLM(_cfg(url)), synthetic, concurrencies=(1, 4), n_samples=2,
                                progress=None))
    assert [lv["concurrency"] for lv in res["levels"]] == [1, 4]
    lv = res["levels"][1]
    assert lv["requests"] == 16 and lv["parse_rate"] == 1.0 and lv["usd_per_1k_forecasts"] > 0
    prompts = [r["messages"][-1]["content"] for r in state["requests"]]
    assert len(set(prompts)) == len(prompts) == 32  # no repeated prompt, so no prefix-cache shortcut
    with pytest.raises(ValueError):
        asyncio.run(run_bench(OpenAICompatibleLLM(_cfg(url), cache=ResponseCache(":memory:")), synthetic))
