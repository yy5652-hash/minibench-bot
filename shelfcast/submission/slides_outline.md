# Slide deck outline (8 slides)

Judging criteria to hit: Application of Technology · Presentation · Business Value · Originality.

1. **ShelfCast.** One line: an LLM demand planner on AMD MI300X that turns forecasts into restocking
   orders. Track: Reinvent Commerce. Team, repo, demo URL.
2. **The problem (Business Value).** Ordering decisions every week, per SKU. Systems extrapolate
   sales and miss holidays, promotions, price moves and news. Cost of empty shelves vs overstock.
   Manual planner overrides: slow, inconsistent, unmeasured.
3. **What a planner sees.** Dashboard screenshot: Thanksgiving week, baseline vs ShelfCast range,
   order tiles, drivers with evidence.
4. **How it works (Originality).** Pipeline: baseline → evidence brief ("actual vs baseline" effects,
   clean vs overlapping events, uplift-model suggestion, notes) → 5 LLM samples with guided JSON →
   median → calibration → newsvendor order. Why multipliers and not raw numbers: anchored,
   explainable, ordered quantiles.
5. **Built on AMD (Application of Technology).** vLLM on ROCm, one MI300X, 192 GB HBM3. n-sampling
   with prefix caching, structured outputs, AITER kernels. Benchmark table: forecasts/min, tok/s,
   p95 latency, $ per 1,000 forecasts. Data stays on the retailer's GPU.
6. **Does it pay off? (Business Value).** Real Walmart M5 backtest: FVA vs baseline, event weeks vs
   ordinary weeks, inventory cost, fill rate, coverage. Ablation vs the classical uplift rule.
   Use only numbers from `results/backtest_m5-60.md`.
7. **Honest limits and next steps.** One-week horizon, single-period newsvendor, assumed economics.
   Next: multi-week with carry-over stock, store rollout, planner feedback loop.
8. **Close.** Demo URL, repo, "from forecast to the right order, on AMD".
