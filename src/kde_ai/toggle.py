#!/usr/bin/env python3
"""Toggle the KDE AI window (optional global shortcut, unset by default)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys


def _pids(proc_name: str, needle: str | None = None) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-a", proc_name], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pids: list[int] = []
    me = os.getpid()
    for line in out.splitlines():
        if needle is not None and needle not in line:
            continue
        try:
            pid = int(line.split(None, 1)[0])
        except ValueError:
            continue
        if pid != me:
            pids.append(pid)
    return pids


def _close(pids: list[int]) -> bool:
    closed = False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            closed = True
        except ProcessLookupError:
            continue
    return closed


def main() -> None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("KDE AI: no graphical session.", file=sys.stderr)
        raise SystemExit(1)
    if _close(_pids("kde-ai-ui") or _pids("plasmawindowed", "org.kde.kdeai")):
        return
    # Wayland's task manager maps windows by desktop file name.
    # plasmawindowed hardcodes org.kde.plasmawindowed → the Plasma logo, so
    # prefer kde-ai-ui which reports org.kde.kdeai and ships the circuit-brain icon.
    ui = shutil.which("kde-ai-ui")
    if ui:
        os.execvp(ui, [ui])
    windowed = shutil.which("plasmawindowed")
    if windowed:
        os.execvp(windowed, [windowed, "org.kde.kdeai"])
    print("KDE AI: install kde-ai-ui (pip install -e '.[ui]') or plasmawindowed.", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
