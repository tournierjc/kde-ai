#!/usr/bin/env bash
# Smoke the acceptance matrix pieces that do not need a GPU, GGUF, or live Plasma.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT"
python -m data.generators.write_gold
python -m data.validators.validate_jsonl --gold "$ROOT/data/gold"
if [[ -f "$ROOT/data/out/eval.jsonl" ]]; then
  python "$ROOT/scripts/eval_holdout.py" --eval "$ROOT/data/out/eval.jsonl" --metrics "$ROOT/data/out/holdout_metrics.json"
fi
python -m pytest -q
echo "e2e smoke ok (see docs/qa-matrix.md for GPU/SSH/Flatpak/manual items)"
