from __future__ import annotations

import os
from pathlib import Path

from kde_ai.llm import find_llama_server


def test_find_llama_server_abs_path(tmp_path: Path):
    bin_path = tmp_path / "llama-server"
    bin_path.write_text("#!/bin/sh\n")
    bin_path.chmod(0o755)
    assert find_llama_server(str(bin_path)) == str(bin_path)


def test_find_llama_server_which(tmp_path: Path, monkeypatch):
    bin_path = tmp_path / "llama-server"
    bin_path.write_text("#!/bin/sh\n")
    bin_path.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    assert find_llama_server("llama-server") == str(bin_path)
