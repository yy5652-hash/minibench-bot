# Results

Written by the GPU run (`deploy/run_all.sh`), committed as evidence:

- `backtest_<dataset>.json` / `.md`: every forecast with the model's drivers and reasoning, and the scores
- `bench.json` / `.md`: throughput, latency and cost per 1,000 forecasts on the serving GPU
- `gpu_info.txt`: `amd-smi` / `rocm-smi` output from the serving host
- `llm_cache.sqlite`: every model answer, keyed by request; replay mode serves the dashboard from it
