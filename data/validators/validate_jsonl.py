"""Validate gold and/or full JSONL corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALLOW = {
    "system_info",
    "run_readonly_cmd",
    "search_bugzilla",
    "search_invent",
    "open_url",
    "kde_settings_hint",
    "search_docs",
    "propose_solved",
    "run_privileged_cmd",
    "pacman_mutate",
    "edit_config",
    "plasma_script",
    "screenshot_ocr",
}
SECRET = re.compile(r"(password|token|authorization|secret|api[_-]?key)\s*[:=]\s*\S+", re.I)
TRAIN_MIX = {
    "tools": 6000,
    "kde": 6000,
    "cachyos": 4500,
    "bug_search": 6000,
    "solve": 4500,
    "rag": 1500,
    "refuse": 1500,
}
EVAL_MIX = {
    "tools": 100,
    "kde": 100,
    "cachyos": 75,
    "bug_search": 100,
    "solve": 75,
    "rag": 25,
    "refuse": 25,
}
DPO_MIX = {
    "call-vs-no-call": 200,
    "propose-vs-not": 150,
    "privilege-cancel-vs-proceed": 150,
}


def _approx_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def _tool_names(msg: dict) -> list[str]:
    names = []
    for tc in msg.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or tc
        name = fn.get("name")
        if name:
            names.append(name)
    return names


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{i}: {exc}") from exc
    return rows


def validate_record(rec: dict, path: str, i: int, dpo: bool = False) -> None:
    if not rec.get("id"):
        raise SystemExit(f"{path}:{i}: missing id")
    msgs = rec.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 2 or len(msgs) > 16:
        raise SystemExit(f"{path}:{i}: messages 2-16 required")
    if msgs[0].get("role") != "system":
        raise SystemExit(f"{path}:{i}: first message must be system")
    meta = rec.get("meta") or {}
    for key in ("domain", "issue_mode", "skills", "os", "plasma", "source"):
        if key not in meta:
            raise SystemExit(f"{path}:{i}: meta.{key} missing")
    issue = bool(meta.get("issue_mode"))
    blob = json.dumps(rec)
    if SECRET.search(blob):
        raise SystemExit(f"{path}:{i}: password-like string")
    tok = sum(_approx_tokens(json.dumps(m, ensure_ascii=False)) for m in msgs)
    if tok > 4096:
        raise SystemExit(f"{path}:{i}: over 4096 approx tokens ({tok})")
    for m in msgs:
        for name in _tool_names(m):
            if name not in ALLOW:
                raise SystemExit(f"{path}:{i}: unknown tool {name}")
            if name == "propose_solved" and not issue:
                raise SystemExit(f"{path}:{i}: propose_solved without issue_mode")
    if dpo and ("chosen" not in rec or "rejected" not in rec):
        raise SystemExit(f"{path}:{i}: dpo needs chosen/rejected")


def _mix(rows: list[dict], expected: dict, path: str, tol: float = 0.02) -> None:
    c = Counter((r.get("meta") or {}).get("domain") for r in rows)
    for domain, n in expected.items():
        got = c.get(domain, 0)
        if abs(got - n) > max(1, int(n * tol)):
            raise SystemExit(f"{path}: mix {domain} got {got} want {n} ±{tol:.0%}")
    if sum(expected.values()) != len(rows):
        raise SystemExit(f"{path}: row count {len(rows)} want {sum(expected.values())}")


def validate_gold(gold_dir: Path) -> list[dict]:
    files = sorted(gold_dir.glob("*.jsonl"))
    if not files:
        raise SystemExit(f"no gold jsonl in {gold_dir}")
    rows = []
    for f in files:
        part = load_jsonl(f)
        for i, rec in enumerate(part, 1):
            validate_record(rec, str(f), i)
        rows.extend(part)
    if len(rows) < 400:
        raise SystemExit(f"gold has {len(rows)} rows, need ≥400")
    return rows


def validate_full(out: Path) -> None:
    train = load_jsonl(out / "train.jsonl")
    ev = load_jsonl(out / "eval.jsonl")
    dpo = load_jsonl(out / "dpo.jsonl")
    for i, rec in enumerate(train, 1):
        validate_record(rec, "train.jsonl", i)
    for i, rec in enumerate(ev, 1):
        validate_record(rec, "eval.jsonl", i)
    for i, rec in enumerate(dpo, 1):
        validate_record(rec, "dpo.jsonl", i, dpo=True)
    _mix(train, TRAIN_MIX, "train.jsonl")
    _mix(ev, EVAL_MIX, "eval.jsonl")
    expected_dpo = sum(DPO_MIX.values())
    if len(dpo) != expected_dpo:
        raise SystemExit(f"dpo.jsonl has {len(dpo)} want {expected_dpo}")
    kinds = Counter((r.get("meta") or {}).get("dpo_kind") for r in dpo)
    for kind, n in DPO_MIX.items():
        got = kinds.get(kind, 0)
        if got != n:
            raise SystemExit(f"dpo.jsonl: {kind} got {got} want {n}")
    sums_path = out / "SHA256SUMS"
    if not sums_path.exists():
        raise SystemExit("missing SHA256SUMS")
    listed = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h, name = line.split()
        listed[name] = h
    for name in ("train.jsonl", "eval.jsonl", "dpo.jsonl"):
        got = hashlib.sha256((out / name).read_bytes()).hexdigest()
        if listed.get(name) != got:
            raise SystemExit(f"SHA256 mismatch for {name}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gold", type=Path)
    p.add_argument("--full", type=Path)
    args = p.parse_args()
    if args.gold:
        n = len(validate_gold(args.gold))
        print(f"gold ok ({n} rows)")
    if args.full:
        validate_full(args.full)
        print("full corpus ok")
    if not args.gold and not args.full:
        raise SystemExit("pass --gold and/or --full")


if __name__ == "__main__":
    main()
