#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${GVAI_PRIVATE_RUNTIME_DIR:-$HOME/.cache/gvai-private-runtime}"
LLAMA_BUILD="b10809"
LLAMA_ARCHIVE="llama-b10809-bin-ubuntu-x64.tar.gz"
LLAMA_DIR="$CACHE_ROOT/llama.cpp/llama-$LLAMA_BUILD"
LLAMA_BIN="$LLAMA_DIR/llama-cli"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_BUILD/$LLAMA_ARCHIVE"

MODEL_DIR="$CACHE_ROOT/models"
MODEL_FILE="qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/$MODEL_FILE"
MODEL_SHA256="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"

mkdir -p "$LLAMA_DIR" "$MODEL_DIR"

if [[ ! -x "$LLAMA_BIN" ]]; then
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT
  echo "Downloading llama.cpp $LLAMA_BUILD..."
  python -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$LLAMA_URL" "$tmp_dir/$LLAMA_ARCHIVE"
  tar -xzf "$tmp_dir/$LLAMA_ARCHIVE" -C "$LLAMA_DIR"
  candidate="$(find "$LLAMA_DIR" -type f -name llama-cli -print -quit)"
  if [[ -z "$candidate" ]]; then
    echo "llama-cli not found after extraction." >&2
    exit 1
  fi
  chmod +x "$candidate"
  if [[ "$candidate" != "$LLAMA_BIN" ]]; then
    ln -sf "$candidate" "$LLAMA_BIN"
  fi
fi

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Downloading Qwen GGUF..."
  python -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$MODEL_URL" "$MODEL_PATH"
fi

actual_sha="$(sha256sum "$MODEL_PATH" | awk '{print $1}')"
if [[ "$actual_sha" != "$MODEL_SHA256" ]]; then
  echo "Model SHA256 mismatch." >&2
  echo "expected: $MODEL_SHA256" >&2
  echo "actual:   $actual_sha" >&2
  exit 1
fi

echo "Private runtime assets verified."
echo "llama-cli: $LLAMA_BIN"
echo "model:     $MODEL_PATH"
echo "sha256:    $actual_sha"
