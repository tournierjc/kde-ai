from __future__ import annotations

from kde_ai.errors import TOOL_DENIED, VALIDATION, RpcError
from kde_ai.tools import UNIT_RE, clip
from kde_ai.undo import append_undo

ALLOW = {
    "id": ["id"],
    "systemctl_status_unit": ["systemctl", "status", "--no-pager"],
    "journalctl_system_n": ["journalctl", "-n", "50", "--no-pager"],
    "dmesg": ["dmesg", "-T"],
}


def argv_for(name: str, args: dict) -> list[str]:
    if name not in ALLOW:
        raise RpcError(TOOL_DENIED, f"unknown privileged command {name}")
    argv = list(ALLOW[name])
    if name == "systemctl_status_unit":
        unit = args.get("unit") or ""
        if not UNIT_RE.match(unit):
            raise RpcError(VALIDATION, "invalid unit")
        argv.append(unit)
    return argv


def handle(args: dict, ctx) -> dict:
    name = args.get("name")
    argv = argv_for(name, args)
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    r = ctx.request_privilege(argv, f"privileged {name}")
    r["stdout"] = clip(r.get("stdout") or "", ctx.tool_result_chars)
    r["stderr"] = clip(r.get("stderr") or "", ctx.tool_result_chars)
    return r


SCHEMA = {
    "name": "run_privileged_cmd",
    "description": "Run an allowlisted admin command after the user authenticates",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "unit": {"type": "string"},
        },
        "required": ["name"],
    },
}
