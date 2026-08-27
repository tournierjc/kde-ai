from __future__ import annotations

import json


def _looks_like_tool_payload(text: str) -> bool:
    blob = (text or "").strip()
    if not blob.startswith("{"):
        return False
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    return "ok" in data and ("summary" in data or "gpus" in data or "monitors" in data)


def visible_chat_messages(messages: list[dict] | None) -> list[dict]:
    """User/assistant lines for the chat UI — skip tool JSON and empty tool-call stubs."""
    out: list[dict] = []
    for msg in messages or []:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "user":
            if content.strip():
                out.append({"role": "user", "content": content})
            continue
        if role != "assistant":
            continue
        if not content.strip() or _looks_like_tool_payload(content):
            continue
        out.append({"role": "assistant", "content": content})
    return out
