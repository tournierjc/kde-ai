from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLD = REPO / "data" / "gold"
TOOLS = {
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


def _rows():
    rows = []
    for f in sorted(GOLD.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _tags(rec):
    return set(rec.get("meta", {}).get("tags") or [])


def _tool_names(rec):
    names = set()
    for m in rec.get("messages") or []:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or tc
            if fn.get("name"):
                names.add(fn["name"])
        if m.get("name"):
            names.add(m["name"])
    return names


def test_gold_present_and_coverage():
    rows = _rows()
    assert len(rows) >= 400
    seen_tools = set()
    yes = no = cancel = priv = rag = refuse = narrow = 0
    for rec in rows:
        tags = _tags(rec)
        seen_tools |= {t.split(":", 1)[1] for t in tags if t.startswith("tool:")}
        seen_tools |= _tool_names(rec) & TOOLS
        if "issue_yes" in tags:
            yes += 1
        if "issue_no_undo" in tags:
            no += 1
        if "issue_cancel" in tags:
            cancel += 1
        if "privilege_cancel" in tags:
            priv += 1
        if "rag_cite" in tags:
            rag += 1
            blob = json.dumps(rec)
            assert "(" in blob and ")" in blob
        if "refuse" in tags:
            refuse += 1
        if "skill_narrow" in tags:
            narrow += 1
            assert len(rec["meta"]["skills"]) <= 2
    missing = TOOLS - seen_tools
    assert not missing, missing
    assert yes >= 10
    assert no >= 10
    assert cancel >= 5
    assert priv >= 5
    assert rag >= 5
    assert refuse >= 5
    assert narrow >= 3
