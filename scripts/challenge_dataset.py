#!/usr/bin/env python3
"""Validate corpus and score gold/daily suites before Spark training."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "data/out/challenge_report.json")
    args = p.parse_args()

    report: dict = {}

    _run([sys.executable, "-m", "data.validators.validate_jsonl", "--gold", "data/gold", "--full", "data/out"])
    _run([sys.executable, "-m", "pytest", "-q", "tests/data", "--tb=short"])

    from scripts.bakeoff_lib import compare_predictions, load_jsonl

    daily = ROOT / "data/eval/daily_scenarios.jsonl"
    eval_path = ROOT / "data/out/eval.jsonl"
    train_path = ROOT / "data/out/train.jsonl"

    daily_rows = load_jsonl(daily)
    eval_rows = load_jsonl(eval_path)
    train_rows = load_jsonl(train_path)

    daily_metrics = compare_predictions(daily_rows, daily_rows)
    eval_metrics = compare_predictions(eval_rows, eval_rows)

    from collections import Counter

    domains = Counter(r["meta"]["domain"] for r in train_rows)
    speech = 0
    for r in train_rows:
        for m in r.get("messages") or []:
            if m.get("role") != "user":
                continue
            q = (m.get("content") or "").lower()
            if any(x in q for x in ("i want to", "best way", "how do i", "how can i", "give me an example")):
                speech += 1
            break

    report = {
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "daily_rows": len(daily_rows),
        "train_domains": dict(domains),
        "train_speech_act_hits": speech,
        "daily_gold_substance": daily_metrics["daily_substance"],
        "eval_gold_substance": eval_metrics["daily_substance"],
        "eval_format": eval_metrics["format"],
        "ready_for_qwen35_4b": daily_metrics["daily_substance"] == 1.0 and len(train_rows) == 30000,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    if not report["ready_for_qwen35_4b"]:
        raise SystemExit("dataset challenge failed: not ready for Qwen3.5-4B training")


if __name__ == "__main__":
    main()
