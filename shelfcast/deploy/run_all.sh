#!/usr/bin/env bash
# Everything after the model server is up, on the AMD GPU host:
# install, build datasets, benchmark, backtest (real M5 data + synthetic store),
# pre-run upcoming weeks for replay, then start the dashboard.
#
#   export SHELFCAST_LLM_API_KEY=...        # same secret as serve_vllm.sh
#   bash deploy/run_all.sh                  # SKIP_M5=1 to skip the real-data backtest
set -euo pipefail
cd "$(dirname "$0")/.."

export SHELFCAST_LLM_BASE_URL="${SHELFCAST_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export SHELFCAST_LLM_MODEL="${SHELFCAST_LLM_MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}"
: "${SHELFCAST_LLM_API_KEY:?set SHELFCAST_LLM_API_KEY (the key vLLM was started with)}"
ORIGINS="${ORIGINS:-26}"
M5_SERIES="${M5_SERIES:-60}"
PORT="${PORT:-8080}"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "== waiting for the model server at $SHELFCAST_LLM_BASE_URL"
for _ in $(seq 1 120); do
  if python -m shelfcast check; then break; fi
  sleep 10
done
python -m shelfcast check

mkdir -p results
if command -v amd-smi >/dev/null 2>&1; then amd-smi static --asic --vram > results/gpu_info.txt 2>&1 || true
elif command -v rocm-smi >/dev/null 2>&1; then rocm-smi --showproductname --showmeminfo vram > results/gpu_info.txt 2>&1 || true
fi

echo "== datasets"
python -m shelfcast data synthetic --out data/synthetic-store.json
if [ "${SKIP_M5:-0}" != "1" ]; then
  python -m shelfcast data m5 --n-series "$M5_SERIES" --out data/m5.json
fi

echo "== inference benchmark"
python -m shelfcast bench --dataset data/synthetic-store.json

echo "== backtests"
if [ "${SKIP_M5:-0}" != "1" ]; then
  python -m shelfcast backtest --dataset data/m5.json --origins "$ORIGINS"
fi
python -m shelfcast backtest --dataset data/synthetic-store.json --origins "$ORIGINS"

echo "== pre-running the upcoming weeks so replay mode can show them later"
python -m shelfcast warm --dataset data/synthetic-store.json

echo "== dashboard on port $PORT"
exec python -m shelfcast serve --dataset data/synthetic-store.json --mode live --port "$PORT"
