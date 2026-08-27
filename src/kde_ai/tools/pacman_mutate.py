from __future__ import annotations

from kde_ai.errors import IRREVERSIBLE, TOOL_DENIED, VALIDATION, RpcError
from kde_ai.tools import PKG_RE, run_argv
from kde_ai.undo import append_undo


def _check_pkgs(pkgs: list) -> list[str]:
    if not isinstance(pkgs, list) or not pkgs or len(pkgs) > 10:
        raise RpcError(VALIDATION, "1-10 packages required")
    out = []
    for p in pkgs:
        if not isinstance(p, str) or not PKG_RE.match(p):
            raise RpcError(VALIDATION, f"invalid package {p}")
        out.append(p)
    return out


def handle(args: dict, ctx) -> dict:
    action = args.get("action")
    if action not in ("install", "remove"):
        raise RpcError(TOOL_DENIED, "only install/remove; no -Syu")
    pkgs = _check_pkgs(args.get("pkgs") or [])
    snapshot = run_argv(["pacman", "-Qq"], timeout=30)
    installed = set((snapshot.get("stdout") or "").split())
    if action == "install":
        argv = ["pacman", "-S", "--noconfirm", *pkgs]
        was_new = [p for p in pkgs if p not in installed]
        if ctx.attempt_dir:
            append_undo(
                ctx.attempt_dir,
                {"op": "pacman", "action": "remove", "pkgs": was_new, "was_new": True},
            )
    else:
        argv = ["pacman", "-R", "--noconfirm", *pkgs]
        if ctx.attempt_dir:
            append_undo(
                ctx.attempt_dir,
                {"op": "pacman", "action": "install", "pkgs": pkgs, "was_new": False},
            )
    return ctx.request_privilege(argv, f"pacman {action} {pkgs}")


def undo_pacman(op: dict) -> None:
    pkgs = op.get("pkgs") or []
    if not pkgs:
        return
    action = op.get("action")
    if action == "remove":
        r = run_argv(["pacman", "-R", "--noconfirm", *pkgs], timeout=120)
    else:
        r = run_argv(["pacman", "-S", "--noconfirm", *pkgs], timeout=120)
    if not r.get("ok"):
        raise RpcError(IRREVERSIBLE, r.get("stderr") or "pacman undo failed")


SCHEMA = {
    "name": "pacman_mutate",
    "description": "Install or remove packages after privilege confirmation",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["install", "remove"]},
            "pkgs": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action", "pkgs"],
    },
}
