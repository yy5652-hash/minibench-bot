"""Statistical baselines: the "outside view" the agent starts from.

``ses`` is simple exponential smoothing with the smoothing weight picked on
in-sample one-step error, and quantiles taken from the empirical distribution
of its recent one-step errors. This is the kind of forecast most retail
replenishment systems run today. ``snaive`` (same week last year) is kept as a
second reference.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import LEVELS

_ALPHAS = np.round(np.arange(0.05, 0.96, 0.05), 2)


@dataclass
class BaselineForecast:
    method: str
    point: float
    quantiles: np.ndarray
    alpha: float | None = None


def _monotone_nonneg(q: np.ndarray) -> np.ndarray:
    return np.maximum.accumulate(np.clip(q, 0.0, None))


def _ses(y: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Fit SES on ``y``; return (alpha, final level, one-step residuals).

    All candidate smoothing weights run side by side, one pass over time.
    """
    a = _ALPHAS
    level = np.full(a.shape, y[0])
    res = np.empty((a.size, len(y) - 1))
    for t in range(1, len(y)):
        res[:, t - 1] = y[t] - level
        level = a * y[t] + (1 - a) * level
    best = int(np.argmin(np.sum(res[:, -104:] ** 2, axis=1)))
    return float(a[best]), float(level[best]), res[best]


def _from_residuals(point: float, res: np.ndarray, widen: float, levels: tuple[float, ...]) -> np.ndarray:
    if res.size >= 12:
        offsets = np.quantile(res, levels)
    else:
        sigma = max(float(np.std(res)) if res.size else 0.0, np.sqrt(max(point, 1.0)))
        from statistics import NormalDist

        offsets = np.array([NormalDist().inv_cdf(p) * sigma for p in levels])
    return _monotone_nonneg(point + widen * offsets)


def baseline_forecast(
    history: np.ndarray,
    horizon: int = 1,
    method: str = "ses",
    window: int = 52,
    levels: tuple[float, ...] = LEVELS,
) -> BaselineForecast:
    """Quantile forecast ``horizon`` weeks after the end of ``history``."""
    y = np.asarray(history, dtype=float)
    y = y[~np.isnan(y)][-156:]
    if y.size == 0:
        return BaselineForecast(method, 0.0, np.zeros(len(levels)))
    if y.size < 3:
        point = float(y.mean())
        return BaselineForecast(method, point, _from_residuals(point, np.array([]), 1.0, levels))

    if method == "snaive" and y.size > 52 + horizon:
        point = float(y[-52 + horizon - 1])
        res = y[52:] - y[:-52]
        return BaselineForecast(method, point, _from_residuals(point, res[-window:], 1.0, levels))

    alpha, level, res = _ses(y)
    widen = float(np.sqrt(1 + (horizon - 1) * alpha**2))
    return BaselineForecast("ses", level, _from_residuals(level, res[-window:], widen, levels), alpha)
