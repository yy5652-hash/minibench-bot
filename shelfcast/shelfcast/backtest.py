"""Rolling-origin backtest: baseline vs agent, scored on accuracy and on money.

For every series and each of the last ``n_origins`` observed weeks, forecast
that week from the weeks before it, then score:

* forecast quality: scaled pinball loss, 80%/90% interval coverage, WAPE, bias;
* forecast value add (FVA): how much the agent improves on the baseline;
* inventory outcome: order with the newsvendor rule and count the real cost
  of leftovers and lost sales against what actually sold.

``rule`` is an ablation: a classical uplift rule that multiplies the same
evidence the agent reads, with no LLM. The gap between ``rule`` and ``agent``
is what the model's judgment adds.

Calibrated variants (``*_cal``) are fit only on forecasts for earlier weeks.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np

from . import LEVELS
from .agent import ForecastAgent, apply_adjustment, rule_adjustment
from .baseline import baseline_forecast
from .calibration import QuantileCalibrator
from .data import Dataset, event_key
from .decision import Economics, order_quantity, realized_cost
from .metrics import summarize

METHODS = ("snaive", "baseline", "baseline_cal", "rule", "rule_cal", "agent", "agent_cal")


@dataclass
class BacktestConfig:
    n_origins: int = 26
    n_samples: int = 5
    concurrency: int = 64
    margin_pct: float = 0.35
    overage_pct: float = 0.25
    calib_min_samples: int = 40
    min_history: int = 26


def _jobs(dataset: Dataset, cfg: BacktestConfig):
    jobs = []
    for s in dataset.series:
        last = s.last_known_index()
        for t in range(last - cfg.n_origins + 1, last + 1):
            if t >= cfg.min_history and not np.isnan(s.demand[t]):
                jobs.append((s, t))
    return jobs


def _inventory(records: list[dict], key: str, cfg: BacktestConfig) -> dict:
    cost = lost = left = sold = demand = stockouts = 0.0
    for r in records:
        econ = Economics(r["price"], cfg.margin_pct, cfg.overage_pct)
        order = order_quantity(np.array(r[key]), econ)
        y = r["actual"]
        cost += realized_cost(order, y, econ)
        lost += max(y - order, 0.0)
        left += max(order - y, 0.0)
        sold += min(order, y)
        demand += y
        stockouts += y > order
    return {
        "total_cost": round(cost, 2),
        "lost_sales_units": round(lost, 1),
        "leftover_units": round(left, 1),
        "fill_rate": round(sold / max(demand, 1e-9), 4),
        "stockout_rate": round(stockouts / max(len(records), 1), 4),
    }


def _score(records: list[dict], cfg: BacktestConfig) -> dict:
    out = {}
    for m in METHODS:
        out[m] = {**summarize(records, m), **_inventory(records, m, cfg)}
    # Like against like: the calibrated agent against the calibrated baseline and rule,
    # so calibration itself is never credited to the model. Raw-vs-raw is kept alongside.
    b, a, r = out["baseline_cal"], out["agent_cal"], out["rule_cal"]
    if b.get("scaled_pinball"):
        out["fva_pinball_pct"] = round(100 * (1 - a["scaled_pinball"] / b["scaled_pinball"]), 2)
        out["fva_pinball_raw_pct"] = round(
            100 * (1 - out["agent"]["scaled_pinball"] / out["baseline"]["scaled_pinball"]), 2)
    if b.get("scaled_pinball") and r.get("scaled_pinball"):
        out["fva_vs_rule_pct"] = round(100 * (1 - a["scaled_pinball"] / r["scaled_pinball"]), 2)
    if b.get("total_cost"):
        out["cost_saving_pct"] = round(100 * (1 - a["total_cost"] / b["total_cost"]), 2)
        out["cost_saving_raw_pct"] = round(100 * (1 - out["agent"]["total_cost"] / out["baseline"]["total_cost"]), 2)
    return out


async def run_backtest(dataset: Dataset, agent: ForecastAgent, cfg: BacktestConfig | None = None,
                       progress=None) -> dict:
    cfg = cfg or BacktestConfig()
    jobs = _jobs(dataset, cfg)
    t0 = time.perf_counter()
    forecasts = await agent.forecast_many(jobs, concurrency=cfg.concurrency, progress=progress)
    wall = time.perf_counter() - t0

    records: list[dict] = []
    for (s, t), fc in zip(jobs, forecasts):
        sn = baseline_forecast(s.demand[:t], method="snaive")
        rule_q = apply_adjustment(fc.baseline.quantiles, rule_adjustment(fc.context))
        price = float(s.price[t]) if not np.isnan(s.price[t]) else 1.0
        adj = fc.adjustment
        records.append({
            "sku_id": s.sku_id, "title": s.title, "category": s.category,
            "week": s.week_starts[t], "target_index": t,
            "actual": float(s.demand[t]), "scale": fc.scale, "price": price,
            "events": s.events[t],
            "event_week": any(event_key(e) != "SNAP" for e in s.events[t]),
            "snaive": [round(float(x), 3) for x in sn.quantiles],
            "baseline": [round(float(x), 3) for x in fc.baseline.quantiles],
            "rule": [round(float(x), 3) for x in rule_q],
            "agent": [round(float(x), 3) for x in fc.quantiles],
            "llm_ok": fc.llm_ok, "error": fc.error,
            "median_multiplier": None if adj is None else round(adj.median_multiplier, 3),
            "downside_spread": None if adj is None else round(adj.downside_spread, 3),
            "upside_spread": None if adj is None else round(adj.upside_spread, 3),
            "confidence": None if adj is None else adj.confidence,
            "drivers": [] if adj is None else adj.drivers,
            "analysis": "" if adj is None else adj.analysis[:600],
            "sample_multipliers": [round(x.median_multiplier, 3) for x in fc.samples],
            "usage": fc.usage,
        })

    # Calibrate each week on the weeks before it only.
    weeks = sorted({r["week"] for r in records})
    cals = {}
    for w in weeks:
        past = [r for r in records if r["week"] < w]
        today = [r for r in records if r["week"] == w]
        for src in ("baseline", "rule", "agent"):
            cal = QuantileCalibrator(min_samples=cfg.calib_min_samples)
            if past:
                cal.fit(np.array([r[src] for r in past]), np.array([r["actual"] for r in past]),
                        np.array([r["scale"] for r in past]))
            cals[src] = cal
            for r in today:
                r[f"{src}_cal"] = [round(float(x), 3) for x in cal.apply(np.array(r[src]), r["scale"])]

    summary = _score(records, cfg)
    segments = {
        "event_weeks": _score([r for r in records if r["event_week"]], cfg),
        "ordinary_weeks": _score([r for r in records if not r["event_week"]], cfg),
    }
    by_category = {}
    for c in sorted({r["category"].split(" / ")[0] for r in records}):
        sub = [r for r in records if r["category"].split(" / ")[0] == c]
        by_category[c] = _score(sub, cfg)

    usage = [r["usage"] for r in records if r["usage"]]
    ok = [r for r in records if r["llm_ok"]]
    llm_stats = {
        "forecasts": len(records),
        "llm_ok": len(ok),
        "cached": sum(1 for u in usage if u.get("cached")),
        "samples_per_forecast": agent.n_samples,
        "prompt_tokens": int(sum(u.get("prompt_tokens", 0) for u in usage)),
        "completion_tokens": int(sum(u.get("completion_tokens", 0) for u in usage)),
        "mean_latency_s": round(float(np.mean([u["latency_s"] for u in usage])), 3) if usage else None,
        "wall_time_s": round(wall, 2),
        "model": usage[0]["model"] if usage else getattr(agent.llm, "model", None),
        "errors": sorted({r["error"] for r in records if r["error"]})[:10],
    }
    return {
        "meta": {
            "dataset": dataset.name, "source": dataset.source, "description": dataset.description,
            "n_series": len(dataset.series), "n_forecasts": len(records), "weeks": [weeks[0], weeks[-1]] if weeks else [],
            "levels": list(LEVELS), "config": asdict(cfg),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "summary": summary,
        "segments": segments,
        "by_category": by_category,
        "llm": llm_stats,
        "calibration": {k: v.to_dict() for k, v in cals.items()},
        "records": records,
    }
