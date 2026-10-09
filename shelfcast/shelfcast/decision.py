"""From a demand distribution to an order: the newsvendor rule.

Ordering one more unit costs ``overage`` if it is left over (markdown, waste,
holding) and saves ``underage`` if it would otherwise be a lost sale (lost
margin). The cost-minimising order is the demand quantile at the critical
ratio underage / (underage + overage).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import LEVELS


@dataclass
class Economics:
    unit_price: float
    margin_pct: float = 0.35
    overage_pct: float = 0.25

    @property
    def unit_cost(self) -> float:
        return self.unit_price * (1.0 - self.margin_pct)

    @property
    def underage(self) -> float:
        """Margin lost per unit of unmet demand."""
        return self.unit_price * self.margin_pct

    @property
    def overage(self) -> float:
        """Cost per leftover unit (markdown, spoilage, holding), as a share of unit cost."""
        return self.unit_cost * self.overage_pct

    @property
    def critical_ratio(self) -> float:
        return self.underage / (self.underage + self.overage)


def quantile_at(q: np.ndarray, p: float, levels: tuple[float, ...] = LEVELS) -> float:
    """Piecewise-linear inverse CDF, extrapolated linearly beyond the outer levels."""
    lv = np.asarray(levels)
    q = np.asarray(q, dtype=float)
    if p <= lv[0]:
        slope = (q[1] - q[0]) / (lv[1] - lv[0])
        return max(0.0, float(q[0] - slope * (lv[0] - p)))
    if p >= lv[-1]:
        slope = (q[-1] - q[-2]) / (lv[-1] - lv[-2])
        return float(q[-1] + slope * (p - lv[-1]))
    return float(np.interp(p, lv, q))


def order_quantity(q: np.ndarray, econ: Economics, levels: tuple[float, ...] = LEVELS) -> float:
    return float(np.round(quantile_at(q, econ.critical_ratio, levels)))


def realized_cost(order: float, demand: float, econ: Economics) -> float:
    return econ.overage * max(order - demand, 0.0) + econ.underage * max(demand - order, 0.0)


def expected_cost(q: np.ndarray, order: float, econ: Economics, levels: tuple[float, ...] = LEVELS,
                  grid: int = 199) -> float:
    """Expected newsvendor cost when demand follows the forecast distribution."""
    us = (np.arange(grid) + 0.5) / grid
    draws = np.array([quantile_at(q, u, levels) for u in us])
    return float(np.mean(econ.overage * np.maximum(order - draws, 0) + econ.underage * np.maximum(draws - order, 0)))
