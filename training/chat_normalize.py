"""Normalize chat messages for Qwen3.x chat templates."""

from __future__ import annotations

import json
from typing import Any


def _parse_arguments(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": value}
    return value


def normalize_message(msg: dict) -> dict:
    out = dict(msg)
    if out.get("role") == "assistant" and out.get("tool_calls"):
        calls = []
        for tc in out["tool_calls"]:
            if not isinstance(tc, dict):
                calls.append(tc)
                continue
            call = dict(tc)
            fn = call.get("function")
            if isinstance(fn, dict) and "arguments" in fn:
                fn = dict(fn)
                fn["arguments"] = _parse_arguments(fn["arguments"])
                call["function"] = fn
            calls.append(call)
        out["tool_calls"] = calls
    return out


def normalize_messages(messages: list[dict]) -> list[dict]:
    return [normalize_message(m) for m in messages]


def normalize_record(record: dict) -> dict:
    out = dict(record)
    if "messages" in out:
        out["messages"] = normalize_messages(out["messages"])
    if "prompt" in out and isinstance(out["prompt"], list):
        out["prompt"] = normalize_messages(out["prompt"])
    for key in ("chosen", "rejected"):
        val = out.get(key)
        if isinstance(val, dict):
            out[key] = normalize_message(val)
        elif isinstance(val, list):
            out[key] = [normalize_message(m) if isinstance(m, dict) else m for m in val]
    return out
