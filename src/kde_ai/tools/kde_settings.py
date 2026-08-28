from __future__ import annotations

import json
import re

from kde_ai.paths import package_root
from kde_ai.undo import append_undo


def _match_kcm(query: str, data: dict) -> dict | None:
    q = (query or "").lower().strip()
    if not q:
        return None
    for key, val in data.items():
        if re.search(rf"\b{re.escape(key)}\b", q):
            return val
    return None


def handle(args: dict, ctx) -> dict:
    q = (args.get("query") or "").lower()
    data = json.loads((package_root() / "data" / "kcm_map.json").read_text(encoding="utf-8"))
    best = _match_kcm(q, data)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    if best is None:
        return {"ok": True, "matched": False, "kcm": None, "command": None, "doc": None}
    return {"ok": True, "matched": True, **best}


SCHEMA = {
    "name": "kde_settings_hint",
    "description": "Map a symptom to a System Settings module",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}
