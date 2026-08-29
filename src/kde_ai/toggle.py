#!/usr/bin/env python3
"""Open, close, or toggle the KDE AI window (optional global shortcut, unset by default)."""

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


def window_pids() -> list[int]:
    return _pids("kde-ai-ui") or _pids("plasmawindowed", "org.kde.kdeai")


def _close(pids: list[int]) -> bool:
    closed = False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            closed = True
        except ProcessLookupError:
            continue
    return closed


def _activate_existing() -> bool:
    if not window_pids():
        return False
    for cmd in (["kstart6", "--activate", "org.kde.kdeai"], ["kstart", "--activate", "org.kde.kdeai"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False, capture_output=True)
            return True
    return True


def _launch_window() -> int:
    # Wayland's task manager maps windows by desktop file name.
    # plasmawindowed hardcodes org.kde.plasmawindowed → the Plasma logo, so
    # prefer kde-ai-ui which reports org.kde.kdeai and ships the circuit-brain icon.
    ui = shutil.which("kde-ai-ui")
    if ui:
        subprocess.Popen(
            [ui],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return 0
    windowed = shutil.which("plasmawindowed")
    if windowed:
        subprocess.Popen(
            [windowed, "org.kde.kdeai"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return 0
    print("KDE AI: install kde-ai-ui (pip install -e '.[ui]') or plasmawindowed.", file=sys.stderr)
    return 1


def open_window() -> int:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("KDE AI: no graphical session.", file=sys.stderr)
        return 1
    if _activate_existing():
        return 0
    return _launch_window()


def close_window() -> bool:
    return _close(window_pids())


def main() -> None:
    if close_window():
        return
    raise SystemExit(open_window())


if __name__ == "__main__":
    main()
