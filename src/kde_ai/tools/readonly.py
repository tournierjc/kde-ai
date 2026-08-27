from __future__ import annotations

from kde_ai.errors import TOOL_DENIED, VALIDATION, RpcError
from kde_ai.tools import PKG_RE, clip, run_argv
from kde_ai.undo import append_undo

ALLOW = {
    "user_systemctl_status": ["systemctl", "--user", "status", "--no-pager"],
    "pacman_qi": ["pacman", "-Qi"],
    "pacman_qs": ["pacman", "-Qs"],
    "journal_user": ["journalctl", "--user", "-n", "50", "--no-pager"],
    "journal_kernel": ["journalctl", "-k", "-n", "50", "--no-pager"],
    "lspci_vga": ["lspci", "-nnk"],
    "echo_session": ["printenv", "XDG_SESSION_TYPE"],
}


def handle(args: dict, ctx) -> dict:
    name = args.get("name")
    if name not in ALLOW:
        raise RpcError(TOOL_DENIED, f"unknown readonly command {name}")
    argv = list(ALLOW[name])
    if name in ("pacman_qi", "pacman_qs"):
        pkg = args.get("pkg")
        if pkg:
            if not isinstance(pkg, str) or not PKG_RE.match(pkg):
                raise RpcError(VALIDATION, "invalid package name")
            argv.append(pkg)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    r = run_argv(argv)
    r["stdout"] = clip(r.get("stdout") or "", ctx.tool_result_chars)
    r["stderr"] = clip(r.get("stderr") or "", ctx.tool_result_chars)
    return r


SCHEMA = {
    "name": "run_readonly_cmd",
    "description": "Run an allowlisted read-only command by name",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "pkg": {"type": "string"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}
