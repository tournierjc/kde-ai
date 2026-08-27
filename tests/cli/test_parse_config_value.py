from __future__ import annotations

from kde_ai.cli import parse_config_value


def test_parse_config_value_json_and_raw_shortcut():
    assert parse_config_value("true") is True
    assert parse_config_value("15") == 15
    assert parse_config_value('"Meta+Ctrl+K"') == "Meta+Ctrl+K"
    assert parse_config_value("Meta+Ctrl+K") == "Meta+Ctrl+K"
    assert parse_config_value("") == ""
    assert parse_config_value('["kwin","firefox"]') == ["kwin", "firefox"]
