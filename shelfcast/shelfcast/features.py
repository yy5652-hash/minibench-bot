"""Evidence the agent reads: recent sales, last year, past event and promotion effects.

Every past effect is measured the same way: actual units divided by what the
statistical baseline predicted for that week from the weeks before it. That is
exactly the multiplier the agent applies, it stays honest when the baseline has
already caught up with a trend or a multi-week season, and it lets effects from
different years be compared. Medians use "clean" occurrences, where no other
event or promotion fell in the same week, whenever one exists.

Only weeks before the forecast origin are used, plus what is planned for the
target week (events and shelf price), so backtests do not leak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from . import LEVELS
from .baseline import BaselineForecast, baseline_forecast
from .data import Series, event_key

MID = LEVELS.index(0.5)


@dataclass
class Context:
    sku_id: str
    title: str
    category: str
    store: str
    target_index: int
    target_week: str
    horizon: int
    target_events: list[str]
    target_price: float | None
    ref_price: float | None
    price_change_pct: float | None
    recent: list[dict]
    last_year: list[dict]
    event_history: list[dict]
    promo_history: dict | None
    stats: dict
    baseline: BaselineForecast
    notes: str | None = None
    history: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def scale(self) -> float:
        """Typical weekly demand, used to make errors comparable across SKUs."""
        return max(float(self.stats.get("mean_52") or 0.0), 1.0)


def _keys(events: list[str]) -> list[str]:
    """Event keys that can move demand (SNAP counts are shown, not keyed)."""
    return [k for k in (event_key(e) for e in events) if k != "SNAP"]


def _vs_baseline(series: Series, j: int) -> float | None:
    """Actual units in week ``j`` over the baseline median forecast made just before it."""
    cache = series.__dict__.setdefault("_baseline_median_cache", {})
    if j not in cache:
        hist = series.demand[:j]
        cache[j] = float(baseline_forecast(hist).quantiles[MID]) if np.sum(~np.isnan(hist)) >= 8 else None
    b = cache[j]
    y = series.demand[j]
    if b is None or np.isnan(y):
        return None
    return round(float(y) / max(b, 0.5), 2)


def _median_effect(rows: list[dict]) -> tuple[float | None, bool]:
    """Median ratio over clean rows if any, else over all rows; flag if confounded."""
    clean = [r["vs_baseline"] for r in rows if r["vs_baseline"] is not None and not r["also"]]
    every = [r["vs_baseline"] for r in rows if r["vs_baseline"] is not None]
    if clean:
        return round(float(np.median(clean)), 2), False
    if every:
        return round(float(np.median(every)), 2), True
    return None, False


def build_context(
    series: Series,
    target_index: int,
    notes: str | None = None,
    baseline_method: str = "ses",
    recent_weeks: int = 12,
) -> Context:
    if not 0 < target_index < series.n_weeks:
        raise IndexError(f"target_index {target_index} out of range for {series.sku_id}")
    known_end = min(target_index, series.last_known_index() + 1)
    if known_end <= 0:
        raise ValueError(f"{series.sku_id}: no sales history before week {target_index}")
    horizon = target_index - known_end + 1
    demand = series.demand
    hist = demand[:known_end]
    base = baseline_forecast(hist, horizon=horizon, method=baseline_method)

    recent = []
    for j in range(max(0, known_end - recent_weeks), known_end):
        recent.append({
            "week": series.week_starts[j],
            "units": None if np.isnan(demand[j]) else float(demand[j]),
            "price": None if np.isnan(series.price[j]) else float(series.price[j]),
            "events": series.events[j],
        })

    last_year = []
    for j in (target_index - 53, target_index - 52, target_index - 51):
        if 0 <= j < known_end:
            last_year.append({
                "week": series.week_starts[j],
                "units": float(demand[j]),
                "vs_baseline": _vs_baseline(series, j),
                "events": series.events[j],
                "is_same_week": j == target_index - 52,
            })

    target_keys = list(dict.fromkeys(k for k in _keys(series.events[target_index]) if k != "Promotion"))
    next_keys: list[str] = []
    if target_index + 1 < series.n_weeks:
        next_keys = [k for k in dict.fromkeys(_keys(series.events[target_index + 1]))
                     if k != "Promotion" and k not in target_keys]

    event_history = []
    for k in target_keys:
        rows = []
        for j in range(known_end):
            ks = _keys(series.events[j])
            if k in ks:
                rows.append({"week": series.week_starts[j], "units": float(demand[j]),
                             "vs_baseline": _vs_baseline(series, j),
                             "also": [e for e in series.events[j] if event_key(e) not in (k, "SNAP")]})
        med, confounded = _median_effect(rows)
        event_history.append({"event": k, "timing": "event week", "occurrences": rows[-4:],
                              "median_vs_baseline": med, "confounded": confounded})
    # Shoppers stock up ahead of some events. Only weeks with no event of their own measure that cleanly.
    for k in next_keys:
        rows = []
        for j in range(known_end - 1):
            if k in _keys(series.events[j + 1]) and not _keys(series.events[j]):
                rows.append({"week": series.week_starts[j], "units": float(demand[j]),
                             "vs_baseline": _vs_baseline(series, j), "also": []})
        med, _ = _median_effect(rows)
        event_history.append({"event": k, "timing": "week before the event", "occurrences": rows[-4:],
                              "median_vs_baseline": med, "confounded": False})

    promo_history = None
    promo_rows = []
    after_rows = []
    for j in range(known_end):
        promo = next((e for e in series.events[j] if e.startswith("Promotion")), None)
        if promo is None:
            continue
        promo_rows.append({"week": series.week_starts[j], "promotion": promo, "units": float(demand[j]),
                           "vs_baseline": _vs_baseline(series, j),
                           "also": [e for e in series.events[j] if event_key(e) not in ("Promotion", "SNAP")]})
        if j + 1 < known_end and not _keys(series.events[j + 1]):
            after_rows.append({"vs_baseline": _vs_baseline(series, j + 1), "also": []})
    if promo_rows:
        med, confounded = _median_effect(promo_rows)
        after, _ = _median_effect(after_rows)
        promo_history = {"count": len(promo_rows), "median_vs_baseline": med, "confounded": confounded,
                         "week_after_vs_baseline": after, "recent": promo_rows[-5:]}

    prices = series.price[:known_end]
    ordinary_prices = [
        series.price[j] for j in range(max(0, known_end - 8), known_end)
        if not np.isnan(series.price[j]) and not any(e.startswith("Promotion") for e in series.events[j])
    ]
    ref_price = float(np.median(ordinary_prices)) if ordinary_prices else (
        float(np.nanmedian(prices[-8:])) if np.any(~np.isnan(prices[-8:])) else None)
    tp = series.price[target_index]
    target_price = None if np.isnan(tp) else float(tp)
    price_change = None
    if target_price is not None and ref_price:
        price_change = round(100.0 * (target_price / ref_price - 1.0), 1)

    h = hist[~np.isnan(hist)]
    mean_13 = float(h[-13:].mean()) if h.size else 0.0
    mean_52 = float(h[-52:].mean()) if h.size else 0.0
    prev_13 = float(h[-26:-13].mean()) if h.size >= 26 else None
    stats = {
        "weeks_of_history": int(h.size),
        "mean_13": round(mean_13, 1),
        "mean_52": round(mean_52, 1),
        "trend_13_vs_prior_13_pct": None if not prev_13 else round(100 * (mean_13 / prev_13 - 1), 1),
        "cv_13": round(float(h[-13:].std() / mean_13), 2) if mean_13 > 0 else None,
    }

    return Context(
        sku_id=series.sku_id,
        title=series.title,
        category=series.category,
        store=series.store,
        target_index=target_index,
        target_week=series.week_starts[target_index],
        horizon=horizon,
        target_events=series.events[target_index],
        target_price=target_price,
        ref_price=ref_price,
        price_change_pct=price_change,
        recent=recent,
        last_year=last_year,
        event_history=event_history,
        promo_history=promo_history,
        stats=stats,
        baseline=base,
        notes=notes,
        history=hist,
    )


def _fmt_units(v: float | None) -> str:
    return "n/a" if v is None else f"{v:,.0f}"


def _fmt_ratio(v: float | None) -> str:
    return "n/a" if v is None else f"x{v}"


def _also(r: dict) -> str:
    return f" [same week: {'; '.join(r['also'])}]" if r.get("also") else ""


def render_context(ctx: Context) -> str:
    """Compact plain-text brief for the LLM."""
    week_end = date.fromisoformat(ctx.target_week).toordinal() + 6
    ahead = ("next week" if ctx.horizon == 1
             else f"{ctx.horizon} weeks after the last week with sales data")
    lines = [
        f"PRODUCT: {ctx.title} | category {ctx.category} | {ctx.store}",
        f"TARGET WEEK: {ctx.target_week} to {date.fromordinal(week_end).isoformat()} ({ahead})",
        "",
        "KNOWN PLAN FOR THE TARGET WEEK:",
        "  events: " + ("; ".join(ctx.target_events) if ctx.target_events else "none"),
    ]
    if ctx.target_price is not None:
        chg = "" if ctx.price_change_pct is None else f" ({ctx.price_change_pct:+.1f}% vs regular price {ctx.ref_price:.2f})"
        lines.append(f"  shelf price: {ctx.target_price:.2f}{chg}")
    if ctx.notes:
        lines.append(f"  planner notes: {ctx.notes.strip()}")

    qs = dict(zip(LEVELS, ctx.baseline.quantiles))
    lines += [
        "",
        "STATISTICAL BASELINE (exponential smoothing of recent sales; it ignores events, promotions and prices):",
        f"  median {qs[0.5]:,.1f} | 5%-95%: {qs[0.05]:,.1f} - {qs[0.95]:,.1f} | 10%-90%: {qs[0.1]:,.1f} - {qs[0.9]:,.1f}",
        "",
        "In the evidence below, 'vs baseline' = actual units / what this same baseline predicted for that week.",
        "It is the multiplier that would have been right, so it maps directly onto median_multiplier.",
        "",
        "HISTORY STATS: " + ", ".join(f"{k}={v}" for k, v in ctx.stats.items()),
        "",
        "RECENT WEEKS (week start | units | price | events):",
    ]
    for r in ctx.recent:
        price = "n/a" if r["price"] is None else f"{r['price']:.2f}"
        lines.append(f"  {r['week']} | {_fmt_units(r['units'])} | {price} | {'; '.join(r['events']) or '-'}")

    if ctx.last_year:
        lines += ["", "SAME TIME LAST YEAR (week start | units | vs baseline | events):"]
        for r in ctx.last_year:
            tag = "  <- same week last year" if r["is_same_week"] else ""
            lines.append(f"  {r['week']} | {_fmt_units(r['units'])} | {_fmt_ratio(r['vs_baseline'])} | "
                         f"{'; '.join(r['events']) or '-'}{tag}")

    if ctx.event_history:
        lines += ["", "PAST EFFECT OF THE EVENTS AROUND THE TARGET WEEK:"]
        for eh in ctx.event_history:
            label = f"{eh['event']} [{eh['timing']}]"
            if not eh["occurrences"]:
                why = "no earlier occurrence" if eh["timing"] == "event week" else "no clean earlier occurrence"
                lines.append(f"  {label}: {why} in the history")
                continue
            note = " (every occurrence overlapped another event or promotion)" if eh["confounded"] else ""
            lines.append(f"  {label}: median {_fmt_ratio(eh['median_vs_baseline'])} vs baseline{note}")
            for o in eh["occurrences"]:
                lines.append(f"    {o['week']}: {o['units']:,.0f} units, {_fmt_ratio(o['vs_baseline'])}{_also(o)}")

    if ctx.promo_history:
        p = ctx.promo_history
        note = " (all overlapped holidays)" if p["confounded"] else ""
        lines += ["", f"PAST PROMOTIONS: {p['count']} total, median {_fmt_ratio(p['median_vs_baseline'])} vs "
                      f"baseline{note}; the following ordinary week: median "
                      f"{_fmt_ratio(p['week_after_vs_baseline'])}"]
        for r in p["recent"]:
            lines.append(f"  {r['week']} | {r['promotion']} | {r['units']:,.0f} units, "
                         f"{_fmt_ratio(r['vs_baseline'])}{_also(r)}")
    return "\n".join(lines)
