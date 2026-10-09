import asyncio
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from shelfcast import LEVELS
from shelfcast.agent import ForecastAgent
from shelfcast.backtest import METHODS, BacktestConfig, run_backtest
from shelfcast.cli import main
from shelfcast.llm import FakeLLM, LLMConfig, OpenAICompatibleLLM, ResponseCache
from shelfcast.report import backtest_markdown, bench_markdown
from shelfcast.server import create_app


@pytest.fixture(scope="module")
def backtest_result(synthetic):
    from tests.conftest import planner_responder

    agent = ForecastAgent(FakeLLM(planner_responder), n_samples=3)
    cfg = BacktestConfig(n_origins=12, n_samples=3, concurrency=8)
    return asyncio.run(run_backtest(synthetic, agent, cfg))


def test_backtest_structure(backtest_result, synthetic):
    res = backtest_result
    assert res["meta"]["n_forecasts"] == 12 * len(synthetic.series)
    assert res["llm"]["llm_ok"] == res["meta"]["n_forecasts"]
    for m in METHODS:
        s = res["summary"][m]
        assert {"scaled_pinball", "coverage_80", "total_cost", "fill_rate"} <= set(s)
    assert "fva_pinball_pct" in res["summary"] and "cost_saving_pct" in res["summary"]
    r = res["records"][0]
    assert len(r["agent_cal"]) == len(LEVELS) and len(r["baseline_cal"]) == len(LEVELS)
    assert res["segments"]["event_weeks"]["agent"]["n"] + res["segments"]["ordinary_weeks"]["agent"]["n"] == len(
        res["records"])
    json.dumps(res)  # serialisable


def test_backtest_calibration_uses_only_past_weeks(backtest_result):
    first_week = min(r["week"] for r in backtest_result["records"])
    for r in backtest_result["records"]:
        if r["week"] == first_week:
            assert r["agent_cal"] == r["agent"]


def test_evidence_in_the_brief_beats_baseline_in_event_weeks(synthetic):
    from tests.conftest import evidence_responder

    agent = ForecastAgent(FakeLLM(evidence_responder), n_samples=1)
    res = asyncio.run(run_backtest(synthetic, agent, BacktestConfig(n_origins=52, n_samples=1)))
    ev = res["segments"]["event_weeks"]
    assert ev["agent"]["scaled_pinball"] < 0.9 * ev["baseline"]["scaled_pinball"]
    assert ev["agent_cal"]["total_cost"] < ev["baseline"]["total_cost"]


def test_markdown_reports(backtest_result):
    md = backtest_markdown(backtest_result)
    assert "ShelfCast agent + calibration" in md and "Event weeks" in md
    bench = {"model": "m", "n_samples": 5, "price_per_hour": 1.99, "created_at": "now", "gpu_info": "MI300X",
             "levels": [{"concurrency": 8, "forecasts_per_min": 100.0, "output_tok_per_s": 900.0,
                         "p50_latency_s": 1.0, "p95_latency_s": 2.0, "usd_per_1k_forecasts": 0.33,
                         "parse_rate": 1.0}]}
    assert "MI300X" in bench_markdown(bench)


@pytest.fixture
def client(tmp_path, synthetic, backtest_result):
    (tmp_path / f"backtest_{synthetic.name}.json").write_text(json.dumps(backtest_result))
    other = {**backtest_result, "meta": {**backtest_result["meta"], "dataset": "m5-60", "source": "m5"}}
    (tmp_path / "backtest_m5-60.json").write_text(json.dumps(other))
    (tmp_path / "gpu_info.txt").write_text("AMD Instinct MI300X")
    from tests.conftest import planner_responder

    agent = ForecastAgent(FakeLLM(planner_responder), n_samples=3)
    return TestClient(create_app(synthetic, agent, results_dir=tmp_path, mode="live"))


def test_server_info_and_skus(client):
    info = client.get("/api/info").json()
    assert info["mode"] == "live" and info["gpu_info"] == "AMD Instinct MI300X"
    assert info["calibration"]["active"]
    skus = client.get("/api/skus").json()
    assert len(skus) == 20
    pumpkin = next(s for s in skus if s["sku_id"] == "BAK-001")
    labels = [w["label"] for w in pumpkin["weeks"]]
    assert any("Thanksgiving" in lbl and lbl.startswith("2026-11-23") for lbl in labels)
    assert any("(actual known)" in lbl for lbl in labels)


def test_server_forecast_future_week(client, synthetic):
    s = synthetic.get("BAK-001")
    t = s.week_starts.index("2026-11-23")
    r = client.post("/api/forecast", json={"sku_id": "BAK-001", "target_index": t}).json()
    assert r["llm_ok"] and r["calibrated"] and r["horizon"] == 7
    d = r["decision"]
    assert d["orders"]["agent"] > d["orders"]["baseline"]
    assert "actual" not in d and len(r["chart"]["weeks"]) == 27
    assert "Thanksgiving" in r["brief"]


def test_server_forecast_past_week_scores_both(client, synthetic):
    s = synthetic.get("SNK-001")
    t = s.last_known_index()
    r = client.post("/api/forecast", json={"sku_id": "SNK-001", "target_index": t,
                                           "notes": "store closed two days for repairs"}).json()
    d = r["decision"]
    assert d["actual"] == s.demand[t]
    assert set(d["realized_cost"]) == {"baseline", "agent"} and set(d["pinball"]) == {"baseline", "agent"}
    assert any(dr["name"] == "closure" for dr in r["adjustment"]["drivers"])


def test_server_rejects_bad_requests(client):
    assert client.post("/api/forecast", json={"sku_id": "NOPE"}).status_code == 404
    assert client.post("/api/forecast", json={"sku_id": "BAK-001", "target_index": 5}).status_code == 400
    assert client.post("/api/forecast", json={"sku_id": "BAK-001", "margin_pct": 1.5}).status_code == 422


def test_server_backtest_and_bench(client):
    bt = client.get("/api/backtest").json()
    assert bt["available"] and len(bt["runs"]) == 2
    real, synth = bt["runs"]
    assert real["meta"]["source"] == "m5" and not real["replayable"] and real["best"] == []
    assert synth["replayable"] and len(synth["best"]) == 6 and len(synth["worst"]) == 3
    assert "records" not in synth
    assert client.get("/api/bench").json() == {"available": False}
    assert "ShelfCast" in client.get("/").text


def test_replay_mode_serves_cache_then_baseline(tmp_path, synthetic):
    cache = ResponseCache(tmp_path / "c.sqlite")
    cfg = LLMConfig(base_url="http://127.0.0.1:9/v1", model="m")
    agent = ForecastAgent(OpenAICompatibleLLM(cfg, cache=cache, offline=True), n_samples=2)
    s = synthetic.get("SNK-001")
    t = s.last_known_index() + 1
    _, msgs = agent.build(s, t)
    key = agent.llm._cache_key(msgs, 2, __import__("shelfcast.agent", fromlist=["OUTPUT_SCHEMA"]).OUTPUT_SCHEMA)
    from shelfcast.llm import Completion

    ans = json.dumps({"analysis": "a", "drivers": [], "median_multiplier": 1.1, "downside_spread": 1,
                      "upside_spread": 1, "confidence": "low"})
    cache.put(key, Completion(texts=[ans, ans], model="m"))
    c = TestClient(create_app(synthetic, agent, results_dir=tmp_path, mode="replay"))
    hit = c.post("/api/forecast", json={"sku_id": "SNK-001", "target_index": t}).json()
    assert hit["llm_ok"] and hit["usage"]["cached"] and hit["mode"] == "replay"
    miss = c.post("/api/forecast", json={"sku_id": "SNK-001", "target_index": t, "notes": "new"}).json()
    assert not miss["llm_ok"] and "offline" in miss["error"]
    assert np.allclose(miss["final_quantiles"], miss["baseline"]["quantiles"])


def test_cli_offline_backtest_writes_reports(tmp_path, synthetic, capsys):
    ds_path = tmp_path / "ds.json"
    synthetic.save(ds_path)
    main(["backtest", "--dataset", str(ds_path), "--origins", "2", "--offline",
          "--cache", str(tmp_path / "c.sqlite"), "--out-dir", str(tmp_path / "out")])
    res = json.loads((tmp_path / "out" / f"backtest_{synthetic.name}.json").read_text())
    assert res["llm"]["llm_ok"] == 0 and res["meta"]["n_forecasts"] == 40
    assert (tmp_path / "out" / f"backtest_{synthetic.name}.md").exists()
