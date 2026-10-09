"""Forecast scores: pinball loss, interval coverage, WAPE and bias."""

from __future__ import annotations

import numpy as np

from . import LEVELS


def pinball(y: float, q: np.ndarray, levels: tuple[float, ...] = LEVELS) -> float:
    """Mean pinball (quantile) loss over the levels; approximates CRPS."""
    q = np.asarray(q, dtype=float)
    lv = np.asarray(levels)
    diff = y - q
    return float(np.mean(np.maximum(lv * diff, (lv - 1) * diff)))


def summarize(records: list[dict], key: str, levels: tuple[float, ...] = LEVELS) -> dict:
    """Aggregate scores for the quantiles stored under ``record[key]``.

    Each record needs ``actual``, ``scale`` and the quantile list under ``key``.
    """
    lv = list(levels)
    i05, i10, i50, i90, i95 = (lv.index(p) for p in (0.05, 0.1, 0.5, 0.9, 0.95))
    y = np.array([r["actual"] for r in records], dtype=float)
    s = np.array([r["scale"] for r in records], dtype=float)
    q = np.array([r[key] for r in records], dtype=float)
    if len(y) == 0:
        return {}
    pl = np.array([pinball(y[k], q[k], levels) for k in range(len(y))])
    med = q[:, i50]
    return {
        "n": int(len(y)),
        "scaled_pinball": round(float(np.mean(pl / s)), 4),
        "wape_median": round(float(np.sum(np.abs(y - med)) / max(np.sum(y), 1e-9)), 4),
        "bias_median_pct": round(float(100 * (np.sum(med) - np.sum(y)) / max(np.sum(y), 1e-9)), 2),
        "coverage_80": round(float(np.mean((y >= q[:, i10]) & (y <= q[:, i90]))), 4),
        "coverage_90": round(float(np.mean((y >= q[:, i05]) & (y <= q[:, i95]))), 4),
    }
