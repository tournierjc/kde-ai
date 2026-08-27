from __future__ import annotations

import re
import subprocess
from typing import Callable

PKG_RE = re.compile(r"^[a-z0-9@._+-]+$")
UNIT_RE = re.compile(r"^[a-zA-Z0-9:_.\\-]+$")


def run_argv(argv: list[str], timeout: int = 30, env: dict | None = None) -> dict:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"not found: {argv[0]}", "code": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "code": 124}
    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "code": proc.returncode,
    }


def clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n] + "…"


class ToolContext:
    def __init__(self, cfg, store, session_id: str, attempt_dir, notify, request_privilege):
        self.cfg = cfg
        self.store = store
        self.session_id = session_id
        self.attempt_dir = attempt_dir
        self.notify = notify
        self.request_privilege = request_privilege
        self.tool_result_chars = int(cfg.get("memory.tool_result_chars", 2000))
        self.offline = bool(cfg.get("network.offline", False))
        self.timeout = int(cfg.get("network.timeout_s", 10))


ToolFn = Callable[[dict, ToolContext], dict]
