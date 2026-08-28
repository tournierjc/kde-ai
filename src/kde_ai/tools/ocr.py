from __future__ import annotations

import os
import re

from kde_ai.errors import FS, RpcError
from kde_ai.paths import runtime_dir
from kde_ai.tools import clip, run_argv
from kde_ai.undo import append_undo

_SCREENSHOT_RE = re.compile(
    r"\b(?:take|capture|grab)\b.{0,24}\b(?:a\s+)?screenshot\b|"
    r"\bscreenshot\b.{0,24}\b(?:please|now|of (?:the |my )?screen)\b|"
    r"\bocr (?:the |this |my )?(?:current )?screen\b|"
    r"\bcapture (?:the |my )?screen\b",
    re.I,
)

_SCREENSHOT_FALLBACK = (
    "I can capture the screen with screenshot_ocr (spectacle or grim, then "
    "tesseract). The chat has no screenshot control; I capture when you ask."
)


def is_screenshot_request(text: str) -> bool:
    return bool(_SCREENSHOT_RE.search(text or ""))


def summarize_screenshot(payload: dict | None) -> str:
    if not payload:
        return _SCREENSHOT_FALLBACK
    if not payload.get("ok"):
        msg = payload.get("message") or payload.get("error") or "screenshot failed"
        return (
            f"Screenshot failed: {msg}. The chat has no screenshot control; "
            "I capture when you ask."
        )
    text = (payload.get("text") or "").strip()
    path = (payload.get("path") or "").strip()
    bits = []
    if path:
        bits.append(f"Captured the screen to {path}.")
    else:
        bits.append("Captured the screen.")
    if text:
        bits.append(f"OCR text: {text}")
    else:
        bits.append("Tesseract found no readable text.")
    return " ".join(bits)


def prefer_screenshot_reply(user_text: str, model_text: str, payload: dict | None) -> str:
    if not is_screenshot_request(user_text):
        return model_text
    return summarize_screenshot(payload)


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
    return {"ok": True, "text": text, "path": str(shot)}


SCHEMA = {
    "name": "screenshot_ocr",
    "description": "Capture the screen and OCR it (CPU tesseract)",
    "parameters": {"type": "object", "properties": {}},
}
