from __future__ import annotations

import pytest

from kde_ai.config import DEFAULTS
from kde_ai.global_shortcut import parse_combined, to_combined, to_portable


def test_default_shortcut_is_empty():
    assert DEFAULTS["plasma"]["global_shortcut"] == ""


@pytest.mark.parametrize(
    ("seq", "expected"),
    [
        ("Meta+Shift+A", 301989953),
        ("Ctrl+Alt+K", 201326667),
        ("Ctrl+F1", 83886128),
        ("Meta+Return", 285212676),
    ],
)
def test_to_combined_matches_qt(seq: str, expected: int):
    assert parse_combined(seq) == expected


def test_parse_combined_native_aliases():
    assert parse_combined("Meta+Maj+A") == parse_combined("Meta+Shift+A")
    assert parse_combined("Strg+Alt+K") == parse_combined("Ctrl+Alt+K")
    assert to_portable("Méta+Ctrl+K") == "Meta+Ctrl+K"
    assert to_combined("Méta+Ctrl+K") == to_combined("Meta+Ctrl+K")
    assert to_combined("Méta+Ctrl+K") != 0x01FFFFFF
    with pytest.raises(ValueError):
        parse_combined("")
    with pytest.raises(ValueError):
        parse_combined("none")
