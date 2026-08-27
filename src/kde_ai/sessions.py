from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from kde_ai.errors import NOT_FOUND, VALIDATION, RpcError
from kde_ai.paths import exports_dir, sessions_dir


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


class SessionStore:
    def __init__(self, max_sessions: int = 50) -> None:
        self.max_sessions = max_sessions
        self.active_id: str | None = None
        sessions_dir().mkdir(parents=True, exist_ok=True)
        self._ensure_general()

    def root(self, sid: str) -> Path:
        return sessions_dir() / sid

    def meta_path(self, sid: str) -> Path:
        return self.root(sid) / "meta.json"

    def load_meta(self, sid: str) -> dict:
        p = self.meta_path(sid)
        if not p.exists():
            raise RpcError(NOT_FOUND, "session not found")
        return _read_json(p, {})

    def save_meta(self, meta: dict) -> None:
        meta["updated_at"] = _now()
        _write_json(self.meta_path(meta["id"]), meta)

    def _ensure_general(self) -> None:
        existing = list(self.list_sessions(include_archived=True))
        if existing:
            if self.active_id is None:
                self.active_id = existing[0]["id"]
            return
        self.create("General")

    def create(self, title: str | None = None) -> dict:
        sid = str(uuid.uuid4())
        root = self.root(sid)
        root.mkdir(parents=True, exist_ok=True)
        (root / "attempts").mkdir(exist_ok=True)
        meta = {
            "id": sid,
            "title": title or "New session",
            "created_at": _now(),
            "updated_at": _now(),
            "archived": False,
            "issue_mode": False,
            "open_attempt_id": None,
            "attempt_count": 0,
            "locale": None,
            "skills_enabled": {},
            "overflow": False,
        }
        _write_json(self.meta_path(sid), meta)
        _write_json(root / "pins.json", [])
        (root / "transcript.jsonl").touch()
        (root / "solved.jsonl").touch()
        (root / "summary.md").write_text("", encoding="utf-8")
        self.active_id = sid
        self._enforce_cap()
        return meta

    def _enforce_cap(self) -> None:
        items = [m for m in self.list_sessions(include_archived=True) if not m.get("archived")]
        if len(items) <= self.max_sessions:
            return
        items.sort(key=lambda m: m.get("updated_at") or "")
        for m in items:
            if m["id"] == self.active_id:
                continue
            if not m.get("archived"):
                m["archived"] = True
                self.save_meta(m)
                if sum(1 for x in self.list_sessions(False) if not x.get("archived")) <= self.max_sessions:
                    break

    def list_sessions(self, include_archived: bool = False) -> list[dict]:
        out = []
        if not sessions_dir().is_dir():
            return out
        for p in sessions_dir().iterdir():
            if not (p / "meta.json").exists():
                continue
            meta = _read_json(p / "meta.json", {})
            if not include_archived and meta.get("archived"):
                continue
            trans = p / "transcript.jsonl"
            n = 0
            if trans.exists():
                n = sum(1 for _ in trans.open(encoding="utf-8") if _.strip())
            pins = _read_json(p / "pins.json", [])
            meta["message_count"] = n
            meta["pinned_count"] = len(pins)
            out.append(meta)
        out.sort(key=lambda m: m.get("updated_at") or "", reverse=True)
        return out

    def rename(self, sid: str, title: str) -> None:
        meta = self.load_meta(sid)
        meta["title"] = title
        self.save_meta(meta)

    def delete(self, sid: str) -> None:
        root = self.root(sid)
        if not root.exists():
            raise RpcError(NOT_FOUND, "session not found")
        shutil.rmtree(root)
        if self.active_id == sid:
            rest = self.list_sessions()
            self.active_id = rest[0]["id"] if rest else None
            if self.active_id is None:
                self._ensure_general()

    def archive(self, sid: str, archived: bool) -> None:
        meta = self.load_meta(sid)
        meta["archived"] = bool(archived)
        self.save_meta(meta)

    def set_active(self, sid: str) -> None:
        self.load_meta(sid)
        self.active_id = sid

    def transcript(self, sid: str, limit: int = 100, offset: int = 0) -> dict:
        path = self.root(sid) / "transcript.jsonl"
        rows = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        total = len(rows)
        return {"messages": rows[offset : offset + limit], "total": total}

    def append_turn(self, sid: str, msg: dict) -> None:
        _append_jsonl(self.root(sid) / "transcript.jsonl", msg)
        meta = self.load_meta(sid)
        if meta.get("title") in ("New session", "General") and msg.get("role") == "user":
            text = (msg.get("content") or "")[:60]
            if text:
                meta["title"] = text
        self.save_meta(meta)

    def working_messages(self, sid: str) -> list[dict]:
        return self.transcript(sid, limit=10_000)["messages"]

    def pins(self, sid: str) -> list[dict]:
        return _read_json(self.root(sid) / "pins.json", [])

    def save_pins(self, sid: str, pins: list[dict]) -> None:
        _write_json(self.root(sid) / "pins.json", pins)

    def solved(self, sid: str) -> list[dict]:
        path = self.root(sid) / "solved.jsonl"
        rows = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def append_solved(self, sid: str, row: dict) -> None:
        _append_jsonl(self.root(sid) / "solved.jsonl", row)

    def summary(self, sid: str) -> str:
        p = self.root(sid) / "summary.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def set_summary(self, sid: str, text: str) -> None:
        (self.root(sid) / "summary.md").write_text(text, encoding="utf-8")

    def export(self, sid: str, path: str | None = None) -> str:
        dest = Path(path).expanduser() if path else exports_dir() / f"{sid}.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = self.root(sid) / "transcript.jsonl"
        dest.write_text(src.read_text(encoding="utf-8") if src.exists() else "", encoding="utf-8")
        return str(dest)

    def clear_memory(self, sid: str, scope: str) -> None:
        meta = self.load_meta(sid)
        if scope == "working":
            (self.root(sid) / "transcript.jsonl").write_text("", encoding="utf-8")
        elif scope == "summary":
            self.set_summary(sid, "")
        elif scope == "pins":
            self.save_pins(sid, [])
        elif scope == "solved":
            (self.root(sid) / "solved.jsonl").write_text("", encoding="utf-8")
        elif scope == "all":
            for s in ("working", "summary", "pins", "solved"):
                self.clear_memory(sid, s)
            meta["issue_mode"] = False
            meta["open_attempt_id"] = None
            meta["attempt_count"] = 0
            self.save_meta(meta)
            att = self.root(sid) / "attempts"
            if att.exists():
                shutil.rmtree(att)
                att.mkdir()
        else:
            raise RpcError(VALIDATION, f"unknown memory scope {scope}")

    def forget_solved(self, sid: str, solved_id: str) -> None:
        rows = [r for r in self.solved(sid) if r.get("id") != solved_id]
        path = self.root(sid) / "solved.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def bug_report(self, sid: str) -> str:
        meta = self.load_meta(sid)
        journal = ""
        trans = self.transcript(sid, 400)["messages"]
        for m in trans:
            if m.get("role") == "tool" and m.get("name") == "run_readonly_cmd":
                journal = str(m.get("content") or "")[:4000]
        attempts = []
        att = self.root(sid) / "attempts"
        if att.is_dir():
            for d in sorted(att.iterdir()):
                mp = d / "meta.json"
                fp = d / "failed.json"
                line = d.name
                if mp.exists():
                    line += " " + mp.read_text(encoding="utf-8")[:400]
                if fp.exists():
                    line += " failed=" + fp.read_text(encoding="utf-8")[:400]
                attempts.append(line)
        return (
            "# kde-ai bug report\n\n"
            f"- session: {sid}\n"
            f"- title: {meta.get('title')}\n"
            f"- issue_mode: {meta.get('issue_mode')}\n"
            f"- issue: {meta.get('issue_text') or ''}\n\n"
            "## Attempts\n"
            + ("\n".join(attempts) if attempts else "(none)")
            + "\n\n## Last readonly journal (if fetched)\n```\n"
            + journal
            + "\n```\n"
        )

    def attempt_dir(self, sid: str, aid: str) -> Path:
        p = self.root(sid) / "attempts" / aid
        p.mkdir(parents=True, exist_ok=True)
        return p
