#!/usr/bin/env bash
# Merge SFT (+ optional DPO) LoRA and export Q4_K_M + Q5_K_M GGUF for desktop llama.cpp.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SFT="${SFT_ADAPTER:-$ROOT/checkpoints/sft-1.5b}"
DPO="${DPO_ADAPTER:-$ROOT/checkpoints/dpo-1.5b}"
MERGED="${MERGED_DIR:-$ROOT/checkpoints/merged-1.5b-dpo}"
OUT="${1:-$ROOT/dist/gguf}"
BASE="${BASE_MODEL:-Qwen/Qwen2.5-1.5B-Instruct}"
PYTHON="${PYTHON:-python}"
CONVERTER="${LLAMA_CONVERT:-convert_hf_to_gguf.py}"
QUANTIZE="${LLAMA_QUANTIZE:-llama-quantize}"

mkdir -p "$OUT" "$MERGED"

adapters=()
if [[ -f "$SFT/adapter_config.json" ]]; then
  adapters+=(--adapter "$SFT")
fi
if [[ -f "$DPO/adapter_config.json" ]]; then
  adapters+=(--adapter "$DPO")
fi
if [[ ${#adapters[@]} -eq 0 ]]; then
  echo "No LoRA adapters at $SFT or $DPO"
  exit 1
fi

"$PYTHON" "$ROOT/training/merge_lora.py" --base "$BASE" --out "$MERGED" "${adapters[@]}"

if [[ ! -f "$CONVERTER" ]] && ! command -v "$CONVERTER" >/dev/null 2>&1; then
  echo "Place convert_hf_to_gguf.py on PATH or set LLAMA_CONVERT"
  echo "Merged HF dir: $MERGED"
  exit 1
fi

"$PYTHON" "$CONVERTER" "$MERGED" --outtype f16 --outfile "$OUT/kde-ai-f16.gguf" --model-name kde-ai-1.5b-dpo

if ! command -v "$QUANTIZE" >/dev/null 2>&1 && [[ ! -x "$QUANTIZE" ]]; then
  echo "Set LLAMA_QUANTIZE to llama-quantize; f16 GGUF is at $OUT/kde-ai-f16.gguf"
  exit 1
fi
"$QUANTIZE" "$OUT/kde-ai-f16.gguf" "$OUT/kde-ai-q4_k_m.gguf" Q4_K_M
"$QUANTIZE" "$OUT/kde-ai-f16.gguf" "$OUT/kde-ai-q5_k_m.gguf" Q5_K_M
ls -lh "$OUT"/kde-ai-*.gguf
