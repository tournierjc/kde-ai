from __future__ import annotations

import json
import re

from kde_ai.paths import package_root
from kde_ai.undo import append_undo

_DISPLAY_HOWTO_RE = re.compile(
    r"how\s+(?:can|do|to|would|should)\s+.{0,80}"
    r"(?:change|set|configure|adjust).{0,48}"
    r"(?:resolution|scale|refresh|(?:monitor|display|screen)\s+resolution)|"
    r"where\s+(?:do|can|is|are)\s+.{0,48}"
    r"(?:display\s+scal|scaling\s+setting|resolution\s+setting|"
    r"(?:monitor|display)\s+resolution)|"
    r"(?:change|set|configure|adjust)\s+(?:my\s+)?(?:monitor|display|screen)\s+"
    r"(?:resolution|scale|refresh)",
    re.I,
)


def is_display_settings_howto(text: str) -> bool:
    return bool(_DISPLAY_HOWTO_RE.search(text or ""))


def kcm_matched(payload: dict | None) -> bool:
    if not payload or not payload.get("ok"):
        return False
    if payload.get("matched") is False:
        return False
    return bool(payload.get("kcm") or payload.get("command"))


def prefer_display_settings_reply(
    user_text: str,
    model_text: str,
    payload: dict | None,
) -> str:
    if not is_display_settings_howto(user_text):
        return model_text
    if not kcm_matched(payload):
        return model_text
    kcm = payload.get("kcm") or "kcm_kscreen"
    cmd = payload.get("command") or f"systemsettings {kcm}"
    return (
        f"Use System Settings Display ({kcm}): `{cmd}`. "
        "Pick the output and set Resolution (and refresh) there."
    )


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
