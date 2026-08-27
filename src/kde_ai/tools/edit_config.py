from __future__ import annotations

import shutil
from pathlib import Path

from kde_ai.errors import FS, TOOL_DENIED, VALIDATION, RpcError
from kde_ai.undo import append_undo

DENY_PARTS = (".ssh", ".gnupg", ".pki", ".password-store")
MAX = 1024 * 1024


def _safe_path(raw: str) -> Path:
    home = Path.home().resolve()
    p = Path(raw).expanduser()
    try:
        resolved = p.resolve()
    except Exception as exc:
        raise RpcError(FS, str(exc)) from exc
    if home not in resolved.parents and resolved != home:
        raise RpcError(TOOL_DENIED, "path must be under $HOME")
    if resolved.parts[:2] == ("/", "etc"):
        raise RpcError(TOOL_DENIED, "refusing /etc; edit manually")
    s = str(resolved)
    for part in DENY_PARTS:
        if f"/{part}/" in f"/{s}/" or s.endswith(f"/{part}"):
            raise RpcError(TOOL_DENIED, "refusing sensitive path")
    if resolved.suffix == ".key":
        raise RpcError(TOOL_DENIED, "refusing .key files")
    return resolved


def handle(args: dict, ctx) -> dict:
    path = _safe_path(args.get("path") or "")
    if path.exists() and path.stat().st_size > MAX:
        raise RpcError(VALIDATION, "file too large")
    bak = None
    if ctx.attempt_dir:
        bak = ctx.attempt_dir / "files" / path.name
        bak.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, bak)
        append_undo(
            ctx.attempt_dir,
            {"op": "restore_file", "path": str(path), "blob": str(bak)},
        )
    if "content" in args:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
    elif "search" in args and "replace" in args:
        if not path.exists():
            raise RpcError(FS, "file not found")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(args["search"], args["replace"], 1), encoding="utf-8")
    else:
        raise RpcError(VALIDATION, "content or search/replace required")
    return {"ok": True, "path": str(path)}


SCHEMA = {
    "name": "edit_config",
    "description": "Edit a user-owned config file under $HOME",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "search": {"type": "string"},
            "replace": {"type": "string"},
        },
        "required": ["path"],
    },
}
