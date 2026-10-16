# ShelfCast backtest: m5-60

60 item-store series from the M5 (Walmart) competition data, aggregated to Walmart weeks, with calendar events, SNAP days and shelf prices.

- Forecasts: **1560** (60 series × last 26 weeks, 2015-11-21 to 2016-05-14), one week ahead
- Model: `Qwen/Qwen3-30B-A3B-Instruct-2507`, 5 samples per forecast; LLM answered 1560/1560
- Economics: margin 35% of price, leftover cost 25% of unit cost (newsvendor order at the critical ratio)
- Generated 2026-10-16T05:41:44+00:00

## All weeks

forecast value add **-0.6%** (scaled pinball, calibrated agent vs calibrated baseline; raw vs raw -1.0%); vs classical uplift rule **-0.2%**; inventory cost **+0.3%** vs calibrated baseline; ordering the cost-optimal quantile instead of the point forecast: inventory cost **-8.0%** ($7,714 when ordering the point forecast)

| Method | Scaled pinball ↓ | WAPE ↓ | Bias | 80% cov. | 90% cov. | Inventory cost ↓ | Fill rate | Stockout weeks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seasonal naive (same week last year) | 0.1699 | 54.5% | +15.9% | 70.9% | 83.0% | $11,820 | 89.2% | 28.4% |
| Statistical baseline (exp. smoothing) | 0.1017 | 29.0% | +0.2% | 76.7% | 87.1% | $7,014 | 92.0% | 29.4% |
| Baseline + calibration | 0.1023 | 29.0% | -2.1% | 80.2% | 90.6% | $7,096 | 91.6% | 30.2% |
| Classical uplift rule (no LLM, ablation) | 0.1025 | 29.3% | +0.7% | 77.1% | 86.4% | $7,073 | 92.1% | 29.4% |
| Uplift rule + calibration | 0.1027 | 29.3% | -0.7% | 80.7% | 90.3% | $7,115 | 92.0% | 29.5% |
| ShelfCast agent (raw) | 0.1027 | 29.5% | +0.8% | 76.6% | 86.4% | $7,088 | 92.0% | 29.5% |
| ShelfCast agent + calibration | 0.1029 | 29.4% | -1.3% | 81.0% | 90.1% | $7,118 | 92.1% | 28.9% |

## Event weeks (holidays, promotions, other calendar events)

forecast value add **-1.7%** (scaled pinball, calibrated agent vs calibrated baseline; raw vs raw -2.0%); vs classical uplift rule **-0.5%**; inventory cost **+1.4%** vs calibrated baseline; ordering the cost-optimal quantile instead of the point forecast: inventory cost **-7.9%** ($3,902 when ordering the point forecast)

| Method | Scaled pinball ↓ | WAPE ↓ | Bias | 80% cov. | 90% cov. | Inventory cost ↓ | Fill rate | Stockout weeks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seasonal naive (same week last year) | 0.1688 | 55.5% | +14.5% | 71.2% | 82.7% | $6,019 | 87.9% | 29.1% |
| Statistical baseline (exp. smoothing) | 0.1018 | 28.9% | +0.7% | 75.9% | 86.3% | $3,568 | 91.9% | 27.7% |
| Baseline + calibration | 0.1018 | 29.0% | -1.2% | 80.0% | 90.6% | $3,593 | 91.6% | 28.0% |
| Classical uplift rule (no LLM, ablation) | 0.1033 | 29.5% | +1.7% | 76.3% | 85.3% | $3,626 | 92.0% | 27.8% |
| Uplift rule + calibration | 0.1030 | 29.6% | +0.6% | 80.0% | 90.3% | $3,637 | 92.1% | 27.2% |
| ShelfCast agent (raw) | 0.1038 | 29.8% | +1.8% | 75.8% | 84.9% | $3,634 | 92.0% | 28.0% |
| ShelfCast agent + calibration | 0.1035 | 29.8% | +0.0% | 80.1% | 89.5% | $3,645 | 92.2% | 27.2% |

## Ordinary weeks

forecast value add **+0.6%** (scaled pinball, calibrated agent vs calibrated baseline; raw vs raw -0.2%); vs classical uplift rule **+0.1%**; inventory cost **-0.8%** vs calibrated baseline; ordering the cost-optimal quantile instead of the point forecast: inventory cost **-8.1%** ($3,813 when ordering the point forecast)

| Method | Scaled pinball ↓ | WAPE ↓ | Bias | 80% cov. | 90% cov. | Inventory cost ↓ | Fill rate | Stockout weeks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seasonal naive (same week last year) | 0.1710 | 53.5% | +17.3% | 70.6% | 83.3% | $5,800 | 90.4% | 27.7% |
| Statistical baseline (exp. smoothing) | 0.1015 | 29.1% | -0.3% | 77.6% | 87.9% | $3,447 | 92.1% | 31.0% |
| Baseline + calibration | 0.1028 | 29.0% | -2.9% | 80.4% | 90.5% | $3,503 | 91.6% | 32.4% |
| Classical uplift rule (no LLM, ablation) | 0.1016 | 29.1% | -0.2% | 78.0% | 87.6% | $3,446 | 92.1% | 31.0% |
| Uplift rule + calibration | 0.1023 | 29.0% | -2.0% | 81.4% | 90.3% | $3,478 | 91.8% | 31.8% |
| ShelfCast agent (raw) | 0.1017 | 29.2% | -0.3% | 77.4% | 87.9% | $3,453 | 92.1% | 31.1% |
| ShelfCast agent + calibration | 0.1022 | 29.0% | -2.6% | 81.8% | 90.6% | $3,473 | 92.1% | 30.6% |

## By category

| Category | Forecasts | FVA (pinball) | Inventory cost change |
|---|---:|---:|---:|
| FOODS | 520 | +1.6% | -2.1% |
| HOBBIES | 520 | -1.4% | +0.7% |
| HOUSEHOLD | 520 | -1.6% | +3.3% |

## Inference

- Prompt tokens 2,581,537, completion tokens 1,759,308
- Wall time 365.5s, mean request latency 14.777s, 2 responses served from cache

Scaled pinball is the mean quantile loss over 11 levels divided by the SKU's mean weekly demand (lower is better). FVA is the relative improvement of the calibrated agent over the calibrated statistical baseline, so calibration is never credited to the model. Calibrated variants are fit only on earlier weeks.
