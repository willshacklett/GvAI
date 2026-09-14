#!/usr/bin/env bash
set -euo pipefail

if [[ "${GVAI_PRIVATE_BUILD_MODE:-0}" =~ ^(1|true|yes|on)$ ]]; then
  echo "GVAI Private Build Mode enabled."
  privacy/bootstrap_local_runtime.sh

  CACHE_ROOT="${GVAI_PRIVATE_RUNTIME_DIR:-$HOME/.cache/gvai-private-runtime}"
  export GVAI_PRIVATE_MODEL_COMMAND="${GVAI_PRIVATE_MODEL_COMMAND:-python privacy/local_model_worker.py}"
  export GVAI_LOCAL_MODEL_COMMAND="${GVAI_LOCAL_MODEL_COMMAND:-python privacy/llama_cpp_engine.py}"
  export GVAI_LLAMA_CPP_BIN="${GVAI_LLAMA_CPP_BIN:-$CACHE_ROOT/llama.cpp/llama-b10809/llama-cli}"
  export GVAI_LOCAL_MODEL_PATH="${GVAI_LOCAL_MODEL_PATH:-$CACHE_ROOT/models/qwen2.5-0.5b-instruct-q4_k_m.gguf}"
  export GVAI_LOCAL_MODEL_NAME="${GVAI_LOCAL_MODEL_NAME:-qwen2.5-0.5b-instruct-q4_k_m}"
  export GVAI_LOCAL_MAX_TOKENS="${GVAI_LOCAL_MAX_TOKENS:-128}"
  export GVAI_LOCAL_CONTEXT_SIZE="${GVAI_LOCAL_CONTEXT_SIZE:-2048}"
  export GVAI_LOCAL_TEMPERATURE="${GVAI_LOCAL_TEMPERATURE:-0.2}"
  export GVAI_LOCAL_MODEL_TIMEOUT="${GVAI_LOCAL_MODEL_TIMEOUT:-180}"
fi

exec python -m gunicorn -b 0.0.0.0:${PORT:-8080} gvai.api_service:app
