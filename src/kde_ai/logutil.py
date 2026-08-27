from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger("kde-ai")

_SECRET = re.compile(r"(password|token|authorization|secret|api[_-]?key)\s*[:=]\s*\S+", re.I)


def redact_text(text: str) -> str:
    return _SECRET.sub(r"\1: [redacted]", text)


def setup_logging(level: str = "info") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s kde-ai %(levelname)s %(message)s",
    )


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
