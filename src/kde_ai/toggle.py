#!/usr/bin/env python3
"""Open the KDE AI plasmoid (default global shortcut: Meta+Shift+A)."""

from __future__ import annotations

import os
import shutil
import sys


def main() -> None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("KDE AI: no graphical session.", file=sys.stderr)
        raise SystemExit(1)
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
