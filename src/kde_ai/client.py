from __future__ import annotations

import os
import socket
import subprocess
import time
from typing import Any, Callable

from kde_ai.errors import RpcError
from kde_ai.paths import socket_path
from kde_ai.protocol import decode_line, encode, request


class RpcClient:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self._id = 0
        self.notifications: list[dict] = []
        self.on_notify: Callable[[str, dict], None] | None = None

    def connect(self, start_daemon: bool = True) -> None:
        path = socket_path()
        if not path.exists() and start_daemon:
            subprocess.Popen(
                ["systemctl", "--user", "start", "kde-ai-agent.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(20):
                if path.exists():
                    break
                time.sleep(0.1)
            if not path.exists():
                # fall back to spawning in-process sibling
                subprocess.Popen(
                    ["kde-ai-agent"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                for _ in range(30):
                    if path.exists():
                        break
                    time.sleep(0.1)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(path))
        self.sock.settimeout(180)

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def call(self, method: str, params: dict | None = None, timeout: float = 180) -> Any:
        assert self.sock
        nid = self._next_id()
        self.sock.sendall(encode(request(nid, method, params)))
        deadline = time.time() + timeout
        buf = b""
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise RpcError("INTERNAL", "disconnected")
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = decode_line(line)
                if msg.get("id") == nid:
                    if "error" in msg:
                        err = msg["error"]
                        raise RpcError(err.get("code", "INTERNAL"), err.get("message", ""), err.get("data"))
                    return msg.get("result")
                if "method" in msg and "id" not in msg:
                    self.notifications.append(msg)
                    if self.on_notify:
                        self.on_notify(msg["method"], msg.get("params") or {})
        raise RpcError("TIMEOUT", method)

    def hello(self, client: str = "cli", auth: str = "tty") -> Any:

        return self.call(
            "hello",
            {
                "protocol_version": 1,
                "client": client,
                "auth_frontend": auth,
                "pid": os.getpid(),
                "locale": os.environ.get("LANG", "en_US.UTF-8"),
            },
        )

    def drain(self, timeout: float = 0.05) -> None:
        if not self.sock:
            return
        self.sock.settimeout(timeout)
        buf = b""
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = decode_line(line)
                    if "method" in msg and "id" not in msg:
                        self.notifications.append(msg)
                        if self.on_notify:
                            self.on_notify(msg["method"], msg.get("params") or {})
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(180)
