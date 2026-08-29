from __future__ import annotations

import json

import pytest

from kde_ai.lifecycle import clear_user_stopped, is_user_stopped, mark_user_stopped, stop_agent


def test_user_stopped_flag(xdg):
    assert is_user_stopped() is False
    mark_user_stopped()
    assert is_user_stopped() is True
    clear_user_stopped()
    assert is_user_stopped() is False


def test_connect_does_not_autostart_after_quit(xdg, monkeypatch):
    from kde_ai.client import RpcClient
    from kde_ai.paths import socket_path

    mark_user_stopped()
    started = []

    def fake_popen(argv, **kwargs):
        started.append(argv)
        raise AssertionError("must not spawn the agent while the user quit")

    monkeypatch.setattr("kde_ai.client.subprocess.Popen", fake_popen)
    rpc = RpcClient()
    with pytest.raises(OSError):
        rpc.connect(start_daemon=False)
    assert started == []
    assert not socket_path().exists()
    assert is_user_stopped() is True


def test_connect_start_clears_stopped_flag(xdg, monkeypatch):
    from kde_ai.client import RpcClient

    mark_user_stopped()
    started: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        started.append(list(argv))
        return None

    monkeypatch.setattr("kde_ai.client.subprocess.Popen", fake_popen)
    rpc = RpcClient()
    with pytest.raises(OSError):
        rpc.connect(start_daemon=True)
    assert is_user_stopped() is False
    assert started
    assert "systemctl" in started[0]


def test_status_reports_stopped_without_starting(xdg, capsys, monkeypatch):
    from kde_ai import cli

    cli.JSON_MODE = True

    def fake_popen(argv, **kwargs):
        raise AssertionError("status must not spawn the agent")

    monkeypatch.setattr("kde_ai.client.subprocess.Popen", fake_popen)
    assert cli.cmd_status() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "stopped"


def test_stop_agent_sets_flag_without_socket(xdg, monkeypatch):
    monkeypatch.setattr("kde_ai.lifecycle._systemctl_user", lambda *_a, **_k: None)
    monkeypatch.setattr("kde_ai.lifecycle._ask_shutdown", lambda: None)
    monkeypatch.setattr("kde_ai.lifecycle._signal_pidfile", lambda: None)
    result = stop_agent()
    assert result == {"ok": True, "state": "stopped"}
    assert is_user_stopped() is True
