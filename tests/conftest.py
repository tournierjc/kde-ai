from __future__ import annotations

import pytest


@pytest.fixture
def xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "run").mkdir()
    monkeypatch.setenv("KDE_AI_FAKE_LLM", "1")
    from kde_ai.paths import config_dir, ensure_dirs

    ensure_dirs()
    (config_dir() / "config.toml").write_text(
        "[rag]\nreindex_on_boot = false\n[daemon]\nenabled = true\n",
        encoding="utf-8",
    )
    return tmp_path
