from __future__ import annotations

from kde_ai.errors import VALIDATION, RpcError
from kde_ai.undo import append_undo


def handle(args: dict, ctx) -> dict:
    if not ctx.store.load_meta(ctx.session_id).get("issue_mode"):
        return {"ok": True, "ignored_not_issue_mode": True}
    issue = args.get("issue_summary") or ""
    solution = args.get("solution_summary") or ""
    if not issue or not solution:
        raise RpcError(VALIDATION, "issue_summary and solution_summary required")
    meta = ctx.store.load_meta(ctx.session_id)
    aid = meta.get("open_attempt_id")
    ctx.notify(
        "issue.awaiting",
        {
            "session_id": ctx.session_id,
            "attempt_id": aid,
            "issue_summary": issue,
            "solution_summary": solution,
        },
    )
    meta["pending_solution"] = solution
    ctx.store.save_meta(meta)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    return {"ok": True, "awaiting_confirm": True}


SCHEMA = {
    "name": "propose_solved",
    "description": "Propose that the current issue is solved; user must confirm",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_summary": {"type": "string"},
            "solution_summary": {"type": "string"},
        },
        "required": ["issue_summary", "solution_summary"],
    },
}
