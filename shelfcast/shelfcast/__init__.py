"""ShelfCast: calibrated demand forecasts that become restocking decisions.

An open LLM served by vLLM on an AMD Instinct MI300X reads the context a
statistical model cannot (holidays, promotions, price moves, planner notes),
adjusts a statistical baseline like an experienced demand planner, and the
result is turned into an order quantity with the newsvendor rule.
"""

# Quantile levels used everywhere: baseline, agent, calibration and decisions.
LEVELS: tuple[float, ...] = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

__version__ = "0.1.0"
