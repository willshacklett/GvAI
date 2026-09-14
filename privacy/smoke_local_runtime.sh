#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${GVAI_PRIVATE_RUNTIME_DIR:-$HOME/.cache/gvai-private-runtime}"

export GVAI_LOCAL_MODEL_COMMAND="python privacy/llama_cpp_engine.py"
export GVAI_LLAMA_CPP_BIN="$CACHE_ROOT/llama.cpp/llama-b10809/llama-cli"
export GVAI_LOCAL_MODEL_PATH="$CACHE_ROOT/models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
export GVAI_LOCAL_MODEL_NAME="qwen2.5-0.5b-instruct-q4_k_m"
export GVAI_LOCAL_MAX_TOKENS="${GVAI_LOCAL_MAX_TOKENS:-64}"
export GVAI_LOCAL_CONTEXT_SIZE="${GVAI_LOCAL_CONTEXT_SIZE:-2048}"
export GVAI_LOCAL_TEMPERATURE="${GVAI_LOCAL_TEMPERATURE:-0.2}"
export GVAI_LOCAL_MODEL_TIMEOUT="${GVAI_LOCAL_MODEL_TIMEOUT:-180}"

printf '%s\n' '{"system_prompt":"You are GVAI running privately.","user_content":"Reply in one short sentence confirming this response was generated locally."}' \
  | privacy/run_network_sandbox.sh \
    python privacy/local_model_worker.py
