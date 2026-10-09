#!/usr/bin/env bash
# Everything after the model server is up, on the AMD GPU host:
# install, build datasets, benchmark, backtest (real M5 data + synthetic store),
# pre-run upcoming weeks for replay, fill the README results, start the dashboard.
#
#   export SHELFCAST_LLM_API_KEY=...        # same secret as serve_vllm.sh
#   SMOKE=1 bash deploy/run_all.sh          # first: a few minutes on a tiny subset
#   bash deploy/run_all.sh                  # then the full run (SKIP_M5=1 skips the real data)
#
# Model answers are cached in results/llm_cache.sqlite, so a re-run (or the full run
# after the smoke run) never pays twice for the same request.
set -euo pipefail
cd "$(dirname "$0")/.."

export SHELFCAST_LLM_BASE_URL="${SHELFCAST_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export SHELFCAST_LLM_MODEL="${SHELFCAST_LLM_MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}"
: "${SHELFCAST_LLM_API_KEY:?set SHELFCAST_LLM_API_KEY (the key vLLM was started with)}"
PORT="${PORT:-8080}"

if [ "${SMOKE:-0}" = "1" ]; then
  ORIGINS=2; M5_SERIES=6; BENCH_LEVELS="1,8"; OUT=results/smoke; M5_DATA=data/m5-smoke.json
  echo "== SMOKE run: tiny subset, results in $OUT"
else
  ORIGINS="${ORIGINS:-26}"; M5_SERIES="${M5_SERIES:-60}"; BENCH_LEVELS="${BENCH_LEVELS:-1,8,32,64,128}"
  OUT=results; M5_DATA=data/m5.json
fi
CACHE=results/llm_cache.sqlite

if [ ! -f .venv/bin/activate ]; then
  rm -rf .venv
  python3 -m venv .venv || { echo "python3 -m venv failed: install python3-venv (apt install python3-venv) and rerun"; exit 1; }
fi
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "== waiting for the model server at $SHELFCAST_LLM_BASE_URL (first start downloads the model)"
for _ in $(seq 1 360); do
  if python -m shelfcast check 2>/dev/null; then break; fi
  sleep 10
done
python -m shelfcast check

mkdir -p "$OUT"
if command -v amd-smi >/dev/null 2>&1; then amd-smi static --asic --vram > "$OUT/gpu_info.txt" 2>&1 || true
elif command -v rocm-smi >/dev/null 2>&1; then rocm-smi --showproductname --showmeminfo vram > "$OUT/gpu_info.txt" 2>&1 || true
fi

echo "== datasets"
# The synthetic store is committed so the replay cache matches it exactly; only build it if missing.
[ -f data/synthetic-store.json ] || python -m shelfcast data synthetic --out data/synthetic-store.json
if [ "${SKIP_M5:-0}" != "1" ]; then
  python -m shelfcast data m5 --n-series "$M5_SERIES" --out "$M5_DATA"
fi

echo "== inference benchmark"
python -m shelfcast bench --dataset data/synthetic-store.json --concurrency "$BENCH_LEVELS" --out-dir "$OUT" \
  || echo "!! benchmark failed; continuing with the backtests (rerun: python -m shelfcast bench)"

echo "== backtests"
if [ "${SKIP_M5:-0}" != "1" ]; then
  python -m shelfcast backtest --dataset "$M5_DATA" --origins "$ORIGINS" --cache "$CACHE" --out-dir "$OUT"
fi
python -m shelfcast backtest --dataset data/synthetic-store.json --origins "$ORIGINS" --cache "$CACHE" --out-dir "$OUT"

if [ "${SMOKE:-0}" = "1" ]; then
  python -m shelfcast summary --out-dir "$OUT"
  echo "== smoke run finished. Check the numbers above and the 'answered' counts, then run without SMOKE=1."
  exit 0
fi

echo "== pre-running the upcoming weeks so replay mode can show them later"
python -m shelfcast warm --dataset data/synthetic-store.json --cache "$CACHE"

echo "== filling the README results section"
python -m shelfcast summary --out-dir "$OUT" --readme README.md

echo "== dashboard on port $PORT"
exec python -m shelfcast serve --dataset data/synthetic-store.json --mode live --port "$PORT" --cache "$CACHE" --out-dir "$OUT"
