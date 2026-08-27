#!/usr/bin/env bash
# Merge LoRA (if needed) and export Q4_K_M + Q5_K_M GGUF for desktop llama.cpp.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CKPT="${1:-$ROOT/checkpoints/sft-1.5b}"
OUT="${2:-$ROOT/dist/gguf}"
mkdir -p "$OUT"
if ! command -v python >/dev/null; then
  echo "python required"
  exit 1
fi
CONVERTER="${LLAMA_CONVERT:-convert_hf_to_gguf.py}"
if [[ -f "$CKPT/adapter_config.json" ]]; then
  echo "Merge LoRA into a full HF dir first (peft merge_and_unload), then re-run."
fi
if command -v "$CONVERTER" >/dev/null 2>&1 || [[ -f "$CONVERTER" ]]; then
  python "$CONVERTER" "$CKPT" --outfile "$OUT/kde-ai-f16.gguf"
  if command -v llama-quantize >/dev/null; then
    llama-quantize "$OUT/kde-ai-f16.gguf" "$OUT/kde-ai-q4_k_m.gguf" Q4_K_M
    llama-quantize "$OUT/kde-ai-f16.gguf" "$OUT/kde-ai-q5_k_m.gguf" Q5_K_M
  else
    echo "Install llama-quantize to emit Q4_K_M / Q5_K_M"
  fi
else
  echo "Place convert_hf_to_gguf.py on PATH (llama.cpp) or set LLAMA_CONVERT"
  echo "Expected outputs: $OUT/kde-ai-q4_k_m.gguf $OUT/kde-ai-q5_k_m.gguf"
fi
