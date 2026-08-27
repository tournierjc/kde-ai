from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from kde_ai.client import RpcClient
from kde_ai.errors import RpcError

JSON_MODE = False


def parse_config_value(raw: str):
    """Decode a `config set` value. JSON if possible; otherwise the raw token.

    The plasmoid executable engine runs via a shell, which strips the quotes
    JSON.stringify() adds around a shortcut string like Meta+Ctrl+K.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def out(obj) -> None:
    if JSON_MODE:
        print(json.dumps(obj, ensure_ascii=False))
    elif isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(obj)


def _run_sudo(argv: list[str]) -> dict:
    if not sys.stdin.isatty():
        return {"ok": False, "cancelled": True, "stdout": "", "stderr": "no tty", "code": 1}
    try:
        proc = subprocess.run(["sudo", *argv], check=False, capture_output=True, text=True)
        return {
            "ok": proc.returncode == 0,
            "cancelled": proc.returncode == 1 or proc.returncode == 130,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "code": proc.returncode,
        }
    except FileNotFoundError:
        return {"ok": False, "cancelled": True, "stdout": "", "stderr": "sudo missing", "code": 127}


def connect(client: str = "cli") -> RpcClient:
    rpc = RpcClient()

    def on_notify(method: str, params: dict) -> None:
        if JSON_MODE:
            return
        if method == "stream.token":
            sys.stdout.write(params.get("text") or "")
            sys.stdout.flush()
        elif method == "stream.tool":
            name = params.get("name")
            if sys.stderr.isatty():
                print(f"\n[tool {name}]", file=sys.stderr)
        elif method == "stream.done":
            print()
        elif method == "issue.awaiting":
            print(
                f"\nIs the problem solved? [y/N]\n"
                f"  issue={params.get('issue_summary')}\n"
                f"  solution={params.get('solution_summary')}",
                file=sys.stderr,
            )
        elif method == "privilege.required":
            argv = params.get("argv") or []
            print(f"\nPrivilege required: {' '.join(argv)} ({params.get('reason')})", file=sys.stderr)
            res = _run_sudo(argv)
            try:
                rpc.call(
                    "privilege.complete",
                    {
                        "request_id": params.get("request_id"),
                        "ok": res.get("ok"),
                        "cancelled": res.get("cancelled"),
                        "stdout": res.get("stdout"),
                        "stderr": res.get("stderr"),
                        "code": res.get("code"),
                    },
                )
            except RpcError as exc:
                print(exc.message, file=sys.stderr)

    rpc.on_notify = on_notify
    rpc.connect()
    rpc.hello(client=client, auth="tty" if sys.stdin.isatty() else "none")
    return rpc


def _sid(rpc: RpcClient, args) -> str:
    if getattr(args, "session", None):
        return args.session
    st = rpc.call("status.get")
    sid = st.get("active_session_id")
    if sid:
        return sid
    created = rpc.call("session.create", {"title": "General"})
    return created["session_id"]


def _wait_stream(rpc: RpcClient) -> None:
    for _ in range(600):
        rpc.drain(0.2)
        if any(n.get("method") == "stream.done" for n in rpc.notifications):
            break
        time.sleep(0.05)


def collect_stream(notifications: list[dict]) -> dict:
    parts: list[str] = []
    done: dict = {}
    for note in notifications:
        method = note.get("method")
        params = note.get("params") or {}
        if method == "stream.token":
            parts.append(params.get("text") or "")
        elif method == "stream.done":
            done = params
    return {
        "text": "".join(parts),
        "reason": done.get("reason"),
        "error": done.get("error"),
    }


def _last_assistant_text(rpc: RpcClient, sid: str) -> str:
    try:
        transcript = rpc.call("session.transcript", {"session_id": sid, "limit": 40, "offset": 0})
    except RpcError:
        return ""
    for msg in reversed(transcript.get("messages") or []):
        if msg.get("role") == "assistant" and (msg.get("content") or "").strip():
            return str(msg.get("content") or "")
    return ""


def cmd_chat(rpc: RpcClient, args) -> int:
    sid = _sid(rpc, args)
    msg = " ".join(args.message or [])
    if not msg and not sys.stdin.isatty():
        msg = sys.stdin.read()
    if not msg:
        print("empty message", file=sys.stderr)
        return 2
    res = rpc.call("chat.send", {"session_id": sid, "message": msg, "issue_hint": bool(args.fix)})
    _wait_stream(rpc)
    stream = collect_stream(rpc.notifications)
    if not stream.get("text"):
        stream["text"] = _last_assistant_text(rpc, sid)
    if JSON_MODE:
        out({**res, **stream})
    return 0


def cmd_repl(rpc: RpcClient, args) -> int:
    from prompt_toolkit import PromptSession

    session = PromptSession("kde-ai> ")
    sid = _sid(rpc, args)
    print("Type /quit to exit. Prefix issues with /fix")
    while True:
        try:
            line = session.prompt()
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        if line.strip() in ("/quit", "/exit"):
            break
        fix = line.startswith("/fix ")
        text = line[5:] if fix else line
        st = rpc.call("status.get")
        if st.get("state") == "awaiting_confirm":
            yn = line.strip().lower()
            meta_sessions = rpc.call("session.list", {})
            sess = next(s for s in meta_sessions if s["id"] == sid)
            aid = sess.get("open_attempt_id")
            if yn in ("y", "yes"):
                rpc.call("issue.confirm", {"session_id": sid, "attempt_id": aid, "solved": True})
                print("saved")
                continue
            if yn in ("n", "no"):
                rpc.call(
                    "issue.confirm",
                    {"session_id": sid, "attempt_id": aid, "solved": False, "note": text},
                )
                continue
        rpc.notifications.clear()
        rpc.call("chat.send", {"session_id": sid, "message": text, "issue_hint": fix})
        _wait_stream(rpc)
    return 0


def main(argv: list[str] | None = None) -> None:
    global JSON_MODE
    parser = argparse.ArgumentParser(prog="kde-ai")
    parser.add_argument("--json", action="store_true", help="machine-readable JSON on stdout")
    sub = parser.add_subparsers(dest="cmd")
    pchat = sub.add_parser("chat")
    pchat.add_argument("--fix", action="store_true")
    pchat.add_argument("-s", "--session")
    pchat.add_argument("message", nargs="*")
    ps = sub.add_parser("sessions")
    ps.add_argument("action", choices=["list", "new", "rename", "delete", "archive", "use", "transcript"])
    ps.add_argument("rest", nargs="*")
    pm = sub.add_parser("memory")
    pm.add_argument(
        "action",
        choices=["clear", "summarize", "pins", "pin", "unpin", "solved", "forget", "stats", "export"],
    )
    pm.add_argument("rest", nargs="*")
    pm.add_argument("-s", "--session")
    pc = sub.add_parser("confirm")
    pc.add_argument("answer", choices=["yes", "no"])
    pc.add_argument("--note")
    pc.add_argument("-s", "--session")
    sub.add_parser("cancel-attempt")
    sub.add_parser("status")
    pdoc = sub.add_parser("doctor")
    pdoc.add_argument("--reindex", action="store_true")
    sub.add_parser("tools")
    psk = sub.add_parser("skills")
    psk.add_argument("action", choices=["list", "enable", "disable", "show", "install", "remove"])
    psk.add_argument("rest", nargs="*")
    pcfg = sub.add_parser("config")
    pcfg.add_argument("action", choices=["get", "set"])
    pcfg.add_argument("rest", nargs="*")
    psh = sub.add_parser("shortcut")
    psh.add_argument("rest", nargs="*")
    pbug = sub.add_parser("bug-report")
    pbug.add_argument("-s", "--session")
    args = parser.parse_args(argv)
    JSON_MODE = bool(args.json)
    rpc = connect()
    try:
        if args.cmd is None:
            raise SystemExit(cmd_repl(rpc, args))
        if args.cmd == "chat":
            raise SystemExit(cmd_chat(rpc, args))
        if args.cmd == "status":
            out(rpc.call("status.get"))
            return
        if args.cmd == "doctor":
            payload = {}
            if args.reindex:
                payload["reindex"] = rpc.call("rag.reindex", {"force": True})
            payload["doctor"] = rpc.call("doctor")
            out(payload if args.reindex else payload["doctor"])
            return
        if args.cmd == "tools":
            out(rpc.call("tools.list"))
            return
        if args.cmd == "bug-report":
            sid = _sid(rpc, args)
            out(rpc.call("session.bug_report", {"session_id": sid}))
            return
        if args.cmd == "cancel-attempt":
            st = rpc.call("status.get")
            out(rpc.call("issue.cancel", {"session_id": st["active_session_id"]}))
            return
        if args.cmd == "confirm":
            sid = _sid(rpc, args)
            sess = next(s for s in rpc.call("session.list", {}) if s["id"] == sid)
            out(
                rpc.call(
                    "issue.confirm",
                    {
                        "session_id": sid,
                        "attempt_id": sess.get("open_attempt_id"),
                        "solved": args.answer == "yes",
                        "note": args.note,
                    },
                )
            )
            return
        if args.cmd == "sessions":
            act = args.action
            if act == "list":
                out(rpc.call("session.list", {}))
            elif act == "new":
                title = " ".join(args.rest).strip() or None
                out(rpc.call("session.create", {"title": title}))
            elif act == "rename":
                rpc.call("session.rename", {"session_id": args.rest[0], "title": " ".join(args.rest[1:])})
                out({"ok": True})
            elif act == "delete":
                rpc.call("session.delete", {"session_id": args.rest[0]})
                out({"ok": True})
            elif act == "transcript":
                sid = args.rest[0] if args.rest else _sid(rpc, args)
                out(rpc.call("session.transcript", {"session_id": sid, "limit": 100, "offset": 0}))
            elif act == "archive":
                rpc.call("session.archive", {"session_id": args.rest[0], "archived": True})
                out({"ok": True})
            elif act == "use":
                rpc.call("session.set_active", {"session_id": args.rest[0]})
                out({"ok": True})
            return
        if args.cmd == "memory":
            sid = _sid(rpc, args)
            act = args.action
            if act == "clear":
                rpc.call(
                    "memory.clear",
                    {"session_id": sid, "scope": args.rest[0] if args.rest else "working"},
                )
                out({"ok": True})
            elif act == "summarize":
                rpc.call("memory.summarize", {"session_id": sid})
                out({"ok": True})
            elif act == "pins":
                out(rpc.call("memory.pins", {"session_id": sid}))
            elif act == "pin":
                out(rpc.call("memory.pin", {"session_id": sid, "text": " ".join(args.rest)}))
            elif act == "unpin":
                rpc.call("memory.unpin", {"session_id": sid, "pin_id": args.rest[0]})
                out({"ok": True})
            elif act == "solved":
                out(rpc.call("memory.solved", {"session_id": sid}))
            elif act == "forget":
                rpc.call("memory.forget_solved", {"session_id": sid, "solved_id": args.rest[0]})
                out({"ok": True})
            elif act == "stats":
                out(rpc.call("memory.stats", {"session_id": sid}))
            elif act == "export":
                out(rpc.call("session.export", {"session_id": sid}))
            return
        if args.cmd == "skills":
            act = args.action
            if act == "list":
                out(rpc.call("skills.list", {}))
            elif act == "enable":
                rpc.call("skills.set_enabled", {"id": args.rest[0], "enabled": True})
                out({"ok": True})
            elif act == "disable":
                rpc.call("skills.set_enabled", {"id": args.rest[0], "enabled": False})
                out({"ok": True})
            elif act == "show":
                out(rpc.call("skills.get", {"id": args.rest[0]}))
            elif act == "install":
                out(rpc.call("skills.install", {"path": args.rest[0]}))
            elif act == "remove":
                rpc.call("skills.remove", {"id": args.rest[0]})
                out({"ok": True})
            return
        if args.cmd == "config":
            if args.action == "get":
                out(rpc.call("config.get"))
            else:
                if not args.rest:
                    print("config set KEY VALUE", file=sys.stderr)
                    raise SystemExit(2)
                key = args.rest[0]
                value = parse_config_value(" ".join(args.rest[1:]))
                rpc.call("config.set", {"patch": {key: value}})
                out({"ok": True})
            return
        if args.cmd == "shortcut":
            raw = " ".join(args.rest).strip()
            if raw.lower() in ("get", "show", ""):
                cfg = rpc.call("config.get")
                out({"shortcut": (cfg.get("plasma") or {}).get("global_shortcut") or ""})
                return
            if raw.lower() in ("clear", "none", "off"):
                raw = ""
            elif raw.lower().startswith("set "):
                raw = raw[4:].strip()
            rpc.call("config.set", {"patch": {"plasma.global_shortcut": raw}})
            out({"ok": True, "shortcut": raw})
            return
    except RpcError as exc:
        if JSON_MODE:
            print(json.dumps({"error": exc.code, "message": exc.message, "data": exc.data}))
        else:
            print(f"{exc.code}: {exc.message}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        rpc.close()


if __name__ == "__main__":
    main()
