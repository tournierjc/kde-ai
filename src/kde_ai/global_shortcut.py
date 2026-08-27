"""Bind or clear the KDE AI window shortcut (KGlobalAccel _launch). Empty by default."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path

log = logging.getLogger("kde-ai")

COMPONENT = "org.kde.kdeai.desktop"
ACTION = "_launch"
FRIENDLY = "KDE AI"

# Qt::KeyboardModifier bits used by QKeySequence[0].toCombined()
_SHIFT = 0x02000000
_CTRL = 0x04000000
_ALT = 0x08000000
_META = 0x10000000
# Qt::Key_unknown — QKeySequence returns this for unparsed NativeText like "Méta"
_KEY_UNKNOWN = 0x01FFFFFF

_MODS = {
    "meta": _META,
    "super": _META,
    "win": _META,
    "méta": _META,
    "ctrl": _CTRL,
    "control": _CTRL,
    "contrôle": _CTRL,
    "controle": _CTRL,
    "strg": _CTRL,
    "alt": _ALT,
    "option": _ALT,
    "shift": _SHIFT,
    "maj": _SHIFT,
    "umschalt": _SHIFT,
}

_PORTABLE_MOD = {
    "meta": "Meta",
    "super": "Meta",
    "win": "Meta",
    "méta": "Meta",
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "contrôle": "Ctrl",
    "controle": "Ctrl",
    "strg": "Ctrl",
    "alt": "Alt",
    "option": "Alt",
    "shift": "Shift",
    "maj": "Shift",
    "umschalt": "Shift",
}

_NAMED_KEYS = {
    "esc": 0x01000000,
    "escape": 0x01000000,
    "tab": 0x01000001,
    "backtab": 0x01000002,
    "backspace": 0x01000003,
    "return": 0x01000004,
    "enter": 0x01000005,
    "ins": 0x01000006,
    "insert": 0x01000006,
    "del": 0x01000007,
    "delete": 0x01000007,
    "pause": 0x01000008,
    "print": 0x01000009,
    "sysreq": 0x0100000A,
    "clear": 0x0100000B,
    "home": 0x01000010,
    "end": 0x01000011,
    "left": 0x01000012,
    "up": 0x01000013,
    "right": 0x01000014,
    "down": 0x01000015,
    "pgup": 0x01000016,
    "pageup": 0x01000016,
    "pgdown": 0x01000017,
    "pagedown": 0x01000017,
    "space": 0x20,
    "plus": 0x2B,
    "comma": 0x2C,
    "minus": 0x2D,
    "period": 0x2E,
    "slash": 0x2F,
    "semicolon": 0x3B,
    "apostrophe": 0x27,
    "backslash": 0x5C,
    "bracketleft": 0x5B,
    "bracketright": 0x5D,
}

_PORTABLE_KEYS = {
    "esc": "Esc",
    "escape": "Esc",
    "tab": "Tab",
    "backspace": "Backspace",
    "return": "Return",
    "enter": "Enter",
    "ins": "Ins",
    "insert": "Ins",
    "del": "Del",
    "delete": "Del",
    "home": "Home",
    "end": "End",
    "left": "Left",
    "up": "Up",
    "right": "Right",
    "down": "Down",
    "pgup": "PgUp",
    "pageup": "PgUp",
    "pgdown": "PgDown",
    "pagedown": "PgDown",
    "space": "Space",
    "plus": "Plus",
}


def _named_keys() -> dict[str, int]:
    keys = dict(_NAMED_KEYS)
    for i in range(1, 36):
        keys[f"f{i}"] = 0x01000030 + i - 1
    return keys


def _portable_keys() -> dict[str, str]:
    keys = dict(_PORTABLE_KEYS)
    for i in range(1, 36):
        keys[f"f{i}"] = f"F{i}"
    return keys


_KEYS = _named_keys()
_KEY_NAMES = _portable_keys()


def _fold(tok: str) -> str:
    return unicodedata.normalize("NFC", tok).casefold()


def kglobalshortcuts_path() -> Path:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return cfg / "kglobalshortcutsrc"


def _ini_value(path: Path, group: str, key: str) -> str | None:
    if not path.is_file():
        return None
    in_group = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_group = s[1:-1] == group
            continue
        if in_group and s.startswith(key + "="):
            return s.split("=", 1)[1]
    return None


def current_launch_shortcut() -> str | None:
    """Current KDE AI _launch chord, or '' if unbound. None if the entry is missing."""
    raw = _ini_value(kglobalshortcuts_path(), COMPONENT, ACTION)
    if raw is None:
        return None
    cur = raw.split(",", 1)[0].strip().split("\t")[0].strip()
    if not cur or cur.lower() == "none":
        return ""
    return cur


def _tokenize(seq: str) -> list[str]:
    raw = seq.strip().replace(" ", "")
    parts = raw.split("+")
    tokens: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i]
        if part:
            tokens.append(part)
            i += 1
            continue
        # "Ctrl++" → trailing Plus
        tokens.append("plus")
        i += 1
        while i < len(parts) and not parts[i]:
            i += 1
    return tokens


def to_portable(seq: str) -> str:
    """Turn NativeText (e.g. French Méta+Ctrl+K) into Qt PortableText (Meta+Ctrl+K)."""
    text = (seq or "").strip()
    if not text or _fold(text) in ("none", "empty"):
        raise ValueError("empty shortcut")
    tokens = _tokenize(text)
    if not tokens:
        raise ValueError("empty shortcut")
    parts: list[str] = []
    for tok in tokens[:-1]:
        name = _PORTABLE_MOD.get(_fold(tok))
        if name is None:
            raise ValueError(f"unknown modifier: {tok}")
        parts.append(name)
    last = tokens[-1]
    low = _fold(last)
    if low in _PORTABLE_MOD and len(tokens) == 1:
        raise ValueError("modifier-only shortcut")
    if low in _KEY_NAMES:
        parts.append(_KEY_NAMES[low])
    elif len(last) == 1:
        parts.append(last.upper())
    else:
        raise ValueError(f"unknown key: {last}")
    return "+".join(parts)


def parse_combined(seq: str) -> int:
    """Qt toCombined() integer without importing Qt."""
    text = (seq or "").strip()
    if not text or _fold(text) in ("none", "empty"):
        raise ValueError("empty shortcut")
    tokens = _tokenize(text)
    if not tokens:
        raise ValueError("empty shortcut")
    mods = 0
    for tok in tokens[:-1]:
        bit = _MODS.get(_fold(tok))
        if bit is None:
            raise ValueError(f"unknown modifier: {tok}")
        mods |= bit
    last = tokens[-1]
    low = _fold(last)
    if low in _MODS and len(tokens) == 1:
        raise ValueError("modifier-only shortcut")
    if low in _KEYS:
        key = _KEYS[low]
    elif len(last) == 1:
        key = ord(last.upper())
    else:
        raise ValueError(f"unknown key: {last}")
    return mods | key


def to_combined(seq: str) -> int:
    """Qt toCombined() integer for a PortableText chord like Meta+Shift+A."""
    portable = to_portable(seq)
    try:
        from PySide6.QtGui import QKeySequence

        q = QKeySequence(portable)
        if q.count() < 1:
            raise ValueError("empty shortcut")
        code = int(q[0].toCombined())
        if code == _KEY_UNKNOWN:
            return parse_combined(portable)
        return code
    except ImportError:
        return parse_combined(portable)



def _kwrite(group: str, key: str, value: str) -> None:
    exe = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if not exe:
        return
    subprocess.run(
        [exe, "--file", "kglobalshortcutsrc", "--group", group, "--key", key, value],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _dbus_set_keys(keys: list[int]) -> None:
    gdbus = shutil.which("gdbus")
    if not gdbus:
        return
    action = f"['{COMPONENT}', '{ACTION}', '{FRIENDLY}', '{FRIENDLY}']"
    payload = "@ai []" if not keys else f"@ai [{','.join(str(k) for k in keys)}]"
    subprocess.run(
        [
            gdbus,
            "call",
            "--session",
            "--dest",
            "org.kde.kglobalaccel",
            "--object-path",
            "/kglobalaccel",
            "--method",
            "org.kde.KGlobalAccel.doRegister",
            action,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            gdbus,
            "call",
            "--session",
            "--dest",
            "org.kde.kglobalaccel",
            "--object-path",
            "/kglobalaccel",
            "--method",
            "org.kde.KGlobalAccel.setShortcut",
            action,
            payload,
            "4",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
    if qdbus:
        subprocess.run(
            [qdbus, "org.kde.kglobalaccel", "/kglobalaccel", "org.kde.KGlobalAccel.reconfigure"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def apply_launch_shortcut(seq: str) -> None:
    """Write KDE AI's _launch shortcut. Empty string unbinds it (the default)."""
    text = (seq or "").strip()
    if not text or _fold(text) in ("none", "empty"):
        text = ""
    else:
        try:
            text = to_portable(text)
        except ValueError:
            log.warning("could not encode shortcut %r for KGlobalAccel", seq)
            return
    _kwrite(COMPONENT, "_k_friendly_name", FRIENDLY)
    _kwrite(COMPONENT, ACTION, f"{text or 'none'},none,{FRIENDLY}")
    if not text:
        _dbus_set_keys([])
        return
    try:
        _dbus_set_keys([to_combined(text)])
    except ValueError:
        log.warning("could not encode shortcut %r for KGlobalAccel; wrote kconfig only", text)


def overlay_live_shortcut(data: dict) -> dict:
    live = current_launch_shortcut()
    if live is None:
        return data
    if live:
        try:
            live = to_portable(live)
        except ValueError:
            pass
    plasma = data.setdefault("plasma", {})
    if isinstance(plasma, dict):
        plasma["global_shortcut"] = live
    return data
