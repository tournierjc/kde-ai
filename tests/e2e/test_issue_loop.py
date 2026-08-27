from __future__ import annotations

from kde_ai.errors import RpcError
from kde_ai.issue import IssueManager
from kde_ai.sessions import SessionStore


def test_issue_max_attempts(xdg):
    store = SessionStore(10)
    im = IssueManager(store, max_attempts=3)
    sid = store.create("fix")["id"]
    im.enter(sid, "crash")
    meta = store.load_meta(sid)
    assert meta["attempt_count"] == 1
    im.confirm(sid, meta["open_attempt_id"], False, "still broken", "tried a")
    im.enter(sid, "crash")
    meta = store.load_meta(sid)
    im.confirm(sid, meta["open_attempt_id"], False, "no", "tried b")
    im.enter(sid, "crash")
    meta = store.load_meta(sid)
    im.confirm(sid, meta["open_attempt_id"], False, "no", "tried c")
    try:
        im.enter(sid, "crash")
        assert False, "4th attempt must be blocked"
    except RpcError as exc:
        assert exc.code == "VALIDATION"


def test_confirm_yes_writes_solved(xdg):
    store = SessionStore(10)
    im = IssueManager(store, 3)
    sid = store.create("fix")["id"]
    im.enter(sid, "no audio")
    aid = store.load_meta(sid)["open_attempt_id"]
    im.confirm(sid, aid, True, None, "unmuted")
    rows = store.solved(sid)
    assert len(rows) == 1
    assert rows[0]["solution"] == "unmuted"
    assert store.load_meta(sid)["issue_mode"] is False
