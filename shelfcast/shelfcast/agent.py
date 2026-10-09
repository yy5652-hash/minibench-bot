"""The forecasting agent: an LLM demand planner that adjusts a statistical baseline.

The model does not write raw numbers for every quantile. It names the drivers
it sees, then returns three numbers: a multiplier for the baseline median and
two spread factors for the downside and upside. That keeps every forecast
anchored to the outside view, makes each adjustment explainable, and keeps the
quantiles ordered. Several samples are drawn per forecast and combined by the
median of each number, which is robust to one sample going astray.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

import numpy as np

from . import LEVELS
from .baseline import BaselineForecast
from .data import Series
from .features import Context, build_context, render_context
from .llm import LLMClient, LLMUnavailable

SYSTEM_PROMPT = """\
You are ShelfCast, a senior retail demand planner with the habits of a superforecaster.

A statistical model has produced a baseline forecast of weekly unit sales for one product in one store.
That model only extrapolates recent sales. It does NOT know about holidays, promotions, price changes
or anything in the planner notes. Your job is to decide how much those known drivers should move the
forecast, the way a careful planner adjusts a system forecast before an order is placed.

Rules:
1. Start from the baseline: it is the outside view. Adjust only for drivers you can name, and size each
   one from the evidence given: how this product sold around the same event before, its past promotion
   lifts, the same week last year, the price change.
2. Do not double count. If recent weeks already show a trend or a seasonal ramp, the baseline has
   partly absorbed it.
3. An ordinary week with no driver gets a median_multiplier of 1.0. Most weeks are ordinary.
4. Combine drivers multiplicatively, then shrink toward 1.0 when the evidence is thin
   (one past occurrence, a discount never tried before, vague notes).
5. Remember what lowers demand: store closures, the week after a promotion (pantry loading),
   price increases, a competitor promotion mentioned in the notes.
6. The brief ends with a classical uplift model's suggestion. It multiplies past effects mechanically.
   Treat it as a starting point and correct it where judgment is needed: effects measured once,
   overlapping events, a discount deeper than any seen before, a season that the baseline has already
   caught up with, and anything in the planner notes, which it cannot read.
7. Spreads: 1.0 keeps the baseline's uncertainty. Widen the side that is more uncertain
   (upside for a promotion or event with variable lift, downside for supply or closure risk).
   Go below 1.0 only with strong evidence of an unusually stable week.
8. Be calibrated: the final 5%-95% range should contain the actual outcome 90% of the time.

Answer with JSON only, in this shape:
{"analysis": "<=120 words of reasoning",
 "drivers": [{"name": "...", "effect_pct": <signed % effect on the median>, "evidence": "..."}],
 "median_multiplier": <number, 1.0 = keep baseline median>,
 "downside_spread": <number>, "upside_spread": <number>,
 "confidence": "low" | "medium" | "high"}"""

OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "effect_pct": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "effect_pct", "evidence"],
            },
        },
        "median_multiplier": {"type": "number"},
        "downside_spread": {"type": "number"},
        "upside_spread": {"type": "number"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["analysis", "drivers", "median_multiplier", "downside_spread", "upside_spread", "confidence"],
}

MULTIPLIER_RANGE = (0.05, 20.0)
SPREAD_RANGE = (0.5, 3.0)


@dataclass
class Adjustment:
    median_multiplier: float
    downside_spread: float
    upside_spread: float
    confidence: str
    drivers: list[dict]
    analysis: str


@dataclass
class AgentForecast:
    sku_id: str
    title: str
    target_index: int
    target_week: str
    horizon: int
    baseline: BaselineForecast
    quantiles: np.ndarray
    adjustment: Adjustment | None
    samples: list[Adjustment] = field(default_factory=list)
    n_requested: int = 0
    llm_ok: bool = False
    error: str | None = None
    usage: dict = field(default_factory=dict)
    scale: float = 1.0
    context: Context | None = None

    def to_dict(self, include_context: bool = False) -> dict:
        adj = self.adjustment
        d = {
            "sku_id": self.sku_id,
            "title": self.title,
            "target_index": self.target_index,
            "target_week": self.target_week,
            "horizon": self.horizon,
            "levels": list(LEVELS),
            "baseline": {"method": self.baseline.method, "quantiles": _r(self.baseline.quantiles),
                         "alpha": self.baseline.alpha},
            "quantiles": _r(self.quantiles),
            "llm_ok": self.llm_ok,
            "error": self.error,
            "n_requested": self.n_requested,
            "n_valid": len(self.samples),
            "adjustment": None if adj is None else {
                "median_multiplier": round(adj.median_multiplier, 4),
                "downside_spread": round(adj.downside_spread, 4),
                "upside_spread": round(adj.upside_spread, 4),
                "confidence": adj.confidence,
                "drivers": adj.drivers,
                "analysis": adj.analysis,
            },
            "sample_multipliers": [round(s.median_multiplier, 3) for s in self.samples],
            "usage": self.usage,
            "scale": round(self.scale, 3),
        }
        if include_context and self.context is not None:
            d["brief"] = render_context(self.context)
        return d


def _r(a: np.ndarray) -> list[float]:
    return [round(float(x), 3) for x in a]


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def parse_adjustment(text: str) -> Adjustment | None:
    """Parse one model answer; None if it is not usable."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_OBJ.search(text)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    try:
        mm = float(obj["median_multiplier"])
        ds = float(obj.get("downside_spread", 1.0))
        us = float(obj.get("upside_spread", 1.0))
    except (KeyError, TypeError, ValueError):
        return None
    if not all(np.isfinite([mm, ds, us])):
        return None
    drivers = []
    for d in obj.get("drivers") or []:
        if isinstance(d, dict) and d.get("name"):
            try:
                eff = float(d.get("effect_pct", 0.0))
            except (TypeError, ValueError):
                eff = 0.0
            drivers.append({"name": str(d["name"])[:80], "effect_pct": round(eff, 1),
                            "evidence": str(d.get("evidence", ""))[:300]})
    conf = obj.get("confidence")
    return Adjustment(
        median_multiplier=float(np.clip(mm, *MULTIPLIER_RANGE)),
        downside_spread=float(np.clip(ds, *SPREAD_RANGE)),
        upside_spread=float(np.clip(us, *SPREAD_RANGE)),
        confidence=conf if conf in ("low", "medium", "high") else "medium",
        drivers=drivers[:6],
        analysis=str(obj.get("analysis", ""))[:1200],
    )


def combine(samples: list[Adjustment]) -> Adjustment:
    """Median of each number; drivers and wording from the most typical sample."""
    mm = float(np.median([s.median_multiplier for s in samples]))
    ds = float(np.median([s.downside_spread for s in samples]))
    us = float(np.median([s.upside_spread for s in samples]))
    rep = min(samples, key=lambda s: abs(np.log(s.median_multiplier) - np.log(mm)))
    confs = [s.confidence for s in samples]
    conf = max(set(confs), key=confs.count)
    return Adjustment(mm, ds, us, conf, rep.drivers, rep.analysis)


def apply_adjustment(base_q: np.ndarray, adj: Adjustment, levels: tuple[float, ...] = LEVELS) -> np.ndarray:
    """Scale the baseline median and stretch each side of the distribution."""
    q = np.asarray(base_q, dtype=float)
    mid = levels.index(0.5)
    med = q[mid]
    m = adj.median_multiplier
    out = np.empty_like(q)
    for i, p in enumerate(levels):
        if p < 0.5:
            out[i] = m * (med - adj.downside_spread * (med - q[i]))
        elif p > 0.5:
            out[i] = m * (med + adj.upside_spread * (q[i] - med))
        else:
            out[i] = m * med
    return np.maximum.accumulate(np.clip(out, 0.0, None))


def rule_adjustment(ctx: Context) -> Adjustment:
    """Classical uplift rule, no LLM: an ablation to measure what the model's judgment adds.

    Multiplies the clean historical effects of the target week's events, its
    promotion and a post-promotion dip, each shrunk toward 1 by n / (n + 1)
    for n past occurrences.
    """
    log_m = 0.0
    drivers = []

    def add(name: str, ratio: float | None, n: int) -> None:
        nonlocal log_m
        if ratio and n:
            w = n / (n + 1)
            log_m += w * float(np.log(ratio))
            drivers.append({"name": name, "effect_pct": round(100 * (ratio**w - 1), 1),
                            "evidence": f"median x{ratio} vs baseline over {n} past occurrence(s)"})

    for eh in ctx.event_history:
        usable = [o for o in eh["occurrences"] if o["vs_baseline"] is not None]
        clean = [o for o in usable if not o["also"]]
        add(f"{eh['event']} ({eh['timing']})", eh["median_vs_baseline"], len(clean) or len(usable))
    p = ctx.promo_history
    if p and any(e.startswith("Promotion") for e in ctx.target_events):
        usable = [r for r in p["recent"] if r["vs_baseline"] is not None]
        add("promotion", p["median_vs_baseline"], len([r for r in usable if not r["also"]]) or len(usable))
    elif p and ctx.horizon == 1 and ctx.recent and any(e.startswith("Promotion") for e in ctx.recent[-1]["events"]):
        add("week after a promotion", p["week_after_vs_baseline"], 2)
    m = float(np.clip(np.exp(log_m), *MULTIPLIER_RANGE))
    return Adjustment(m, 1.0, 1.0, "medium", drivers, "classical uplift rule")


def render_rule(adj: Adjustment) -> str:
    lines = [f"CLASSICAL UPLIFT MODEL SUGGESTS: median_multiplier {adj.median_multiplier:.2f}"]
    if adj.drivers:
        lines += [f"  {d['name']}: {d['effect_pct']:+.1f}% ({d['evidence']})" for d in adj.drivers]
    else:
        lines.append("  no event, promotion or post-promotion effect found")
    return "\n".join(lines)


class ForecastAgent:
    def __init__(self, llm: LLMClient | None, n_samples: int = 5, baseline_method: str = "ses"):
        self.llm = llm
        self.n_samples = n_samples
        self.baseline_method = baseline_method

    def build(self, series: Series, target_index: int, notes: str | None = None) -> tuple[Context, list[dict]]:
        ctx = build_context(series, target_index, notes=notes, baseline_method=self.baseline_method)
        brief = render_context(ctx) + "\n\n" + render_rule(rule_adjustment(ctx))
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": brief + "\n\nReturn the JSON adjustment now."},
        ]
        return ctx, messages

    async def forecast(self, series: Series, target_index: int, notes: str | None = None) -> AgentForecast:
        ctx, messages = self.build(series, target_index, notes)
        base = ctx.baseline
        fc = AgentForecast(
            sku_id=series.sku_id, title=series.title, target_index=target_index,
            target_week=ctx.target_week, horizon=ctx.horizon, baseline=base,
            quantiles=base.quantiles.copy(), adjustment=None, n_requested=self.n_samples,
            scale=ctx.scale, context=ctx,
        )
        if self.llm is None:
            fc.error = "LLM disabled"
            return fc
        try:
            comp = await self.llm.complete(messages, n=self.n_samples, schema=OUTPUT_SCHEMA)
        except LLMUnavailable as e:
            fc.error = f"LLM unavailable: {e}"
            return fc
        except Exception as e:  # the forecast still has the baseline; report what failed
            fc.error = f"{type(e).__name__}: {str(e)[:300]}"
            return fc
        fc.usage = {
            "model": comp.model, "prompt_tokens": comp.prompt_tokens,
            "completion_tokens": comp.completion_tokens, "latency_s": comp.latency_s, "cached": comp.cached,
        }
        samples = [a for a in (parse_adjustment(t) for t in comp.texts) if a is not None]
        fc.samples = samples
        if not samples:
            fc.error = "no parsable sample"
            return fc
        fc.adjustment = combine(samples)
        fc.quantiles = apply_adjustment(base.quantiles, fc.adjustment)
        fc.llm_ok = True
        return fc

    async def forecast_many(
        self, jobs: list[tuple[Series, int]], concurrency: int = 64, progress=None
    ) -> list[AgentForecast]:
        sem = asyncio.Semaphore(concurrency)
        done = 0

        async def one(s: Series, t: int) -> AgentForecast:
            nonlocal done
            async with sem:
                r = await self.forecast(s, t)
            done += 1
            if progress:
                progress(done, len(jobs), r)
            return r

        return await asyncio.gather(*(one(s, t) for s, t in jobs))
