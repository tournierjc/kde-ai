from __future__ import annotations

import os

from kde_ai.errors import FS, RpcError
from kde_ai.paths import runtime_dir
from kde_ai.tools import clip, run_argv
from kde_ai.undo import append_undo


def handle(_args: dict, ctx) -> dict:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise RpcError(FS, "no display for screenshot")
    shot = runtime_dir() / "shot.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    run_argv(["spectacle", "-b", "-n", "-o", str(shot)], timeout=20)
    if not shot.exists():
        run_argv(["grim", str(shot)], timeout=20)
    if not shot.exists():
        raise RpcError(FS, "screenshot failed")
    ocr = run_argv(["tesseract", str(shot), "stdout", "-l", "eng"], timeout=20)
    text = clip(ocr.get("stdout") or "", 4000)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "delete_file", "path": str(shot)})
    return {"ok": True, "text": text}


SCHEMA = {
    "name": "screenshot_ocr",
    "description": "Capture the screen and OCR it (CPU tesseract)",
    "parameters": {"type": "object", "properties": {}},
}
