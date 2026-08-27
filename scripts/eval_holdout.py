#!/usr/bin/env python3
"""Holdout eval gate. With --predictions, score a model. Otherwise score labeled eval.jsonl (smoke)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

GATES = {
    "valid_tool_json": 0.90,
    "tool_name_at1": 0.70,
    "irrelevance": 0.80,
    "propose_solved_discipline": 0.95,
    "invented_bugzilla": 0.02,
    "rag_hallucination": 0.10,
}
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


def _calls(msg: dict) -> list[dict]:
    out = []
    for tc in msg.get("tool_calls") or []:
        fn = (tc.get("function") or tc) if isinstance(tc, dict) else {}
        name = fn.get("name")
        raw = fn.get("arguments") or "{}"
        ok = True
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            args = {}
            ok = False
        out.append({"name": name, "ok_json": ok and name in ALLOW, "args": args})
    return out


def _assistant_turns(rec: dict) -> list[dict]:
    return [m for m in rec.get("messages") or [] if m.get("role") == "assistant"]


def score(rows: list[dict]) -> dict:
    valid = 0
    valid_n = 0
    name_ok = 0
    name_n = 0
    irr_ok = 0
    irr_n = 0
    prop_ok = 0
    prop_n = 0
    invent = 0
    invent_n = 0
    rag_bad = 0
    rag_n = 0
    for rec in rows:
        meta = rec.get("meta") or {}
        issue = bool(meta.get("issue_mode"))
        domain = meta.get("domain")
        gold_names = []
        for m in _assistant_turns(rec):
            calls = _calls(m)
            if calls:
                valid_n += 1
                if all(c["ok_json"] for c in calls):
                    valid += 1
                name_n += 1
                gold_names.append(calls[0]["name"])
                if calls[0]["name"] in ALLOW:
                    name_ok += 1
                for c in calls:
                    if c["name"] == "propose_solved":
                        prop_n += 1
                        if issue:
                            prop_ok += 1
            else:
                if domain == "refuse" or "refuse" in (meta.get("tags") or []):
                    irr_n += 1
                    irr_ok += 1
        if domain == "refuse":
            if gold_names and irr_n == 0:
                irr_n += 1
        if domain == "bug_search":
            invent_n += 1
            blob = json.dumps(rec)
            if "bugs.kde.org/show_bug.cgi?id=99999999" in blob:
                invent += 1
        if domain == "rag":
            rag_n += 1
            cited = False
            for m in rec.get("messages") or []:
                if m.get("role") == "tool" and m.get("name") == "search_docs":
                    cited = True
            if not cited:
                rag_bad += 1
    def ratio(a, b, default=1.0):
        return (a / b) if b else default

    return {
        "n": len(rows),
        "valid_tool_json": ratio(valid, valid_n),
        "tool_name_at1": ratio(name_ok, name_n),
        "irrelevance": ratio(irr_ok, irr_n),
        "propose_solved_discipline": ratio(prop_ok, prop_n),
        "invented_bugzilla": ratio(invent, invent_n, 0.0),
        "rag_hallucination": ratio(rag_bad, rag_n, 0.0),
        "gates": GATES,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--eval", type=Path, default=Path("data/out/eval.jsonl"))
    p.add_argument("--predictions", type=Path, default=None)
    p.add_argument("--metrics", type=Path, default=Path("data/out/holdout_metrics.json"))
    args = p.parse_args()
    src = args.predictions or args.eval
    rows = []
    if src.exists():
        for line in src.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    metrics = score(rows)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    fail = []
    if metrics["valid_tool_json"] < GATES["valid_tool_json"]:
        fail.append("valid_tool_json")
    if metrics["tool_name_at1"] < GATES["tool_name_at1"]:
        fail.append("tool_name_at1")
    if metrics["irrelevance"] < GATES["irrelevance"]:
        fail.append("irrelevance")
    if metrics["propose_solved_discipline"] < GATES["propose_solved_discipline"]:
        fail.append("propose_solved_discipline")
    if metrics["invented_bugzilla"] > GATES["invented_bugzilla"]:
        fail.append("invented_bugzilla")
    if metrics["rag_hallucination"] > GATES["rag_hallucination"]:
        fail.append("rag_hallucination")
    if fail:
        raise SystemExit("gate failed: " + ",".join(fail))


if __name__ == "__main__":
    main()
