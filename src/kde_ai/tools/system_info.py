from __future__ import annotations

import os
import platform
from pathlib import Path

from kde_ai.tools import run_argv


def handle(_args: dict, ctx) -> dict:
    os_release = {}
    p = Path("/etc/os-release")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                os_release[k] = v.strip().strip('"')
    plasma = run_argv(["plasmashell", "--version"])
    gpu = run_argv(["nvidia-smi", "-L"])
    return {
        "ok": True,
        "os_release": os_release,
        "kernel": platform.release(),
        "plasma": (plasma.get("stdout") or "").strip(),
        "qt": os.environ.get("QT_VERSION", ""),
        "session": os.environ.get("XDG_SESSION_TYPE", ""),
        "gpu": (gpu.get("stdout") or "").strip(),
        "hostname": platform.node(),
        "user": os.environ.get("USER", ""),
    }


SCHEMA = {
    "name": "system_info",
    "description": "Read OS, Plasma, kernel, GPU, hostname",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
