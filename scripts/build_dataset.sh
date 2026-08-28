#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT"
python -m data.generators.write_gold
python -m data.generators.daily_scenarios
python -m data.validators.validate_jsonl --gold "$ROOT/data/gold"
if [[ "${1:-}" == "--gold-only" ]]; then
  echo "gold-only: not an MVP corpus"
  exit 0
fi
python -m data.generators.build_full --out "$ROOT/data/out"
python -m data.validators.validate_jsonl --gold "$ROOT/data/gold" --full "$ROOT/data/out"
echo "dataset ready in data/out"
