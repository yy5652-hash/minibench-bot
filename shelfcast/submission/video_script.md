# Demo video script (about 3 minutes)

Record the dashboard while it runs **live** on the MI300X, so the latency and "answered on the GPU"
labels are real. Keep a terminal with `amd-smi monitor` (or `rocm-smi`) open for the AMD shot.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00 | Title slide | "Every week a store decides how many of each product to order. Too few: empty shelves. Too many: markdowns and waste. ShelfCast makes that call with an AI demand planner running on an AMD Instinct MI300X." |
| 0:15 | Dashboard, Canned Pumpkin, Thanksgiving week | "The grey bar is what a typical replenishment system forecasts: it extrapolates recent sales and has no idea Thanksgiving is coming." |
| 0:30 | Press "Forecast and decide" | "ShelfCast builds a brief: in both past Thanksgivings this product sold [x2.7] what that same baseline predicted. Five model samples come back in one request from vLLM on the MI300X, in [N] seconds." |
| 0:50 | Drivers, analysis, order tiles | "The model names each driver with its evidence, and the forecast becomes an order: [41] units instead of [21], the 68th percentile, because a lost sale costs more than a leftover can." |
| 1:10 | Open "The brief the model read" | "Nothing is hidden: this is exactly what the model saw." |
| 1:20 | Tortilla Chips, a past week, notes "Store closed Monday for renovation" | "Planners know things sales history can't. Type it in and the plan adjusts; a statistical model cannot read this." |
| 1:40 | Backtest section, M5 tab | "Does it pay off? We replayed 26 weeks of real Walmart sales, 60 products, every week forecast only from the past. Forecast value add [+X%]; in holiday and promotion weeks [+Y%]; inventory cost [−Z%]. And it beats a classical uplift rule using the same evidence by [W%]: that is the model's judgment." |
| 2:10 | Inference on AMD section, then the terminal with GPU utilisation | "One MI300X serves [N] forecasts a minute at [$X] per thousand. 192 GB of memory hold the model and hundreds of concurrent requests; the data never leaves the retailer's GPU." |
| 2:35 | Architecture slide | "Baseline, evidence, LLM judgment, calibration, newsvendor decision. Open model, open stack: ROCm and vLLM." |
| 2:50 | Closing slide with repo and demo links | "ShelfCast: from forecast to the right order, on AMD." |

Replace every `[...]` with the number shown on screen or in `results/*.md`.
