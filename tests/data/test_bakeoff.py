from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_daily_scenarios_file_exists():
    path = REPO / "data" / "eval" / "daily_scenarios.jsonl"
    assert path.exists()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 14
    for rec in rows:
        assert rec.get("checks"), rec["id"]
        assert rec["meta"]["source"] == "daily"


def test_bakeoff_scores_gold_as_perfect():
    from scripts.bakeoff_lib import compare_predictions, load_jsonl

    gold = load_jsonl(REPO / "data" / "eval" / "daily_scenarios.jsonl")
    metrics = compare_predictions(gold, gold)
    assert metrics["daily_substance"] == 1.0
    assert metrics["tool_match_at1"] == 1.0


def test_bakeoff_catches_bad_env_prediction():
    from scripts.bakeoff_lib import compare_predictions, load_jsonl

    gold = load_jsonl(REPO / "data" / "eval" / "daily_scenarios.jsonl")
    bad = [r for r in gold if r["id"] == "daily-env-want"][0]
    pred = {
        "id": bad["id"],
        "messages": bad["messages"][:2]
        + [
            {
                "role": "assistant",
                "content": "Use `export` (on the host; allowlisted). Do not run tools.",
            }
        ],
        "meta": bad["meta"],
    }
    metrics = compare_predictions([bad], [pred])
    assert metrics["daily_substance"] == 0.0
    assert metrics["failures_sample"]


@pytest.mark.parametrize("config", sorted((REPO / "training" / "configs").glob("sft_qwen*.yaml")))
def test_sft_configs_present(config):
    text = config.read_text(encoding="utf-8")
    assert "train_file: data/out/train.jsonl" in text
    assert "output_dir: checkpoints/" in text
