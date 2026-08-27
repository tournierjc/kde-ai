#!/usr/bin/env bash
set -euo pipefail
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/kde-ai/models"
mkdir -p "$DEST"
MODEL="${1:-Qwen/Qwen2.5-1.5B-Instruct-GGUF}"
FILE="${2:-qwen2.5-1.5b-instruct-q4_k_m.gguf}"
echo "Place a Q4_K_M GGUF at $DEST/$FILE"
echo "Example: huggingface-cli download $MODEL --include '*q4_k_m*' --local-dir $DEST"
if command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "$MODEL" --include '*Q4_K_M*' --include '*q4_k_m*' --local-dir "$DEST" || true
fi
ls -la "$DEST" || true
