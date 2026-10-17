# ShelfCast

**Calibrated demand forecasts that become restocking decisions, planned by an open LLM on an AMD Instinct MI300X.**

AMD Developer Hackathon: ACT III · Track: **Reinvent Commerce** (demand and inventory planning)

**Live demo:** https://yy5652-hash.github.io/shelfcast/ (every answer in it was produced by the model on
one AMD Instinct MI300X; the page replays them and recomputes the order for any cost you set)

---

> Track brief: "If your product predicts demand, sales, or customer behaviour, explain how the prediction
> was calculated. Do not use a language model as the only forecasting method." ShelfCast's forecast is a
> statistical baseline plus a classical uplift model; the LLM is a judgment layer on top, measured against
> both, and every number it reads is shown in the dashboard.

## The problem

Every week a store manager decides how many units of each product to order. Order too few and
shoppers find an empty shelf; order too many and the surplus is marked down, spoiled or stuck in
the back room. Replenishment systems forecast by extrapolating recent sales, so they are blind to
exactly the weeks that matter most: holidays, promotions, price changes, and the local news a
manager hears about. Demand planners patch this by hand, one SKU at a time, and the patches are
slow, inconsistent and rarely checked against what actually sold.

## What ShelfCast does

```
 sales history ──► statistical baseline (exp. smoothing + empirical error quantiles)  "outside view"
                              │
 calendar, promotions, ──► evidence brief: how this SKU sold vs the baseline around the
 prices, planner notes        same event before, past promotion effects, last year, price moves,
                              plus a classical uplift model's suggestion
                              │
                              ▼
          open LLM on AMD MI300X (vLLM + ROCm), 5 samples in one request, JSON-schema output
          names the drivers ─► median multiplier + downside / upside spread
                              │  median of the samples
                              ▼
          calibrated demand distribution (5% … 95%), recalibrated on past errors
                              │
                              ▼
          order = demand quantile at  lost margin / (lost margin + leftover cost)   (newsvendor)
```

**What each layer is for, and how we know.** We ran the ablations before writing this page.

| Layer | What it adds | How it is measured | Measured on the MI300X run |
|---|---|---|---|
| Calibrated baseline + newsvendor order | Orders the cost-optimal quantile instead of the point forecast | Real inventory cost on M5 (Walmart) | **−8.0%** inventory cost on real Walmart sales |
| Noise-adjusted event and promotion evidence | Moves the forecast only when a past effect clears the SKU's own noise | Event weeks vs ordinary weeks; an uplift rule with no LLM | Synthetic store: **−8.9%** inventory cost, pinball **+4.0%** (event weeks +6.8%) |
| The LLM | Reads planner notes in free text, weighs overlapping or thin evidence, and explains the order | Weeks with a planner note: the baseline and the rule cannot read them | Noted weeks: **−21.9%** inventory cost, pinball **+19.4%** vs baseline, **+17.6%** vs the no-LLM rule |
| The guard | Holds the baseline when there is no evidence and no note | Share of model proposals it blocks | M5: blocked 92 of 389 proposed changes (24%); the model's net effect stays within 0.6% of the baseline |

An honest finding shaped this design: on anonymised Walmart items, where no promotion data exists, a
language model that is free to adjust makes the forecast worse. It treats routine calendar entries as
events and reads one past week as a pattern. So the model is not the forecaster here. It is the judgment
layer on top of a statistical forecast, tied to evidence by a guard, and its own contribution is
measured separately from everything else.

The model behaves like a careful demand planner adjusting a system forecast: it starts from the
baseline, names each driver with its evidence ("Thanksgiving: x2.7 vs baseline in both past
years"), shrinks thin evidence toward no change, widens the uncertain side, and reads free-text
planner notes that no statistical model can use ("a competitor opens across the street this week").
The output is an order quantity, its expected cost, and a short explanation a store manager can
check.

### Why it runs on AMD

* **One GPU holds the whole planner.** An MI300X has 192 GB of HBM3, enough to serve a capable open
  model with plenty of room left for the KV cache, so hundreds of SKU forecasts run concurrently.
* **Several opinions for the price of one prompt.** Each forecast asks for 5 samples in a single
  request: vLLM prefills the brief once and decodes the samples together, and the median of the
  samples is robust to one sample going astray.
* **Guaranteed structure.** vLLM's guided decoding enforces the JSON schema, so no second "parser"
  model call is needed.
* **Sales data stays in-house.** The model is open weights on the retailer's own GPU; no sales history
  is sent to a third-party API.

`python -m shelfcast bench` measures throughput, latency and the GPU cost per 1,000 forecasts on the
serving host, and the dashboard shows those numbers next to the GPU it ran on.

## Evidence it works

`python -m shelfcast backtest` replays the last 26 weeks for every SKU. Each week is forecast only from
the weeks before it, then scored on accuracy and on money:

* **Forecast quality:** scaled pinball loss over 11 quantiles, 80% and 90% interval coverage, WAPE, bias.
* **Forecast value add (FVA):** the improvement over the statistical baseline, the metric demand
  planning teams use to judge manual overrides. Both sides are calibrated the same way, so
  calibration is never credited to the model; raw-vs-raw is reported alongside.
* **Inventory outcome:** order with the newsvendor rule and count the real cost of leftovers and
  lost sales against what actually sold, plus fill rate and stockout weeks.
* **Ablation:** a classical uplift rule that multiplies the same evidence with no LLM. The gap
  between it and ShelfCast is what the model's judgment adds.
* **Decision layer alone:** ordering the baseline's cost-optimal quantile against ordering its point
  forecast, with no model involved.
* **Planner-notes experiment:** a variant of the synthetic store where about 8% of weeks carry a
  free-text note with no number in it ("supplier warns this week's delivery will be short"). Only the
  model can read it, so that segment isolates the model's own contribution.
* **Event weeks vs ordinary weeks**, reported separately.

Two datasets:

* **M5 (Walmart), real sales:** 60 item-store series, stratified across food, household and hobbies,
  with the real event calendar, SNAP benefit days and shelf prices. Series are chosen on the weeks
  before the backtest window, so the window plays no part in picking them. Items are anonymised, so the
  model cannot lean on product knowledge from pretraining.
* **Synthetic store:** 20 named products with US holidays, planned promotions, price changes,
  post-promotion dips and unannounced shocks. It powers the interactive demo, including upcoming
  weeks such as Thanksgiving 2026. It is generated (`shelfcast/data.py`) and labelled as such.

### Results

<!-- RESULTS:START -->
**Real Walmart sales (M5)**: 1,560 one-week-ahead forecasts, 60 SKUs, 2015-11-21 to 2016-05-14; model `Qwen/Qwen3-30B-A3B-Instruct-2507`, 5 samples each, answered 1560/1560.

| (all three calibrated on earlier weeks) | Statistical baseline | Uplift rule, no LLM | ShelfCast |
|---|---:|---:|---:|
| Scaled pinball loss ↓, all weeks | 0.1023 | 0.1027 | 0.1029 |
| Scaled pinball loss ↓, event weeks | 0.1018 | 0.1030 | 0.1035 |
| Scaled pinball loss ↓, ordinary weeks | 0.1028 | 0.1023 | 0.1022 |
| 90% interval coverage (target 90%) | 90.6% | 90.3% | 90.1% |
| Inventory cost ↓ (leftovers + lost margin) | $7,096 | $7,115 | $7,118 |
| Fill rate | 91.6% | 92.0% | 92.1% |

Forecast value add vs the calibrated baseline: **-0.6%** (event weeks -1.7%, ordinary weeks +0.6%); vs the uplift rule: **-0.2%**; inventory cost **+0.3%**.

**Synthetic store**: 520 one-week-ahead forecasts, 20 SKUs, 2026-04-13 to 2026-10-05; model `Qwen/Qwen3-30B-A3B-Instruct-2507`, 5 samples each, answered 520/520.

| (all three calibrated on earlier weeks) | Statistical baseline | Uplift rule, no LLM | ShelfCast |
|---|---:|---:|---:|
| Scaled pinball loss ↓, all weeks | 0.1145 | 0.1116 | 0.1099 |
| Scaled pinball loss ↓, event weeks | 0.1472 | 0.1387 | 0.1372 |
| Scaled pinball loss ↓, ordinary weeks | 0.0952 | 0.0957 | 0.0938 |
| 90% interval coverage (target 90%) | 88.5% | 88.3% | 88.3% |
| Inventory cost ↓ (leftovers + lost margin) | $16,804 | $15,591 | $15,314 |
| Fill rate | 90.5% | 91.6% | 92.1% |

Forecast value add vs the calibrated baseline: **+4.0%** (event weeks +6.8%, ordinary weeks +1.5%); vs the uplift rule: **+1.5%**; inventory cost **-8.9%**.

**Synthetic store with planner notes**: 520 one-week-ahead forecasts, 20 SKUs, 2026-04-13 to 2026-10-05; model `Qwen/Qwen3-30B-A3B-Instruct-2507`, 5 samples each, answered 520/520.

| (all three calibrated on earlier weeks) | Statistical baseline | Uplift rule, no LLM | ShelfCast |
|---|---:|---:|---:|
| Scaled pinball loss ↓, all weeks | 0.1106 | 0.1174 | 0.1103 |
| Scaled pinball loss ↓, event weeks | 0.1347 | 0.1458 | 0.1372 |
| Scaled pinball loss ↓, ordinary weeks | 0.0952 | 0.0992 | 0.0931 |
| 90% interval coverage (target 90%) | 88.8% | 88.8% | 89.0% |
| Inventory cost ↓ (leftovers + lost margin) | $15,017 | $13,970 | $13,211 |
| Fill rate | 91.6% | 92.5% | 93.3% |

Forecast value add vs the calibrated baseline: **+0.3%** (event weeks -1.9%, ordinary weeks +2.2%); vs the uplift rule: **+6.0%**; inventory cost **-12.0%**.

In the weeks where the planner left a note: forecast value add **+19.4%**, vs the uplift rule **+17.6%**, inventory cost **-21.9%**.

**Inference on one AMD Instinct MI300X** (`Qwen/Qwen3-30B-A3B-Instruct-2507`, vLLM, 5 samples per forecast): 256 forecasts/min at 128 concurrent requests, 4,722 output tokens/s, p95 latency 47.8s, $0.194 per 1,000 forecasts at $2.99/GPU-hour; 100.0% of samples parsed as valid JSON.
<!-- RESULTS:END -->

Full reports written by the run:

| File | Contents |
|---|---|
| `results/backtest_m5-60.md` | real-data backtest: all weeks, event weeks, ordinary weeks, by category |
| `results/backtest_synthetic-store.md` | the same on the synthetic store |
| `results/backtest_synthetic-store-notes.md` | the planner-notes experiment |
| `results/bench.md` | forecasts/min, output tokens/s, p50/p95 latency, $ per 1,000 forecasts |
| `results/gpu_info.txt` | `amd-smi` / `rocm-smi` output from the serving host |

## Run it on an MI300X

The results above were produced on 16 Oct 2026 on one **AMD Instinct MI300X** VM from Hot Aisle (ROCm 7.2,
the `rocm/vllm` container). The whole run, from boot to the last forecast, took about 35 minutes of GPU
time, $1.49 at $2.99/hour. `results/amd_smi_under_load.txt` is `amd-smi` captured during the benchmark.
Any MI300X host works, for example AMD Developer Cloud:

1. Create a GPU VM with **1× MI300X** and a ROCm image (the vLLM quick-start image works).
2. On the droplet:

   ```bash
   git clone https://github.com/yy5652-hash/shelfcast && cd shelfcast
   export SHELFCAST_LLM_API_KEY=$(openssl rand -hex 16)
   nohup bash deploy/serve_vllm.sh > vllm.log 2>&1 &     # downloads the model on first start
   bash deploy/run_all.sh                                 # benchmark, backtests, then the dashboard
   ```

3. Open `http://<droplet-ip>:8080` (allow port 8080 in the firewall). vLLM itself stays on
   127.0.0.1 behind an API key.

Model choice: the default is `Qwen/Qwen3-30B-A3B-Instruct-2507`, a mixture-of-experts model with
about 3B active parameters per token, which keeps throughput high. Any chat model vLLM serves on
ROCm works: set `SHELFCAST_LLM_MODEL` for both scripts (for example a 70B dense model in bf16, which
still fits on one MI300X).

Every model answer is cached in `results/llm_cache.sqlite`. Copy `results/` off the droplet and
destroy it when you are done: a powered-off GPU droplet is still billed. The dashboard keeps working
without a model:

```bash
python -m shelfcast serve --dataset data/synthetic-store.json --mode replay
```

Replay mode serves the cached answers (all backtest weeks and the pre-run upcoming weeks) and falls
back to the statistical baseline, clearly labelled, for anything never run. To keep a public demo URL
up during judging, commit `results/` and deploy the included `Dockerfile` to any small CPU host, for
example a Hugging Face Docker Space (it listens on port 7860), or export a static copy with
`python submission/build_static_demo.py --live` on the GPU host (that is how the live demo above was made).

## Develop locally (no GPU)

```bash
cd shelfcast
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                      # 57 tests; the model is replaced by fakes and a mock vLLM server
```

Point `SHELFCAST_LLM_BASE_URL` at any OpenAI-compatible endpoint to try the full loop.

## Command line

```
python -m shelfcast data synthetic|m5     build a dataset (m5 downloads the Walmart data)
python -m shelfcast check                 ping the model endpoint
python -m shelfcast forecast --sku BAK-001 [--week N] [--notes "..."] [--brief]
python -m shelfcast backtest --dataset data/m5.json [--origins 26] [--offline]
python -m shelfcast bench [--concurrency 1,8,32,64,128,256,512] [--max-requests 1024] [--price-per-hour 2.99]
python -m shelfcast warm                  pre-run upcoming weeks for replay mode
python -m shelfcast serve [--mode live|replay] [--port 8080]
```

## Code map

| Path | What it does |
|---|---|
| `shelfcast/data.py` | weekly series model, synthetic store, M5 loader |
| `shelfcast/baseline.py` | exponential smoothing with empirical error quantiles; seasonal naive |
| `shelfcast/features.py` | the evidence brief: effects measured as actual / baseline, clean vs overlapping occurrences |
| `shelfcast/agent.py` | prompt, JSON schema, parsing, sample median, adjustment, classical uplift rule |
| `shelfcast/llm.py` | OpenAI-compatible client for vLLM: n samples, guided JSON, cache, offline mode |
| `shelfcast/calibration.py` | per-quantile recalibration from past errors (split-conformal style) |
| `shelfcast/decision.py` | newsvendor order quantity, realised and expected cost |
| `shelfcast/backtest.py`, `metrics.py`, `report.py` | rolling backtest, scores, markdown reports |
| `shelfcast/bench.py` | throughput and latency benchmark against the live endpoint |
| `shelfcast/server.py`, `web/index.html` | the dashboard (FastAPI + one HTML page) |
| `deploy/` | `serve_vllm.sh` (vLLM on ROCm), `run_all.sh` (everything else) |

## Design notes and limits

* One SKU's weekly sales are noisy, and on real Walmart data a past "holiday effect" seen two or
  three times mostly fails to repeat. So every effect is shrunk toward no change unless it clears the
  SKU's own week-to-week noise (a positive-part James-Stein weight), and where a pooled series exists
  (all items of the department in that store) the effect is measured there instead, where it is far
  less noisy. Without this, a mechanical uplift rule was 24% worse than the plain baseline on M5;
  with it, the rule is level with the baseline on M5 and still better on event weeks in the synthetic store.
* Effects are measured as **actual ÷ what the baseline predicted at the time**, not against "nearby
  weeks". That is the multiplier the agent applies, and it stays honest when the baseline has
  already caught up with a multi-week season. An event that overlapped a promotion is shown but kept
  out of the median when a clean occurrence exists.
* The backtest is one week ahead and treats each week as a single-period newsvendor problem
  (no carry-over stock), a standard simplification for perishables and fast movers.
* The economics (margin, leftover cost) are adjustable assumptions, not each SKU's real figures.
* Calibration is fit across SKUs in scaled units, on earlier weeks only.

## Origin

ShelfCast grew out of this repository's Metaculus forecasting bot: the same superforecasting habits
(start from the base rate, weigh the status quo, name the scenarios, aggregate several samples, stay
calibrated) applied to the forecast a retailer acts on every week.
