from __future__ import annotations

from pathlib import Path

import pytest

from data.validators.validate_jsonl import (
    EVAL_MIX,
    TRAIN_MIX,
    load_jsonl,
    validate_full,
    validate_gold,
)

REPO = Path(__file__).resolve().parents[2]


def test_gold_validates():
    rows = validate_gold(REPO / "data" / "gold")
    assert len(rows) >= 400


def test_full_mix_if_present():
    out = REPO / "data" / "out"
    if not (out / "train.jsonl").exists():
        pytest.skip("full corpus not built")
    validate_full(out)
    train = load_jsonl(out / "train.jsonl")
    from collections import Counter

    c = Counter(r["meta"]["domain"] for r in train)
    for k, n in TRAIN_MIX.items():
        assert c[k] == n
    ev = load_jsonl(out / "eval.jsonl")
    c2 = Counter(r["meta"]["domain"] for r in ev)
    for k, n in EVAL_MIX.items():
        assert c2[k] == n
    assert len(load_jsonl(out / "dpo.jsonl")) == 200
