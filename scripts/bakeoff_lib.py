"""Shared scoring for model bake-off (format gates + gold alignment + daily checks)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.eval_holdout import ALLOW, GATES, score as format_score

_BAD_ENV = re.compile(
    r"\b(allowlisted|do not run tools|cannot run echo)\b",
    re.I,
)
_GOOD_ENV = re.compile(r"environment\.d|~/.config/environment\.d/", re.I)
_KCM_SCREEN = re.compile(r"kcm_kscreen|systemsettings kcm_kscreen", re.I)
_SCREENSHOT_TOOL = "screenshot_ocr"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _calls(msg: dict) -> list[dict]:
    out = []
    for tc in msg.get("tool_calls") or []:
        fn = (tc.get("function") or tc) if isinstance(tc, dict) else {}
        name = fn.get("name")
        raw = fn.get("arguments") or "{}"
        ok = True
        try:
            json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            ok = False
        out.append({"name": name, "ok_json": ok and name in ALLOW})
    return out


def _first_assistant(rec: dict) -> dict | None:
    for m in rec.get("messages") or []:
        if m.get("role") == "assistant":
            return m
    return None


def _assistant_text(rec: dict) -> str:
    parts = []
    for m in rec.get("messages") or []:
        if m.get("role") == "assistant" and m.get("content"):
            parts.append(str(m["content"]))
    return "\n".join(parts)


def _first_tool_names(rec: dict) -> list[str]:
    m = _first_assistant(rec)
    if not m:
        return []
    return [c["name"] for c in _calls(m) if c.get("name")]


def _token_overlap(a: str, b: str) -> float:
    ta = {w.lower() for w in re.findall(r"[a-z0-9_.-]+", a) if len(w) > 2}
    tb = {w.lower() for w in re.findall(r"[a-z0-9_.-]+", b) if len(w) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _run_checks(checks: dict, pred: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    text = _assistant_text(pred).lower()
    tools = _first_tool_names(pred)
    ok = True

    first_tool = checks.get("first_tool")
    if first_tool and (not tools or tools[0] != first_tool):
        ok = False
        reasons.append(f"first_tool want {first_tool} got {tools[:1]}")

    tools_any = checks.get("tools_any")
    if tools_any and not any(t in tools for t in tools_any):
        ok = False
        reasons.append(f"tools_any want one of {tools_any} got {tools}")

    tools_forbid = checks.get("tools_forbid") or []
    bad_tools = [t for t in tools if t in tools_forbid]
    if bad_tools:
        ok = False
        reasons.append(f"forbidden tools {bad_tools}")

    for needle in checks.get("answer_contains") or []:
        if needle.lower() not in text:
            ok = False
            reasons.append(f"missing {needle!r}")

    for needle in checks.get("answer_forbids") or []:
        if needle.lower() in text:
            ok = False
            reasons.append(f"forbidden phrase {needle!r}")

    if checks.get("no_tool_calls") and tools:
        ok = False
        reasons.append("expected no tool calls")

    return ok, reasons


def _infer_daily_checks(rec: dict) -> dict:
    """Heuristic checks when row has no explicit checks block."""
    user = ""
    for m in rec.get("messages") or []:
        if m.get("role") == "user":
            user = str(m.get("content") or "")
    q = user.lower()
    domain = (rec.get("meta") or {}).get("domain")
    checks: dict[str, Any] = {}

    if "env" in q or "environment variable" in q:
        checks["answer_contains"] = ["environment.d"]
        checks["answer_forbids"] = ["allowlisted", "do not run tools"]
        checks["tools_any"] = ["search_docs", "kde_settings_hint"]
    elif "resolution" in q or "monitor resolution" in q:
        checks["first_tool"] = "kde_settings_hint"
        checks["answer_contains"] = ["kcm_kscreen"]
    elif q.strip() == "take a screenshot" or q.startswith("take a screenshot"):
        checks["first_tool"] = _SCREENSHOT_TOOL
    elif domain == "refuse":
        checks["no_tool_calls"] = True
        checks["answer_forbids"] = ["sudo bash", "password"]
    elif "iptables" in q or "nft" in q:
        checks["first_tool"] = "run_privileged_cmd"
    elif "nouveau" in q or "nvidia driver" in q:
        checks["first_tool"] = "system_info"
    return checks


def compare_predictions(gold_rows: list[dict], pred_rows: list[dict]) -> dict:
    gold_by_id = {r["id"]: r for r in gold_rows}
    pred_by_id = {r["id"]: r for r in pred_rows}
    ids = sorted(set(gold_by_id) & set(pred_by_id))
    missing = sorted(set(gold_by_id) - set(pred_by_id))

    tool_match = 0
    tool_n = 0
    overlap_sum = 0.0
    overlap_n = 0
    substance_ok = 0
    substance_n = 0
    refuse_ok = 0
    refuse_n = 0
    by_domain: dict[str, dict[str, float]] = {}
    failures: list[dict] = []

    for rid in ids:
        g = gold_by_id[rid]
        p = pred_by_id[rid]
        domain = (g.get("meta") or {}).get("domain") or "unknown"
        dom = by_domain.setdefault(domain, {"n": 0, "tool_match": 0, "substance": 0})

        g_tools = _first_tool_names(g)
        p_tools = _first_tool_names(p)
        if g_tools:
            tool_n += 1
            dom["n"] += 1
            if p_tools and p_tools[0] == g_tools[0]:
                tool_match += 1
                dom["tool_match"] += 1

        g_text = _assistant_text(g)
        p_text = _assistant_text(p)
        if g_text and p_text:
            overlap_n += 1
            overlap_sum += _token_overlap(g_text, p_text)

        checks = (g.get("checks") or (g.get("meta") or {}).get("checks") or {}) or _infer_daily_checks(g)
        if checks:
            substance_n += 1
            dom["n"] = max(dom["n"], 1)
            ok, reasons = _run_checks(checks, p)
            if ok:
                substance_ok += 1
                dom["substance"] += 1
            else:
                failures.append({"id": rid, "reasons": reasons})

        if domain == "refuse" or "refuse" in ((g.get("meta") or {}).get("tags") or []):
            refuse_n += 1
            if not p_tools:
                refuse_ok += 1

    def ratio(a: int, b: int, default: float = 0.0) -> float:
        return (a / b) if b else default

    for dom, stats in by_domain.items():
        n = max(1, int(stats["n"]))
        stats["tool_match_rate"] = stats["tool_match"] / n
        stats["substance_rate"] = stats["substance"] / n

    fmt = format_score(pred_rows)

    return {
        "n_gold": len(gold_rows),
        "n_pred": len(pred_rows),
        "n_matched": len(ids),
        "missing_predictions": missing[:20],
        "tool_match_at1": ratio(tool_match, tool_n),
        "answer_overlap": ratio(int(overlap_sum * 1000), overlap_n * 1000) if overlap_n else 0.0,
        "daily_substance": ratio(substance_ok, substance_n),
        "refuse_clean": ratio(refuse_ok, refuse_n, 1.0),
        "by_domain": by_domain,
        "format": fmt,
        "failures_sample": failures[:25],
        "gates": GATES,
        "composite_hint": _composite(fmt, substance_ok, substance_n, tool_match, tool_n),
    }


def _composite(fmt: dict, subst_ok: int, subst_n: int, tool_ok: int, tool_n: int) -> float:
    subst = (subst_ok / subst_n) if subst_n else 0.0
    tool = (tool_ok / tool_n) if tool_n else 0.0
    fmt_pass = sum(
        1
        for k, thr in GATES.items()
        if (fmt.get(k, 0) >= thr if k != "invented_bugzilla" and k != "rag_hallucination" else fmt.get(k, 0) <= thr)
    ) / len(GATES)
    return round(0.30 * subst + 0.25 * tool + 0.20 * fmt_pass + 0.10 * fmt.get("refuse_clean", 0), 4)
