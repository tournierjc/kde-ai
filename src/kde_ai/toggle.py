#!/usr/bin/env python3
"""Open or raise the KDE AI window (optional global shortcut, unset by default)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_KWIN_RAISE = """
const wins = (typeof workspace.windowList === "function")
    ? workspace.windowList()
    : workspace.clientList();
for (let i = 0; i < wins.length; ++i) {
    const w = wins[i];
    const klass = String(w.resourceClass);
    const cap = String(w.caption);
    if (klass.indexOf("plasmawindowed") === -1 || cap.indexOf("KDE AI") === -1) {
        continue;
    }
    if (w.minimized) {
        w.minimized = false;
    }
    if (typeof workspace.activateWindow === "function") {
        workspace.activateWindow(w);
    } else {
        workspace.activeWindow = w;
    }
}
"""


def _qdbus() -> str | None:
    return shutil.which("qdbus6") or shutil.which("qdbus")


def _activate_existing() -> bool:
    """Raise an already-running plasmawindowed KDE AI window via KWin."""
    qdbus = _qdbus()
    if not qdbus:
        return False
    path = None
    plugin = "kdeai-raise"
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(_KWIN_RAISE)
            path = fh.name
        subprocess.run(
            [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", plugin],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        loaded = subprocess.run(
            [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", path, plugin],
            capture_output=True,
            text=True,
            check=False,
        )
        sid = (loaded.stdout or "").strip()
        if sid.isdigit():
            subprocess.run(
                [qdbus, "org.kde.KWin", f"/Scripting/Script{sid}", "org.kde.kwin.Script.run"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            subprocess.run(
                [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        subprocess.run(
            [qdbus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", plugin],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    finally:
        if path:
            Path(path).unlink(missing_ok=True)
    return True


def _plasmawindowed_running() -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-a", "plasmawindowed"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return "org.kde.kdeai" in out


def main() -> None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("KDE AI: no graphical session.", file=sys.stderr)
        raise SystemExit(1)
    if _plasmawindowed_running():
        _activate_existing()
        return
    windowed = shutil.which("plasmawindowed")
    if windowed:
        os.execvp(windowed, [windowed, "org.kde.kdeai"])
    ui = shutil.which("kde-ai-ui")
    if ui:
        os.execvp(ui, [ui])
    print("KDE AI: install plasmawindowed (plasma-workspace) or kde-ai-ui.", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
