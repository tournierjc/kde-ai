from __future__ import annotations

import os
from urllib.parse import urlparse

from kde_ai.errors import FS, VALIDATION, RpcError
from kde_ai.tools import run_argv
from kde_ai.undo import append_undo


def handle(args: dict, ctx) -> dict:
    url = args.get("url") or ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RpcError(VALIDATION, "url must be http(s)")
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RpcError(FS, f"no display; open manually: {url}")
    r = run_argv(["xdg-open", url], timeout=10)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    r["url"] = url
    return r


SCHEMA = {
    "name": "open_url",
    "description": "Open an http(s) URL in the browser",
    "parameters": {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
}
