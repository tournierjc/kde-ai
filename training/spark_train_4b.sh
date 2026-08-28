#!/usr/bin/env bash
# Start Qwen3.5-4B SFT (+ DPO) on Spark in tmux. Requires ~25 GiB free unified memory.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
stamp=$(date +%Y%m%d-%H%M)
PY="${PY:-/home/jct-spark/venvs/kde-ai/bin/python}"
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES=0
export HF_HOME="${HF_HOME:-/home/jct-spark/.cache/huggingface-kde-ai}"
export TRANSFORMERS_CACHE="$HF_HOME"
export TORCH_COMPILE_DISABLE=1
export TRITON_DISABLE=1
export TORCH_DISABLE_NATIVE_JIT=1

need_gb="${NEED_GB:-25}"
avail_kb=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
avail_gb=$((avail_kb / 1024 / 1024))
echo "MemAvailable: ${avail_gb} GiB (need ~${need_gb} GiB)"
if (( avail_gb < need_gb )); then
  echo "ERROR: not enough free memory. Stop vLLM/ComfyUI or other GPU jobs first." >&2
  exit 1
fi

mkdir -p checkpoints
for d in sft-4b dpo-4b; do
  if [[ -d "checkpoints/$d" && -f "checkpoints/$d/adapter_config.json" ]]; then
    mv "checkpoints/$d" "checkpoints/${d}-${stamp}"
    echo "archived checkpoints/${d}-${stamp}"
  fi
done
mkdir -p checkpoints/sft-4b checkpoints/dpo-4b

tmux has-session -t kde-ai-sft 2>/dev/null && tmux kill-session -t kde-ai-sft || true
tmux new-session -d -s kde-ai-sft -c "$ROOT" "
set -e
export TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=0 HF_HOME='$HF_HOME' TRANSFORMERS_CACHE='$HF_HOME'
export TORCH_COMPILE_DISABLE=1 TRITON_DISABLE=1 TORCH_DISABLE_NATIVE_JIT=1
PY='$PY'
echo \"=== SFT Qwen3.5-4B start \$(date -Is) ===\" | tee checkpoints/sft-4b/train.log
\$PY -u training/train_sft.py --config training/configs/sft_qwen35_4b.yaml 2>&1 | tee -a checkpoints/sft-4b/train.log
echo \"=== DPO start \$(date -Is) ===\" | tee checkpoints/dpo-4b/train.log
\$PY -u training/train_dpo.py --config training/configs/dpo_qwen35_4b.yaml 2>&1 | tee -a checkpoints/dpo-4b/train.log
echo \"=== DONE \$(date -Is) ===\" | tee -a checkpoints/dpo-4b/train.log
"
echo "tmux session kde-ai-sft started (Qwen3.5-4B SFT -> DPO)"
echo "  ssh spark 'tmux attach -t kde-ai-sft'"
echo "  ssh spark 'tail -f $ROOT/checkpoints/sft-4b/train.log'"
