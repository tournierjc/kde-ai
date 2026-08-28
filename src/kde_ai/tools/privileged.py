from __future__ import annotations

import re

from kde_ai.errors import TOOL_DENIED, VALIDATION, RpcError
from kde_ai.tools import UNIT_RE, clip
from kde_ai.undo import append_undo

ALLOW = {
    "id": ["id"],
    "systemctl_status_unit": ["systemctl", "status", "--no-pager"],
    "journalctl_system_n": ["journalctl", "-n", "50", "--no-pager"],
    "dmesg": ["dmesg", "-T"],
    "nft_list_ruleset": ["nft", "list", "ruleset"],
}

_NETFILTER_LOOKUP_RE = re.compile(
    r"(?:what|which|show|list|dump|print)\b.{0,60}\b(?:iptables?|nftables|\bnft\b|ruleset|firewall\s+rules?)\b|"
    r"\b(?:iptables?|nftables|\bnft\b|netfilter)\b.{0,40}\b(?:rules?|ruleset|chains?)\b|"
    r"custom rules.{0,30}\b(?:iptables?|nftables|\bnft\b|firewall)\b|"
    r"\bin my (?:iptables?|nftables|\bnft\b)\b",
    re.I,
)

_NETFILTER_FALLBACK = (
    "Live filter/NAT rules are nftables on CachyOS (`nft list ruleset`); "
    "iptables-nft is only a compat view. I can list that ruleset after you "
    "authenticate. I will not invent iptables rules or run ip route."
)


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


def is_netfilter_lookup(text: str) -> bool:
    return bool(_NETFILTER_LOOKUP_RE.search(text or ""))


def summarize_nft(payload: dict | None) -> str:
    if not payload:
        return _NETFILTER_FALLBACK
    err = (payload.get("error") or "") + " " + (payload.get("message") or "")
    if payload.get("error") in {"PRIVILEGE_CANCELLED", "PRIVILEGE_TIMEOUT"} or "cancelled" in err.lower():
        return (
            "Listing the live ruleset needs authentication (`nft list ruleset`). "
            "I will not invent iptables/nft rules or run ip route."
        )
    stderr = (payload.get("stderr") or "").strip()
    stdout = (payload.get("stdout") or "").strip()
    if not payload.get("ok"):
        if "not found" in stderr.lower() or payload.get("code") == 127:
            return (
                "nft is not installed, so I cannot list the kernel ruleset. "
                "This host may still be on iptables-legacy."
            )
        if stderr:
            return f"nft list ruleset failed: {stderr}"
        if payload.get("message"):
            return str(payload["message"])
        return _NETFILTER_FALLBACK
    if not stdout:
        return (
            "nft list ruleset is empty — no tables loaded, so there are no custom "
            "iptables/nft rules. CachyOS uses nftables; iptables-nft would show the same."
        )
    return (
        "Live netfilter (nftables; iptables-nft is a compat shim), not ip route:\n" + stdout
    )


def prefer_netfilter_reply(user_text: str, model_text: str, payload: dict | None) -> str:
    if not is_netfilter_lookup(user_text):
        return model_text
    return summarize_nft(payload)


SCHEMA = {
    "name": "run_privileged_cmd",
    "description": (
        "Allowlisted admin command after the user authenticates: id, "
        "systemctl_status_unit, journalctl_system_n, dmesg, nft_list_ruleset "
        "(live nftables ruleset; iptables-nft is a shim). Fixed argv only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "unit": {"type": "string"},
        },
        "required": ["name"],
    },
}
