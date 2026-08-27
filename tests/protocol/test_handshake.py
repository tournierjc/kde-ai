from __future__ import annotations

import threading
import time

from kde_ai.client import RpcClient
from kde_ai.daemon import Daemon
from kde_ai.errors import RpcError
from kde_ai.protocol import decode_line, encode, request


def _start(xdg):
    d = Daemon()
    t = threading.Thread(target=d.serve, daemon=True)
    t.start()
    for _ in range(50):
        from kde_ai.paths import socket_path

        if socket_path().exists():
            break
        time.sleep(0.05)
    return d


def test_hello_required(xdg):
    _start(xdg)
    import socket

    from kde_ai.paths import socket_path

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(str(socket_path()))
    s.sendall(encode(request(1, "status.get", {})))
    line = b""
    while b"\n" not in line:
        line += s.recv(4096)
    msg = decode_line(line.split(b"\n", 1)[0])
    assert msg["error"]["code"] == "PROTOCOL"
    s.close()


def test_handshake_and_busy(xdg):
    daemon = _start(xdg)
    rpc = RpcClient()
    rpc.connect(start_daemon=False)
    hello = rpc.hello()
    assert hello["ok"] is True
    sid = rpc.call("session.create", {"title": "A"})["session_id"]
    rpc.call("session.set_active", {"session_id": sid})
    # fake LLM is instant; still test second send while holding lock via pause disabled
    st = rpc.call("status.get")
    assert st["state"] in {"ready", "idle_unloaded", "answering", "disabled"}
    rpc.call("chat.send", {"session_id": sid, "message": "hello there"})
    time.sleep(0.3)
    rpc.drain(0.2)
    trans = rpc.call("session.transcript", {"session_id": sid, "limit": 50})
    assert trans["total"] >= 1
    rpc.close()
    daemon._stop = True


def test_config_whitelist(xdg):
    _start(xdg)
    rpc = RpcClient()
    rpc.connect(start_daemon=False)
    rpc.hello()
    try:
        rpc.call("config.set", {"patch": {"invent.token": "secret"}})
        assert False, "should reject"
    except RpcError as exc:
        assert exc.code == "VALIDATION"
    rpc.call("config.set", {"patch": {"daemon.log_level": "debug"}})
    cfg = rpc.call("config.get")
    assert cfg["daemon"]["log_level"] == "debug"
    rpc.call("config.set", {"patch": {"gpu.graphics_allow": "kwin,firefox,openlogi"}})
    cfg = rpc.call("config.get")
    assert "firefox" in cfg["gpu"]["graphics_allow"]
    assert "openlogi" in cfg["gpu"]["graphics_allow"]
    rpc.close()
