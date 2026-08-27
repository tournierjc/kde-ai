from __future__ import annotations

import json

from kde_ai.paths import package_root
from kde_ai.undo import append_undo


def handle(args: dict, ctx) -> dict:
    q = (args.get("query") or "").lower()
    data = json.loads((package_root() / "data" / "kcm_map.json").read_text(encoding="utf-8"))
    best = None
    for key, val in data.items():
        if key in q or q in key:
            best = val
            break
    if best is None:
        best = next(iter(data.values()))
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    return {"ok": True, **best}


SCHEMA = {
    "name": "kde_settings_hint",
    "description": "Map a symptom to a System Settings module",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}
