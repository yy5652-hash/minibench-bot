# lablab.ai submission form: ready-to-paste text

Fill the `[...]` placeholders after the GPU run. Use only numbers that appear in `results/*.md`.

## Project title

ShelfCast: an LLM demand planner on AMD MI300X that turns forecasts into restocking orders

## Short description

ShelfCast reads what sales history can't (holidays, promotions, price moves, planner notes), adjusts a
statistical forecast like an expert demand planner, and turns it into a cost-optimal order. It runs on
an open model served by vLLM on an AMD Instinct MI300X.

## Track

Reinvent Commerce: demand and inventory planning

## Technology tags

AMD Instinct MI300X, AMD Developer Cloud, ROCm, vLLM, Qwen3, open-weight LLM, structured outputs,
probabilistic forecasting, conformal calibration, newsvendor optimisation, FastAPI, Python

## Long description

**Problem.** Every week, store managers decide how many units of each product to order. Replenishment
systems forecast by extrapolating recent sales, so they miss exactly the weeks that matter: holidays,
promotions, price changes and local news. Planners patch this by hand, one SKU at a time,
inconsistently and without checking the result. The cost shows up as empty shelves (lost margin) and
overstock (markdowns and waste).

**Solution.** ShelfCast is an AI demand planner. For each product and week it:
1. computes a statistical baseline (exponential smoothing with empirical error quantiles);
2. builds an evidence brief: how this SKU sold, relative to that same baseline, around the same event
   in past years, its past promotion effects, last year's same week, price moves, a classical uplift
   model's suggestion and any planner notes;
3. asks an open LLM, served by vLLM on an AMD Instinct MI300X, for 5 independent judgments in one
   request, each naming its drivers and returning a multiplier and two uncertainty spreads under a
   JSON schema enforced by guided decoding;
4. combines the samples by their median, recalibrates the resulting distribution on past errors, and
   orders the demand quantile that minimises expected cost: lost margin against leftover cost
   (the newsvendor rule).

The store manager sees the order, its expected cost, the drivers with their evidence, and the
forecast range next to the baseline's.

**Evidence.** A rolling 26-week backtest on real Walmart sales (M5, 60 item-store series) and on a
synthetic store scores every forecast on accuracy (pinball loss, interval coverage) and on money
(the actual cost of leftovers and lost sales when ordering with each forecast). It includes an
ablation: a classical uplift rule that uses the same evidence with no LLM.
Results on real data: forecast value add [+X.X%] vs the statistical baseline, [+X.X%] in event weeks,
inventory cost [−X.X%], 90% interval coverage [XX%], and [+X.X%] vs the classical uplift rule.

**Why AMD.** The MI300X's 192 GB of HBM3 holds a capable open model with ample KV cache, so hundreds
of SKU forecasts run concurrently on one GPU: [N] forecasts per minute at [$X.XX] per 1,000 forecasts.
Prefix caching and n-sampling mean each brief is prefilled once for all 5 samples. The model is
open-weight and runs on the retailer's own GPU, so sales data never leaves the company.

**What's next.** Multi-week horizons with carry-over stock, store-level rollout via the same
OpenAI-compatible endpoint, and planner feedback as training data.

## Links

- GitHub: [public repo URL]
- Demo: [dashboard URL: live on the MI300X during the event, replay host afterwards]
- Video: [URL]
- Slides: [URL]
