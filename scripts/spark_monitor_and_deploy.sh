#!/usr/bin/env bash
# Poll Spark training, export GGUF when done, deploy to local desktop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPARK="${SPARK_HOST:-spark}"
SPARK_ROOT="${SPARK_ROOT:-/home/jct-spark/kde-ai}"
LOCAL_MODEL_DIR="${KDE_AI_MODEL_DIR:-$HOME/.local/share/kde-ai/models}"
GGUF_NAME="${KDE_AI_GGUF_NAME:-kde-ai-qwen35-4b-q4_k_m.gguf}"
POLL_S="${POLL_S:-300}"
LOG="$ROOT/checkpoints/monitor.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }

wait_for_done() {
  while true; do
    if ssh "$SPARK" "
      test -f '$SPARK_ROOT/checkpoints/sft-4b/adapter_config.json' &&
      test -f '$SPARK_ROOT/checkpoints/dpo-4b/adapter_config.json' &&
      grep -q '=== DONE' '$SPARK_ROOT/checkpoints/dpo-4b/train.log' 2>/dev/null &&
      ! pgrep -f 'train_sft.py.*sft_qwen35_4b' >/dev/null &&
      ! pgrep -f 'train_dpo.py.*dpo_qwen35_4b' >/dev/null
    "; then
      log "training finished"
      return 0
    fi
    if ssh "$SPARK" "grep -q 'Traceback' '$SPARK_ROOT/checkpoints/sft-4b/train.log' 2>/dev/null && ! pgrep -f 'train_sft.py.*sft_qwen35_4b' >/dev/null"; then
      log "SFT failed — check Spark logs"
      return 1
    fi
    if ssh "$SPARK" "grep -q 'Traceback' '$SPARK_ROOT/checkpoints/dpo-4b/train.log' 2>/dev/null && ! pgrep -f 'train_dpo.py.*dpo_qwen35_4b' >/dev/null"; then
      log "DPO failed — check Spark logs"
      return 1
    fi
    sft_tail=$(ssh "$SPARK" "tail -1 '$SPARK_ROOT/checkpoints/sft-4b/train.log' 2>/dev/null" || true)
    dpo_tail=$(ssh "$SPARK" "tail -1 '$SPARK_ROOT/checkpoints/dpo-4b/train.log' 2>/dev/null" || true)
    log "waiting… sft: ${sft_tail:-(none)} | dpo: ${dpo_tail:-(none)}"
    sleep "$POLL_S"
  done
}

export_on_spark() {
  log "exporting GGUF on Spark"
  ssh "$SPARK" "cd '$SPARK_ROOT' && \
    SFT_ADAPTER=checkpoints/sft-4b DPO_ADAPTER=checkpoints/dpo-4b \
    BASE_MODEL=Qwen/Qwen3.5-4B MERGED_DIR=checkpoints/merged-4b-dpo \
    PYTHON=/home/jct-spark/venvs/kde-ai/bin/python \
    TORCH_DISABLE_NATIVE_JIT=1 TORCH_COMPILE_DISABLE=1 \
    ./training/export_gguf.sh dist/gguf-4b" 2>&1 | tee -a "$LOG"
}

deploy_local() {
  mkdir -p "$LOCAL_MODEL_DIR"
  log "copying Q4_K_M to $LOCAL_MODEL_DIR/$GGUF_NAME"
  scp "$SPARK:$SPARK_ROOT/dist/gguf-4b/kde-ai-q4_k_m.gguf" "$LOCAL_MODEL_DIR/$GGUF_NAME"
  CFG="$HOME/.config/kde-ai/config.toml"
  if [[ -f "$CFG" ]]; then
  if grep -q '^gguf' "$CFG" 2>/dev/null || grep -q '^\[llm\]' "$CFG"; then
    sed -i "s|gguf = .*|gguf = \"$LOCAL_MODEL_DIR/$GGUF_NAME\"|" "$CFG" || true
  fi
  fi
  log "restarting kde-ai-agent"
  systemctl --user restart kde-ai-agent.service 2>/dev/null || true
  log "deployed $LOCAL_MODEL_DIR/$GGUF_NAME"
}

main() {
  log "monitor start (poll ${POLL_S}s)"
  wait_for_done
  export_on_spark
  deploy_local
  log "complete"
}

main "$@"
