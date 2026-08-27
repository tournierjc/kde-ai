from __future__ import annotations

from kde_ai.errors import TOOL_DENIED, RpcError
from kde_ai.tools import run_argv
from kde_ai.undo import append_undo


def _kread(file: str, group: str, key: str) -> str:
    r = run_argv(["kreadconfig6", "--file", file, "--group", group, "--key", key])
    return (r.get("stdout") or "").strip()


def restore_kwriteconfig(op: dict) -> None:
    run_argv(
        [
            "kwriteconfig6",
            "--file",
            op["file"],
            "--group",
            op["group"],
            "--key",
            op["key"],
            op.get("old") or "",
        ]
    )
    run_argv(["qdbus", "org.kde.KWin", "/KWin", "reconfigure"], timeout=10)


def handle(args: dict, ctx) -> dict:
    name = args.get("name")
    if name == "kwin_compositing":
        values = args.get("values") or {}
        enabled = str(values.get("Enabled", "true"))
        old = _kread("kwinrc", "Compositing", "Enabled")
        if ctx.attempt_dir:
            append_undo(
                ctx.attempt_dir,
                {
                    "op": "kwriteconfig",
                    "file": "kwinrc",
                    "group": "Compositing",
                    "key": "Enabled",
                    "old": old,
                },
            )
        run_argv(
            [
                "kwriteconfig6",
                "--file",
                "kwinrc",
                "--group",
                "Compositing",
                "--key",
                "Enabled",
                enabled,
            ]
        )
        run_argv(["qdbus", "org.kde.KWin", "/KWin", "reconfigure"], timeout=10)
        return {"ok": True, "old": old, "new": enabled}
    if name == "plasma_restart":
        if ctx.attempt_dir:
            append_undo(ctx.attempt_dir, {"op": "noop", "reason": "plasma_restart"})
        run_argv(["kquitapp6", "plasmashell"], timeout=15)
        r = run_argv(["kstart", "plasmashell"], timeout=15)
        if r.get("code") == 127:
            r = run_argv(["kstart5", "plasmashell"], timeout=15)
        return {"ok": True, "warn": "restart is not auto-undone"}
    if name == "notify_test":
        if ctx.attempt_dir:
            append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
        return run_argv(["notify-send", "kde-ai", "Test notification"])
    raise RpcError(TOOL_DENIED, f"unknown plasma script {name}")


SCHEMA = {
    "name": "plasma_script",
    "description": "Allowlisted Plasma/KWin actions",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "values": {"type": "object"},
        },
        "required": ["name"],
    },
}
