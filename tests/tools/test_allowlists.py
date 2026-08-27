from __future__ import annotations

from pathlib import Path

import pytest

from kde_ai.errors import TOOL_DENIED, RpcError
from kde_ai.tools import ToolContext
from kde_ai.tools.edit_config import handle as edit_handle
from kde_ai.tools.pacman_mutate import handle as pac_handle
from kde_ai.tools.readonly import handle as ro_handle
from kde_ai.undo import replay_undo


class Dummy:
    def get(self, k, d=None):
        return d


def ctx(tmp_path, store=None):
    cfg = Dummy()
    cfg.get = lambda k, d=None: {
        "memory.tool_result_chars": 2000,
        "network.offline": False,
        "network.timeout_s": 2,
    }.get(k, d)
    return ToolContext(cfg, store, "sid", tmp_path / "att", lambda *a: None, lambda argv, reason: {"ok": True, "stdout": "", "stderr": "", "code": 0})


def test_readonly_allowlist(xdg, tmp_path):
    c = ctx(tmp_path)
    with pytest.raises(RpcError) as ei:
        ro_handle({"name": "bash"}, c)
    assert ei.value.code == TOOL_DENIED


def test_pacman_regex(xdg, tmp_path):
    c = ctx(tmp_path)
    with pytest.raises(RpcError):
        pac_handle({"action": "install", "pkgs": ["../etc"]}, c)
    with pytest.raises(RpcError):
        pac_handle({"action": "upgrade", "pkgs": ["htop"]}, c)


def test_edit_config_home_jail_and_undo(xdg, tmp_path):
    home = Path.home()
    target = home / ".config" / "kde-ai-test.conf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")
    att = tmp_path / "att"
    att.mkdir()
    c = ctx(tmp_path)
    c.attempt_dir = att
    edit_handle({"path": str(target), "content": "new\n"}, c)
    assert target.read_text(encoding="utf-8") == "new\n"
    replay_undo(att)
    assert target.read_text(encoding="utf-8") == "old\n"
    with pytest.raises(RpcError) as ei:
        edit_handle({"path": "/etc/passwd", "content": "x"}, c)
    assert ei.value.code == TOOL_DENIED
    with pytest.raises(RpcError):
        edit_handle({"path": str(home / ".ssh" / "id_rsa"), "content": "x"}, c)
