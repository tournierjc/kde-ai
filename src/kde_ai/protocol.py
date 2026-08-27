from __future__ import annotations

import json
from typing import Any

MAX_LINE = 8 * 1024 * 1024


def encode(obj: dict) -> bytes:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    data = line.encode("utf-8")
    if len(data) > MAX_LINE:
        raise ValueError("message too large")
    return data


def decode_line(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_LINE:
        raise ValueError("message too large")
    return json.loads(line.decode("utf-8"))


def result(id_: Any, payload: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": payload}


def error(id_: Any, code: str, message: str, data: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": id_,
        "error": {"code": code, "message": message, "data": data or {}},
    }


def notify(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def request(id_: Any, method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
