from __future__ import annotations

import json
import uuid

from kde_ai.errors import VALIDATION, RpcError
from kde_ai.sessions import SessionStore
from kde_ai.undo import replay_undo

PATTERNS_DEFAULT = [
    "crash",
    "broken",
    "doesn't work",
    "does not work",
    "won't",
    "failed",
    "error",
    "regression",
    "after update",
    "after upgrade",
    "black screen",
    "no audio",
]


def looks_like_issue(text: str, patterns: list[str] | None = None) -> bool:
    t = text.lower()
    for p in patterns or PATTERNS_DEFAULT:
        if p.lower() in t:
            return True
    return False


class IssueManager:
    def __init__(self, store: SessionStore, max_attempts: int = 3) -> None:
        self.store = store
        self.max_attempts = max_attempts

    def enter(self, sid: str, user_text: str) -> dict:
        meta = self.store.load_meta(sid)
        meta["issue_mode"] = True
        if not meta.get("open_attempt_id"):
            if meta.get("attempt_count", 0) >= self.max_attempts:
                raise RpcError(VALIDATION, "max attempts reached")
            aid = str(uuid.uuid4())
            meta["open_attempt_id"] = aid
            meta["attempt_count"] = int(meta.get("attempt_count") or 0) + 1
            meta["issue_text"] = user_text
            d = self.store.attempt_dir(sid, aid)
            (d / "meta.json").write_text(
                json.dumps({"id": aid, "issue": user_text, "status": "open"}, indent=2),
                encoding="utf-8",
            )
        self.store.save_meta(meta)
        return meta

    def confirm(self, sid: str, attempt_id: str, solved: bool, note: str | None, solution: str) -> dict:
        meta = self.store.load_meta(sid)
        if meta.get("open_attempt_id") != attempt_id:
            raise RpcError(VALIDATION, "attempt mismatch")
        d = self.store.attempt_dir(sid, attempt_id)
        if solved:
            row = {
                "id": str(uuid.uuid4()),
                "issue": meta.get("issue_text") or "",
                "solution": solution,
                "tools": [],
                "attempt_id": attempt_id,
                "ts": meta.get("updated_at"),
            }
            self.store.append_solved(sid, row)
            undo = d / "undo.jsonl"
            if undo.exists():
                undo.write_text("", encoding="utf-8")
            meta["issue_mode"] = False
            meta["open_attempt_id"] = None
            meta["attempt_count"] = 0
            self.store.save_meta(meta)
            return {"ok": True, "next": "solved"}
        replay_undo(d)
        failed = {"note": note or "", "solution": solution}
        (d / "failed.json").write_text(json.dumps(failed, indent=2), encoding="utf-8")
        meta["open_attempt_id"] = None
        if int(meta.get("attempt_count") or 0) >= self.max_attempts:
            meta["issue_mode"] = False
            self.store.save_meta(meta)
            return {"ok": True, "next": "max_attempts"}
        self.store.save_meta(meta)
        return {"ok": True, "next": "retry"}

    def cancel(self, sid: str) -> dict:
        meta = self.store.load_meta(sid)
        aid = meta.get("open_attempt_id")
        if aid:
            replay_undo(self.store.attempt_dir(sid, aid))
        meta["issue_mode"] = False
        meta["open_attempt_id"] = None
        meta["attempt_count"] = 0
        self.store.save_meta(meta)
        return {"ok": True}
