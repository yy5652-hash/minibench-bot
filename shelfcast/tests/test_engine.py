import asyncio
import json

import numpy as np
import pytest

from shelfcast import LEVELS
from shelfcast.agent import Adjustment, ForecastAgent, apply_adjustment, combine, parse_adjustment
from shelfcast.baseline import baseline_forecast
from shelfcast.calibration import QuantileCalibrator
from shelfcast.decision import Economics, expected_cost, order_quantity, quantile_at, realized_cost
from shelfcast.features import build_context, render_context
from shelfcast.llm import FakeLLM, LLMUnavailable
from shelfcast.metrics import pinball, summarize

MID = LEVELS.index(0.5)


# ---------------------------------------------------------------- baseline


def test_baseline_constant_series():
    b = baseline_forecast(np.full(60, 50.0))
    assert b.method == "ses"
    np.testing.assert_allclose(b.quantiles, 50.0, atol=1e-6)


def test_baseline_quantiles_ordered_and_nonnegative():
    rng = np.random.default_rng(1)
    y = rng.poisson(3, size=120).astype(float)
    b = baseline_forecast(y)
    assert np.all(np.diff(b.quantiles) >= 0) and b.quantiles[0] >= 0
    assert b.quantiles[0] < b.quantiles[-1]


def test_baseline_short_and_empty_history():
    assert baseline_forecast(np.array([])).point == 0.0
    b = baseline_forecast(np.array([10.0, 12.0]))
    assert b.quantiles[MID] == pytest.approx(11.0)


def test_snaive_uses_same_week_last_year():
    y = np.arange(120, dtype=float)
    b = baseline_forecast(y, method="snaive")
    assert b.point == y[120 - 52]


def test_horizon_widens_interval():
    rng = np.random.default_rng(2)
    y = 100 + rng.normal(0, 10, size=150)
    w1 = np.ptp(baseline_forecast(y, horizon=1).quantiles)
    w4 = np.ptp(baseline_forecast(y, horizon=4).quantiles)
    assert w4 > w1


# ---------------------------------------------------------------- features


def test_context_finds_event_history(synthetic):
    s = synthetic.get("BAK-001")
    t = s.week_starts.index("2025-11-24")
    ctx = build_context(s, t)
    assert ctx.horizon == 1 and ctx.target_events == ["Holiday: Thanksgiving (Thu)"]
    tg = next(e for e in ctx.event_history if e["event"] == "Holiday: Thanksgiving")
    assert len(tg["occurrences"]) == 2 and tg["median_vs_baseline"] > 2
    # nothing from the target week or later leaks into the brief
    assert all(r["week"] < "2025-11-24" for r in ctx.recent)
    text = render_context(ctx)
    assert "Thanksgiving" in text and "STATISTICAL BASELINE" in text


def test_context_separates_confounded_and_overlapping_events(synthetic):
    # Super Bowl 2025 week also ran a 25% promotion; the week before Valentine's Day is the Super Bowl week.
    s = synthetic.get("SNK-001")
    ctx = build_context(s, s.week_starts.index("2026-02-02"))
    sb = next(e for e in ctx.event_history if e["event"] == "Holiday: Super Bowl")
    confounded = [o for o in sb["occurrences"] if o["also"]]
    clean = [o for o in sb["occurrences"] if not o["also"]]
    assert confounded and clean and not sb["confounded"]
    assert sb["median_vs_baseline"] == clean[0]["vs_baseline"]
    pre_val = next(e for e in ctx.event_history if e["timing"] == "week before the event")
    assert pre_val["occurrences"] == []
    assert "no clean earlier occurrence" in render_context(ctx)


def test_context_future_week_horizon(synthetic):
    s = synthetic.get("CAN-002")
    t = s.week_starts.index("2026-10-26")
    ctx = build_context(s, t, notes="Display moved to the entrance")
    assert ctx.horizon == 3
    assert "planner notes: Display moved" in render_context(ctx)


def test_context_rejects_bad_index(synthetic):
    s = synthetic.series[0]
    with pytest.raises(IndexError):
        build_context(s, s.n_weeks)


# ---------------------------------------------------------------- agent


def test_parse_adjustment_variants():
    good = {"analysis": "x", "drivers": [{"name": "promo", "effect_pct": 30, "evidence": "e"}],
            "median_multiplier": 1.3, "downside_spread": 1, "upside_spread": 1.4, "confidence": "high"}
    a = parse_adjustment(json.dumps(good))
    assert a.median_multiplier == 1.3 and a.drivers[0]["name"] == "promo" and a.confidence == "high"
    assert parse_adjustment("```json\n" + json.dumps(good) + "\n```").median_multiplier == 1.3
    assert parse_adjustment("Here you go: " + json.dumps(good) + " thanks").upside_spread == 1.4
    assert parse_adjustment("no json here") is None
    assert parse_adjustment('{"analysis": "missing numbers"}') is None
    clipped = parse_adjustment(json.dumps({**good, "median_multiplier": 1e6, "downside_spread": -3,
                                           "confidence": "certain"}))
    assert clipped.median_multiplier == 20.0 and clipped.downside_spread == 0.5 and clipped.confidence == "medium"


def test_combine_uses_medians():
    s = [Adjustment(m, 1.0, u, "high", [{"name": str(m)}], str(m)) for m, u in ((1.0, 1.0), (1.5, 1.2), (9.0, 3.0))]
    c = combine(s)
    assert c.median_multiplier == 1.5 and c.upside_spread == 1.2 and c.drivers == [{"name": "1.5"}]


def test_apply_adjustment():
    q = np.array([60, 70, 80, 90, 95, 100, 105, 110, 120, 130, 140], dtype=float)
    same = apply_adjustment(q, Adjustment(1.0, 1.0, 1.0, "medium", [], ""))
    np.testing.assert_allclose(same, q)
    up = apply_adjustment(q, Adjustment(2.0, 1.0, 1.5, "medium", [], ""))
    assert up[MID] == 200 and up[-1] == 2 * (100 + 1.5 * 40)
    assert np.all(np.diff(up) >= 0)
    down = apply_adjustment(q, Adjustment(0.1, 3.0, 1.0, "medium", [], ""))
    assert down.min() >= 0


def test_agent_forecast_with_fake_llm(synthetic, fake_llm):
    s = synthetic.get("BAK-001")
    t = s.week_starts.index("2025-11-24")
    agent = ForecastAgent(fake_llm, n_samples=5)
    fc = asyncio.run(agent.forecast(s, t))
    assert fc.llm_ok and fc.error is None and len(fc.samples) == 5
    assert fc.adjustment.median_multiplier == pytest.approx(1.5)
    assert fc.quantiles[MID] == pytest.approx(1.5 * fc.baseline.quantiles[MID])
    call = fake_llm.calls[0]
    assert call["n"] == 5 and call["schema"]["required"]
    d = fc.to_dict(include_context=True)
    assert d["n_valid"] == 5 and "brief" in d and len(d["quantiles"]) == len(LEVELS)


def test_agent_falls_back_to_baseline(synthetic):
    s = synthetic.series[0]
    t = s.last_known_index()

    async def boom(*a, **k):
        raise LLMUnavailable("down")

    llm = FakeLLM(lambda m, n: ["{}"] * n)
    llm.complete = boom
    fc = asyncio.run(ForecastAgent(llm).forecast(s, t))
    assert not fc.llm_ok and "unavailable" in fc.error
    np.testing.assert_allclose(fc.quantiles, fc.baseline.quantiles)

    fc2 = asyncio.run(ForecastAgent(FakeLLM(lambda m, n: ["garbage"] * n)).forecast(s, t))
    assert not fc2.llm_ok and fc2.error == "no parsable sample"

    fc3 = asyncio.run(ForecastAgent(None).forecast(s, t))
    assert fc3.error == "LLM disabled"


def test_forecast_many_reports_progress(synthetic, fake_llm):
    agent = ForecastAgent(fake_llm, n_samples=2)
    jobs = [(s, s.last_known_index()) for s in synthetic.series[:4]]
    seen = []
    res = asyncio.run(agent.forecast_many(jobs, concurrency=2, progress=lambda d, t, f: seen.append(d)))
    assert len(res) == 4 and sorted(seen) == [1, 2, 3, 4]


# ---------------------------------------------------------------- decisions and scores


def test_economics_and_order():
    e = Economics(unit_price=10.0, margin_pct=0.4, overage_pct=0.5)
    assert e.underage == pytest.approx(4.0) and e.overage == pytest.approx(3.0)
    assert e.critical_ratio == pytest.approx(4 / 7)
    q = np.linspace(50, 150, len(LEVELS))
    assert order_quantity(q, e) == round(quantile_at(q, 4 / 7))


def test_quantile_at_interpolates_and_extrapolates():
    q = np.array(LEVELS) * 100
    assert quantile_at(q, 0.5) == pytest.approx(50)
    assert quantile_at(q, 0.25) == pytest.approx(25)
    assert quantile_at(q, 0.99) == pytest.approx(99)
    assert quantile_at(q, 0.01) == pytest.approx(1)


def test_realized_and_expected_cost():
    e = Economics(10.0, 0.4, 0.5)
    assert realized_cost(10, 7, e) == pytest.approx(9.0)
    assert realized_cost(7, 10, e) == pytest.approx(12.0)
    q = np.linspace(50, 150, len(LEVELS))
    best = order_quantity(q, e)
    costs = {o: expected_cost(q, o, e) for o in (best - 20, best, best + 20)}
    assert costs[best] < costs[best - 20] and costs[best] < costs[best + 20]


def test_pinball_and_summary():
    q = np.full(len(LEVELS), 10.0)
    assert pinball(10.0, q) == 0.0
    assert pinball(12.0, q) == pytest.approx(np.mean(np.array(LEVELS) * 2))
    recs = [{"actual": 10.0, "scale": 10.0, "m": list(np.linspace(5, 15, len(LEVELS)))},
            {"actual": 30.0, "scale": 10.0, "m": list(np.linspace(5, 15, len(LEVELS)))}]
    s = summarize(recs, "m")
    assert s["n"] == 2 and s["coverage_80"] == 0.5 and s["bias_median_pct"] == pytest.approx(-50.0)


def test_calibrator_fixes_biased_forecasts():
    rng = np.random.default_rng(3)
    y = rng.normal(100, 10, size=500)
    z = np.array([-1.645, -1.2816, -0.8416, -0.5244, -0.2533, 0, 0.2533, 0.5244, 0.8416, 1.2816, 1.645])
    q = np.tile(80 + 3 * z, (500, 1))  # too low and too narrow
    cal = QuantileCalibrator().fit(q, y, np.full(500, 100.0))
    fixed = cal.apply(q[0], 100.0)
    assert fixed[MID] == pytest.approx(np.median(y), rel=0.02)
    inside = np.mean((y >= fixed[LEVELS.index(0.1)]) & (y <= fixed[LEVELS.index(0.9)]))
    assert 0.75 < inside < 0.85


def test_calibrator_inactive_with_few_samples():
    cal = QuantileCalibrator(min_samples=40).fit(np.ones((5, len(LEVELS))), np.ones(5), np.ones(5))
    q = np.linspace(1, 2, len(LEVELS))
    np.testing.assert_allclose(cal.apply(q, 1.0), q)


def test_rule_adjustment_ablation(synthetic):
    from shelfcast.agent import rule_adjustment

    s = synthetic.get("BAK-001")
    tg = rule_adjustment(build_context(s, s.week_starts.index("2025-11-24")))
    assert tg.median_multiplier > 1.5 and tg.drivers[0]["name"].startswith("Holiday: Thanksgiving")
    quiet = next(t for t in range(60, s.last_known_index())
                 if not s.events[t] and not s.events[t + 1] and not s.events[t - 1])
    assert rule_adjustment(build_context(s, quiet)).median_multiplier == 1.0
