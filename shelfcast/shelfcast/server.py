"""Demo web app: pick a product and week, add planner notes, get an order.

``live`` mode calls the vLLM endpoint (answers are cached). ``replay`` mode
never calls a model: it serves cached answers and falls back to the baseline
when a request was never run, so the demo URL keeps working after the GPU
instance is shut down.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import LEVELS
from .agent import ForecastAgent
from .calibration import QuantileCalibrator
from .data import Dataset, event_key
from .decision import Economics, expected_cost, order_quantity, realized_cost
from .llm import LLMUnavailable
from .metrics import pinball

WEB_DIR = Path(__file__).parent / "web"


class ForecastRequest(BaseModel):
    sku_id: str
    target_index: int | None = None
    notes: str | None = Field(default=None, max_length=1000)
    margin_pct: float = Field(default=0.35, gt=0.0, lt=1.0)
    overage_pct: float = Field(default=0.25, gt=0.0, le=2.0)


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _week_label(series, i: int) -> str:
    evs = [event_key(e).split(": ", 1)[-1] for e in series.events[i] if event_key(e) != "SNAP"]
    tag = "" if np.isnan(series.demand[i]) else " (actual known)"
    return series.week_starts[i] + (f" · {', '.join(evs)}" if evs else "") + tag


def create_app(dataset: Dataset, agent: ForecastAgent, results_dir: str | Path = "results",
               mode: str = "live") -> FastAPI:
    results_dir = Path(results_dir)
    app = FastAPI(title="ShelfCast", version="0.1.0")

    backtest = _load_json(results_dir / f"backtest_{dataset.name}.json")
    bench = _load_json(results_dir / "bench.json")
    gpu_txt = None
    if (results_dir / "gpu_info.txt").exists():
        gpu_txt = (results_dir / "gpu_info.txt").read_text()
    elif bench and bench.get("gpu_info"):
        gpu_txt = bench["gpu_info"]

    cal_records = [r for r in backtest["records"] if r.get("llm_ok")] if backtest else []
    calibrators: dict[str, QuantileCalibrator] = {}

    def calibrator_for(week: str | None) -> QuantileCalibrator:
        """Calibrator fit on backtest weeks before ``week`` (all of them when None)."""
        key = week or "*"
        if key not in calibrators:
            recs = [r for r in cal_records if week is None or r["week"] < week]
            cal = QuantileCalibrator()
            if recs:
                cal.fit(np.array([r["agent"] for r in recs]), np.array([r["actual"] for r in recs]),
                        np.array([r["scale"] for r in recs]))
            calibrators[key] = cal
        return calibrators[key]

    calibrator = calibrator_for(None)

    highlights: dict[str, list[dict]] = {"best": [], "worst": []}
    if cal_records:
        def gain(r: dict) -> float:
            final = r.get("agent_cal", r["agent"])
            return (pinball(r["actual"], np.array(r["baseline"])) - pinball(r["actual"], np.array(final))) / max(
                r["scale"], 1.0)

        def brief(r: dict) -> dict:
            mid = LEVELS.index(0.5)
            return {
                **{k: r[k] for k in ("sku_id", "title", "week", "target_index", "actual", "events",
                                     "median_multiplier", "drivers")},
                "gain": round(gain(r), 3),
                "baseline_median": r["baseline"][mid],
                "agent_median": r.get("agent_cal", r["agent"])[mid],
            }

        ranked = sorted(cal_records, key=gain, reverse=True)
        highlights = {"best": [brief(r) for r in ranked[:6]], "worst": [brief(r) for r in ranked[::-1][:3]]}

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/info")
    async def info():
        model = getattr(agent.llm, "model", None)
        endpoint_ok = None
        if mode == "live" and hasattr(agent.llm, "list_models"):
            try:
                await agent.llm.list_models()
                endpoint_ok = True
            except LLMUnavailable:
                endpoint_ok = False
            except Exception:
                endpoint_ok = False
        return {
            "dataset": {"name": dataset.name, "source": dataset.source, "description": dataset.description,
                        "n_series": len(dataset.series)},
            "mode": mode,
            "model": model,
            "endpoint_ok": endpoint_ok,
            "n_samples": agent.n_samples,
            "gpu_info": gpu_txt,
            "calibration": calibrator.to_dict(),
            "levels": list(LEVELS),
        }

    @app.get("/api/skus")
    def skus():
        out = []
        for s in dataset.series:
            last = s.last_known_index()
            idx = list(range(max(30, last - 25), min(s.n_weeks, last + 9)))
            default = last + 1 if last + 1 < s.n_weeks else last
            out.append({
                "sku_id": s.sku_id, "title": s.title, "category": s.category, "store": s.store,
                "weeks": [{"index": i, "label": _week_label(s, i)} for i in idx],
                "default_index": default,
            })
        return out

    @app.post("/api/forecast")
    async def forecast(req: ForecastRequest):
        try:
            s = dataset.get(req.sku_id)
        except KeyError:
            raise HTTPException(404, f"unknown sku {req.sku_id}")
        last = s.last_known_index()
        t = req.target_index if req.target_index is not None else min(last + 1, s.n_weeks - 1)
        if not 30 <= t < s.n_weeks:
            raise HTTPException(400, "target week out of range")
        notes = (req.notes or "").strip() or None
        fc = await agent.forecast(s, t, notes=notes)
        res = fc.to_dict(include_context=True)

        agent_q = fc.quantiles
        res["calibrated"] = False
        # For a past week, calibrate only on outcomes known before it.
        cal = calibrator_for(None if np.isnan(s.demand[t]) else s.week_starts[t])
        if fc.llm_ok and cal.active:
            agent_q = cal.apply(fc.quantiles, fc.scale)
            res["calibrated"] = True
        res["final_quantiles"] = [round(float(x), 3) for x in agent_q]

        price = float(s.price[t]) if not np.isnan(s.price[t]) else 1.0
        econ = Economics(price, req.margin_pct, req.overage_pct)
        base_q = fc.baseline.quantiles
        orders = {"baseline": order_quantity(base_q, econ), "agent": order_quantity(agent_q, econ)}
        decision = {
            "unit_price": price,
            "critical_ratio": round(econ.critical_ratio, 4),
            "underage_per_unit": round(econ.underage, 3),
            "overage_per_unit": round(econ.overage, 3),
            "orders": orders,
            # Both orders judged against the agent's distribution: what the agent expects each to cost.
            "expected_cost_under_agent": {k: round(expected_cost(agent_q, v, econ), 2) for k, v in orders.items()},
        }
        actual = None if np.isnan(s.demand[t]) else float(s.demand[t])
        if actual is not None:
            decision["actual"] = actual
            decision["realized_cost"] = {k: round(realized_cost(v, actual, econ), 2) for k, v in orders.items()}
            decision["pinball"] = {"baseline": round(pinball(actual, base_q), 3),
                                   "agent": round(pinball(actual, agent_q), 3)}
        res["decision"] = decision

        lo = max(0, t - 26)
        res["chart"] = {
            "weeks": s.week_starts[lo:t + 1],
            "demand": [None if np.isnan(v) else float(v) for v in s.demand[lo:t]],
            "events": s.events[lo:t + 1],
        }
        res["mode"] = mode
        return JSONResponse(res)

    # Every backtest in the results folder is shown; real data first. Only runs on the
    # served dataset carry clickable case studies, since those can be replayed here.
    runs = []
    for path in sorted(results_dir.glob("backtest_*.json")):
        bt = _load_json(path)
        if not bt or "summary" not in bt:
            continue
        own = bt["meta"]["dataset"] == dataset.name
        runs.append({key: bt[key] for key in ("meta", "summary", "segments", "llm")}
                    | (highlights if own else {"best": [], "worst": []}) | {"replayable": own})
    runs.sort(key=lambda r: (r["meta"]["source"] == "synthetic", r["meta"]["dataset"]))

    @app.get("/api/backtest")
    def backtest_summary():
        return {"available": bool(runs), "runs": runs}

    @app.get("/api/bench")
    def bench_summary():
        return bench or {"available": False}

    return app
