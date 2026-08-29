"""Start/stop the user daemon without the tray status poll bringing it back."""

from __future__ import annotations

import os
import signal
import subprocess
import time

from kde_ai.paths import ensure_dirs, pid_path, socket_path, stopped_path


def is_user_stopped() -> bool:
    return stopped_path().exists()


def mark_user_stopped() -> None:
    ensure_dirs()
    stopped_path().write_text("1\n", encoding="utf-8")


def clear_user_stopped() -> None:
    try:
        stopped_path().unlink()
    except FileNotFoundError:
        pass


def _systemctl_user(*args: str) -> None:
    subprocess.run(
        ["systemctl", "--user", *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def start_agent(wait_s: float = 5.0) -> dict:
    clear_user_stopped()
    _systemctl_user("start", "kde-ai-agent.service")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if socket_path().exists():
            return {"ok": True, "state": "starting"}
        time.sleep(0.1)
    if not socket_path().exists():
        subprocess.Popen(
            ["kde-ai-agent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if socket_path().exists():
                return {"ok": True, "state": "starting"}
            time.sleep(0.1)
    return {"ok": socket_path().exists(), "state": "starting" if socket_path().exists() else "stopped"}


def _ask_shutdown() -> None:
    if not socket_path().exists():
        return
    from kde_ai.client import RpcClient
    from kde_ai.errors import RpcError

    rpc = RpcClient()
    try:
        rpc.connect(start_daemon=False)
        rpc.hello(client="cli", auth="none")
        rpc.call("daemon.shutdown", {}, timeout=5)
    except (OSError, RpcError):
        pass
    finally:
        rpc.close()


def _signal_pidfile() -> None:
    try:
        pid = int(pid_path().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def stop_agent() -> dict:
    mark_user_stopped()
    _ask_shutdown()
    _systemctl_user("stop", "kde-ai-agent.service")
    deadline = time.time() + 3.0
    while socket_path().exists() and time.time() < deadline:
        time.sleep(0.05)
    _signal_pidfile()
    try:
        from kde_ai.toggle import _close, _pids

        _close(_pids("kde-ai-ui") or _pids("plasmawindowed", "org.kde.kdeai"))
    except Exception:
        pass
    sock = socket_path()
    if sock.exists():
        try:
            sock.unlink()
        except OSError:
            pass
    return {"ok": True, "state": "stopped"}
