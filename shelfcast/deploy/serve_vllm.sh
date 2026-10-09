#!/usr/bin/env bash
# Serve an open model with vLLM on an AMD Instinct GPU (ROCm), OpenAI-compatible API.
#
#   export SHELFCAST_LLM_API_KEY=$(openssl rand -hex 16)
#   bash deploy/serve_vllm.sh
#
# Uses the host's `vllm` if installed (AMD Developer Cloud vLLM image), otherwise the
# ROCm vLLM container. Listens on 127.0.0.1 by default: the dashboard runs on the same
# host, so only its port needs to be public.
set -euo pipefail

MODEL="${SHELFCAST_LLM_MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}"
API_KEY="${SHELFCAST_LLM_API_KEY:?set SHELFCAST_LLM_API_KEY to a random secret first}"
HOST="${VLLM_HOST:-127.0.0.1}"
PORT="${VLLM_PORT:-8000}"
MAX_LEN="${VLLM_MAX_MODEL_LEN:-16384}"
IMAGE="${VLLM_IMAGE:-rocm/vllm:latest}"
# AITER: AMD's optimised kernels for MI300-class GPUs. Set to 0 if a model misbehaves.
export VLLM_ROCM_USE_AITER="${VLLM_ROCM_USE_AITER:-1}"

ARGS=(
  --host "$HOST" --port "$PORT"
  --api-key "$API_KEY"
  --max-model-len "$MAX_LEN"
  --gpu-memory-utilization "${VLLM_GPU_MEM:-0.92}"
  --max-num-seqs "${VLLM_MAX_NUM_SEQS:-512}"
  --enable-prefix-caching
)

echo "Serving $MODEL on $HOST:$PORT (AITER=$VLLM_ROCM_USE_AITER)"
if command -v vllm >/dev/null 2>&1; then
  exec vllm serve "$MODEL" "${ARGS[@]}"
fi

exec docker run --rm --name shelfcast-vllm \
  --network=host --ipc=host --shm-size 16g \
  --device /dev/kfd --device /dev/dri --group-add video \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  -e HF_TOKEN -e VLLM_ROCM_USE_AITER \
  "$IMAGE" \
  vllm serve "$MODEL" "${ARGS[@]}"
