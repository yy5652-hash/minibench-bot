# ShelfCast

**Calibrated demand forecasts that become restocking decisions, planned by an open LLM on an AMD Instinct MI300X.**

AMD Developer Hackathon: ACT III · Track: **Reinvent Commerce** (demand and inventory planning)

---

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
  planning teams use to judge manual overrides.
* **Inventory outcome:** order with the newsvendor rule and count the real cost of leftovers and
  lost sales against what actually sold, plus fill rate and stockout weeks.
* **Ablation:** a classical uplift rule that multiplies the same evidence with no LLM. The gap
  between it and ShelfCast is what the model's judgment adds.
* **Event weeks vs ordinary weeks**, reported separately.

Two datasets:

* **M5 (Walmart), real sales:** 60 item-store series, stratified across food, household and hobbies,
  with the real event calendar, SNAP benefit days and shelf prices. Items are anonymised, so the
  model cannot lean on product knowledge from pretraining.
* **Synthetic store:** 20 named products with US holidays, planned promotions, price changes,
  post-promotion dips and unannounced shocks. It powers the interactive demo, including upcoming
  weeks such as Thanksgiving 2026. It is generated (`shelfcast/data.py`) and labelled as such.

### Results

<!-- Replace this block with the headline numbers from results/*.md after the GPU run. -->
Run `deploy/run_all.sh` on the GPU host; it writes:

| File | Contents |
|---|---|
| `results/backtest_m5-60.md` | real-data backtest: all weeks, event weeks, ordinary weeks, by category |
| `results/backtest_synthetic-store.md` | the same on the synthetic store |
| `results/bench.md` | forecasts/min, output tokens/s, p50/p95 latency, $ per 1,000 forecasts |
| `results/gpu_info.txt` | `amd-smi` / `rocm-smi` output from the serving host |

## Run it on AMD Developer Cloud

1. Create a GPU droplet with **1× MI300X** and a ROCm image (the vLLM quick-start image works).
2. On the droplet:

   ```bash
   git clone <this repo> && cd <repo>/shelfcast
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

Every model answer is cached in `results/llm_cache.sqlite`. After the GPU is switched off, the
dashboard keeps working without a model:

```bash
python -m shelfcast serve --dataset data/synthetic-store.json --mode replay
```

Replay mode serves the cached answers (all backtest weeks and the pre-run upcoming weeks) and falls
back to the statistical baseline, clearly labelled, for anything never run. To keep a public demo URL
up during judging, commit `results/` and deploy the included `Dockerfile` to any small CPU host, for
example a Hugging Face Docker Space (it listens on port 7860).

## Develop locally (no GPU)

```bash
cd shelfcast
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                      # 46 tests; the model is replaced by fakes and a mock vLLM server
```

Point `SHELFCAST_LLM_BASE_URL` at any OpenAI-compatible endpoint to try the full loop.

## Command line

```
python -m shelfcast data synthetic|m5     build a dataset (m5 downloads the Walmart data)
python -m shelfcast check                 ping the model endpoint
python -m shelfcast forecast --sku BAK-001 [--week N] [--notes "..."] [--brief]
python -m shelfcast backtest --dataset data/m5.json [--origins 26] [--offline]
python -m shelfcast bench [--concurrency 1,8,32,64,128] [--price-per-hour 1.99]
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
