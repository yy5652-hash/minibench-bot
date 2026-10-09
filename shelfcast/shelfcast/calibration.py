"""Quantile recalibration learned from past forecast errors.

For each quantile level p, find the shift (in units of the SKU's typical
weekly demand) that would have made exactly a share p of past outcomes fall
below the forecast, then apply that shift to new forecasts. This is split
conformal calibration done per level. In a backtest it is fit only on
forecasts whose outcomes were known before the week being forecast.
"""

from __future__ import annotations

import numpy as np

from . import LEVELS


class QuantileCalibrator:
    def __init__(self, levels: tuple[float, ...] = LEVELS, min_samples: int = 40):
        self.levels = levels
        self.min_samples = min_samples
        self.shifts = np.zeros(len(levels))
        self.n = 0

    @property
    def active(self) -> bool:
        return self.n >= self.min_samples

    def fit(self, quantiles: np.ndarray, actuals: np.ndarray, scales: np.ndarray) -> "QuantileCalibrator":
        """``quantiles`` is (n, levels); ``actuals`` and ``scales`` are (n,)."""
        q = np.asarray(quantiles, dtype=float)
        y = np.asarray(actuals, dtype=float)
        s = np.maximum(np.asarray(scales, dtype=float), 1e-9)
        self.n = len(y)
        if not self.active:
            self.shifts = np.zeros(len(self.levels))
            return self
        resid = (y[:, None] - q) / s[:, None]
        self.shifts = np.array([np.quantile(resid[:, i], p) for i, p in enumerate(self.levels)])
        return self

    def apply(self, quantiles: np.ndarray, scale: float) -> np.ndarray:
        q = np.asarray(quantiles, dtype=float)
        if not self.active:
            return q.copy()
        out = q + self.shifts * max(scale, 1e-9)
        return np.maximum.accumulate(np.clip(out, 0.0, None))

    def to_dict(self) -> dict:
        return {"n": self.n, "active": self.active,
                "shifts": [round(float(x), 4) for x in self.shifts]}
