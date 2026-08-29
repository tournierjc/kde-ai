from __future__ import annotations

import json
import os
import signal
import socket
import threading
import time
import uuid
from pathlib import Path

from kde_ai import __version__
from kde_ai.agent import Agent
from kde_ai.config import Config, apply_patch
from kde_ai.errors import OVERFLOW, PROTOCOL, VALIDATION, RpcError
from kde_ai.llm import LlamaRuntime, find_llama_server
from kde_ai.logutil import log, redact_text, setup_logging
from kde_ai.paths import ensure_dirs, pid_path, socket_path
from kde_ai.protocol import decode_line, error, notify, result
from kde_ai.rag import reindex
from kde_ai.sessions import SessionStore
from kde_ai.skills import install_skill, load_all_skills, remove_skill
from kde_ai.tools.registry import SCHEMAS
from kde_ai.watchdog import GpuWatchdog


class ClientConn:
    def __init__(self, sock: socket.socket, daemon: "Daemon") -> None:
        self.sock = sock
        self.daemon = daemon
        self.hello_ok = False
        self.kind = "cli"
        self.auth = "none"
        self.locale = "en_US"
        self.lock = threading.Lock()

    def send(self, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with self.lock:
            try:
                self.sock.sendall(line.encode("utf-8"))
            except OSError:
                pass


class Daemon:
    def __init__(self) -> None:
        ensure_dirs()
        self.cfg = Config()
        setup_logging(str(self.cfg.get("daemon.log_level", "info")))
        self.store = SessionStore(int(self.cfg.get("daemon.max_sessions", 50)))
        self.llm = LlamaRuntime(self.cfg)
        self.llm.on_spawn = lambda pid: self.watchdog.add_pid(pid)
        self.clients: list[ClientConn] = []
        self.watchdog = GpuWatchdog(self.cfg, {os.getpid()})
        self.agent = Agent(self.cfg, self.store, self.llm, self.watchdog, self.broadcast)
        self._stop = False
        self.state = "idle_unloaded"

    def _request_stop(self) -> None:
        time.sleep(0.05)
        try:
            self.llm.unload()
        except Exception:
            pass
        self._stop = True

    def broadcast(self, method: str, params: dict) -> None:
        msg = notify(method, params)
        for c in list(self.clients):
            c.send(msg)
        if method == "status.changed":
            return
        # refresh status after streams
        if method in ("stream.done", "issue.awaiting"):
            self.broadcast_status()

    def status_obj(self) -> dict:
        self.watchdog.poll()
        if not self.cfg.get("daemon.enabled", True):
            st = "disabled"
        elif self.watchdog.paused and not self.cfg.get("daemon.force_run_during_pause"):
            st = "paused"
        elif self.agent.awaiting_privilege:
            st = "awaiting_privilege"
        elif self.agent.busy():
            st = "answering"
        elif self.llm.loaded():
            st = "ready"
        else:
            st = "idle_unloaded"
        meta = None
        sid = self.store.active_id
        pending = False
        if sid:
            try:
                meta = self.store.load_meta(sid)
                pending = bool(meta.get("pending_solution"))
            except RpcError:
                pass
        if pending:
            st = "awaiting_confirm"
        return {
            "state": st,
            "vram_mb": 0,
            "reason": self.watchdog.reason,
            "active_session_id": self.store.active_id,
            "stream_id": self.agent.stream_id,
            "gpu_blocker_pid": self.watchdog.blocker_pid,
            "config_error": self.cfg.config_error,
        }

    def broadcast_status(self) -> None:
        for c in list(self.clients):
            c.send(notify("status.changed", self.status_obj()))

    def doctor(self) -> dict:
        import shutil

        from kde_ai.paths import docs_db

        sock = socket_path()
        linger = False
        try:
            r = __import__("subprocess").run(
                ["loginctl", "show-user", os.environ.get("USER", ""), "-p", "Linger"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            linger = "Linger=yes" in (r.stdout or "")
        except Exception:
            linger = Path(f"/var/lib/systemd/linger/{os.environ.get('USER','')}").exists()
        db = docs_db()
        fts_mtime = db.stat().st_mtime if db.exists() else None
        polkit = bool(shutil.which("pkexec"))
        return {
            "socket": str(sock),
            "socket_exists": sock.exists(),
            "linger": linger,
            "gguf": Path(os.path.expanduser(str(self.cfg.get("llm.gguf")))).exists(),
            "gguf_path": os.path.expanduser(str(self.cfg.get("llm.gguf"))),
            "llama_server": bool(find_llama_server(self.cfg.get("llm.llama_server"))),
            "llama_server_path": find_llama_server(self.cfg.get("llm.llama_server")),
            "nvml": self.watchdog._nvml_ok,
            "paused": self.watchdog.paused,
            "display": bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
            "docs_db": str(db),
            "fts_mtime": fts_mtime,
            "polkit_pkexec": polkit,
            "invent_token": Path(os.path.expanduser("~/.config/kde-ai/invent.token")).exists(),
            "fetch_gguf_hint": "scripts/fetch-gguf.sh",
            "version": __version__,
        }

    def handle(self, conn: ClientConn, req: dict) -> dict | None:
        if "method" in req and "id" not in req:
            return None
        mid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method != "hello" and not conn.hello_ok:
                raise RpcError(PROTOCOL, "hello required")
            payload = self.dispatch(conn, method, params)
            return result(mid, payload)
        except RpcError as exc:
            return error(mid, exc.code, redact_text(exc.message), exc.data)
        except Exception as exc:
            log.exception("dispatch")
            return error(mid, "INTERNAL", str(exc))

    def dispatch(self, conn: ClientConn, method: str, params: dict):
        if method == "hello":
            if int(params.get("protocol_version") or 0) != 1:
                raise RpcError(PROTOCOL, "unsupported protocol")
            conn.hello_ok = True
            conn.kind = params.get("client") or "cli"
            conn.auth = params.get("auth_frontend") or "none"
            conn.locale = params.get("locale") or "en_US"
            return {"ok": True, "daemon_version": __version__, "status": self.status_obj()}
        if method == "status.get":
            return self.status_obj()
        if method == "status.set_enabled":
            apply_patch(self.cfg, {"daemon.enabled": bool(params.get("enabled"))})
            self.broadcast("config.changed", {"patch_keys": ["daemon.enabled"]})
            return self.status_obj()
        if method == "daemon.shutdown":
            threading.Thread(target=self._request_stop, daemon=True).start()
            return {"ok": True}
        if method == "chat.send":
            sid = params.get("session_id") or self.store.active_id
            if not sid:
                raise RpcError(VALIDATION, "no session")
            hint = bool(params.get("issue_hint"))
            stream = self.agent.start_chat(
                sid, params.get("message") or "", hint, conn.kind, conn.locale
            )
            return {"stream_id": stream}
        if method == "chat.cancel":
            self.agent.cancel(params.get("stream_id") or "")
            return {"ok": True}
        if method == "session.create":
            return {"session_id": self.store.create(params.get("title"))["id"]}
        if method == "session.list":
            return self.store.list_sessions(bool(params.get("include_archived")))
        if method == "session.rename":
            self.store.rename(params["session_id"], params["title"])
            return {"ok": True}
        if method == "session.delete":
            self.store.delete(params["session_id"])
            return {"ok": True}
        if method == "session.archive":
            self.store.archive(params["session_id"], params.get("archived", True))
            return {"ok": True}
        if method == "session.transcript":
            return self.store.transcript(
                params["session_id"],
                int(params.get("limit") or 100),
                int(params.get("offset") or 0),
            )
        if method == "session.set_active":
            self.store.set_active(params["session_id"])
            return {"ok": True}
        if method == "session.export":
            path = self.store.export(params["session_id"], params.get("path"))
            return {"path": path}
        if method == "session.bug_report":
            return {"markdown": self.store.bug_report(params["session_id"])}
        if method == "memory.clear":
            self.store.clear_memory(params["session_id"], params.get("scope") or "working")
            return {"ok": True}
        if method == "memory.summarize":
            trans = self.store.transcript(params["session_id"], 200)["messages"]
            text = "\n".join(
                f"{m.get('role')}: {str(m.get('content') or '')[:200]}" for m in trans[-20:]
            )
            self.store.set_summary(params["session_id"], text[:4000])
            return {"ok": True}
        if method == "memory.pin":
            from kde_ai.prompting import approx_tokens

            pins = self.store.pins(params["session_id"])
            text = params.get("text") or ""
            budget = int(self.cfg.get("memory.pins_tok", 200))
            used = approx_tokens("".join(p.get("text") or "" for p in pins))
            if used + approx_tokens(text) > budget:
                raise RpcError(OVERFLOW, "pin budget exceeded")
            pid = str(uuid.uuid4())
            pins.append({"id": pid, "text": text})
            self.store.save_pins(params["session_id"], pins)
            return {"pin_id": pid}
        if method == "memory.unpin":
            pins = [p for p in self.store.pins(params["session_id"]) if p.get("id") != params.get("pin_id")]
            self.store.save_pins(params["session_id"], pins)
            return {"ok": True}
        if method == "memory.pins":
            return self.store.pins(params["session_id"])
        if method == "memory.solved":
            return self.store.solved(params["session_id"])
        if method == "memory.forget_solved":
            self.store.forget_solved(params["session_id"], params["solved_id"])
            return {"ok": True}
        if method == "memory.stats":
            from kde_ai.prompting import approx_tokens

            sid = params["session_id"]
            return {
                "working_tokens": approx_tokens(
                    "".join(str(m.get("content") or "") for m in self.store.working_messages(sid))
                ),
                "summary_tokens": approx_tokens(self.store.summary(sid)),
                "pin_tokens": approx_tokens("".join(p.get("text") or "" for p in self.store.pins(sid))),
                "solved_tokens": approx_tokens(
                    "".join((s.get("issue") or "") + (s.get("solution") or "") for s in self.store.solved(sid))
                ),
                "budget": self.cfg.get("llm.ctx", 4096),
                "overflow": self.store.load_meta(sid).get("overflow", False),
            }
        if method == "config.get":
            from kde_ai.global_shortcut import overlay_live_shortcut

            return overlay_live_shortcut(self.cfg.redacted())
        if method == "config.set":
            keys = apply_patch(self.cfg, params.get("patch") or {})
            if any(k.startswith("gpu.") or k == "daemon.force_run_during_pause" for k in keys):
                self.watchdog._clear_since = 0.0
                self.watchdog.poll()
                self.broadcast_status()
            self.broadcast("config.changed", {"patch_keys": keys})
            return {"ok": True}
        if method == "skills.list":
            skills = load_all_skills()
            sid = params.get("session_id")
            override = self.store.load_meta(sid).get("skills_enabled") if sid else {}
            cfg_en = set(self.cfg.get("skills.enabled") or [])
            out = []
            for sk in skills.values():
                on = override[sk.id] if sid and sk.id in override else sk.id in cfg_en
                out.append(sk.as_dict(on))
            return out
        if method == "skills.set_enabled":
            sid = params.get("session_id")
            skid = params["id"]
            en = bool(params.get("enabled"))
            if sid:
                meta = self.store.load_meta(sid)
                meta.setdefault("skills_enabled", {})[skid] = en
                self.store.save_meta(meta)
            else:
                cur = list(self.cfg.get("skills.enabled") or [])
                if en and skid not in cur:
                    cur.append(skid)
                if not en:
                    cur = [x for x in cur if x != skid]
                apply_patch(self.cfg, {"skills.enabled": cur[: int(self.cfg.get("skills.max_enabled_per_session", 3))]})
            self.broadcast("skills.changed", {"id": skid, "enabled": en})
            return {"ok": True}
        if method == "skills.get":
            skills = load_all_skills()
            sk = skills.get(params["id"])
            if not sk:
                raise RpcError(VALIDATION, "unknown skill")
            return {
                "frontmatter": {
                    "id": sk.id,
                    "name": sk.name,
                    "description": sk.description,
                    "tools": sk.tools,
                },
                "body": sk.body,
            }
        if method == "skills.install":
            sid = install_skill(params["path"])
            return {"id": sid}
        if method == "skills.remove":
            remove_skill(params["id"])
            return {"ok": True}
        if method == "issue.confirm":
            sid = params["session_id"]
            meta = self.store.load_meta(sid)
            sol = meta.get("pending_solution") or ""
            out = self.agent.issues.confirm(
                sid, params["attempt_id"], bool(params.get("solved")), params.get("note"), sol
            )
            meta = self.store.load_meta(sid)
            meta.pop("pending_solution", None)
            self.store.save_meta(meta)
            return out
        if method == "issue.cancel":
            return self.agent.issues.cancel(params["session_id"])
        if method == "tools.list":
            return SCHEMAS
        if method == "privilege.complete":
            return self.agent.privilege_complete(
                params["request_id"],
                {
                    "ok": params.get("ok"),
                    "cancelled": params.get("cancelled"),
                    "stdout": params.get("stdout") or "",
                    "stderr": params.get("stderr") or "",
                    "code": params.get("code", 1),
                },
            )
        if method == "rag.reindex":
            n = reindex(self.cfg, bool(params.get("force")))
            return {"docs_indexed": n}
        if method == "doctor":
            return self.doctor()
        raise RpcError(PROTOCOL, f"unknown method {method}")

    def idle_loop(self) -> None:
        while not self._stop:
            time.sleep(1)
            self.watchdog.poll()
            if self.llm.proc and self.llm.loaded():
                idle = time.time() - self.llm.last_used
                if (
                    idle >= float(self.cfg.get("daemon.idle_unload_s", 15))
                    and not self.agent.busy()
                    and not self.agent.awaiting_privilege
                ):
                    self.llm.unload()
                    self.broadcast_status()
            if self.llm.proc and self.llm.proc.pid:
                self.watchdog.add_pid(self.llm.proc.pid)

    def serve(self) -> None:
        ensure_dirs()
        path = socket_path()
        if path.exists():
            path.unlink()
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(path))
        os.chmod(path, 0o600)
        srv.listen(16)
        srv.settimeout(0.5)
        pid_path().write_text(str(os.getpid()), encoding="utf-8")
        threading.Thread(target=self.idle_loop, daemon=True).start()
        if self.cfg.get("rag.reindex_on_boot"):
            threading.Thread(target=lambda: reindex(self.cfg, False), daemon=True).start()
        log.info("listening on %s", path)

        def stop(*_):
            self._stop = True
            try:
                self.llm.unload()
            except Exception:
                pass

        try:
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
        except ValueError:
            pass
        while not self._stop:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                import struct

                _pid, uid, _gid = struct.unpack("3i", creds)
                if uid != os.getuid():
                    conn.close()
                    continue
            except OSError:
                conn.close()
                continue
            cc = ClientConn(conn, self)
            self.clients.append(cc)
            threading.Thread(target=self._client_loop, args=(cc,), daemon=True).start()
        srv.close()
        if path.exists():
            path.unlink()

    def _client_loop(self, cc: ClientConn) -> None:
        buf = b""
        try:
            while not self._stop:
                chunk = cc.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    req = decode_line(line)
                    resp = self.handle(cc, req)
                    if resp:
                        cc.send(resp)
        except Exception:
            pass
        finally:
            try:
                self.clients.remove(cc)
            except ValueError:
                pass
            cc.sock.close()


def main() -> None:
    Daemon().serve()


if __name__ == "__main__":
    main()
