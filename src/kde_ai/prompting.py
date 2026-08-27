from __future__ import annotations

from kde_ai.paths import package_root


def load_system_prompt(locale: str = "en_US") -> str:
    text = (package_root() / "prompts" / "system.txt").read_text(encoding="utf-8")
    return text.strip() + f"\nuser_locale: {locale}\n"


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def clip_tokens(text: str, budget: int) -> str:
    if approx_tokens(text) <= budget:
        return text
    # 4 chars ≈ 1 token
    return text[: max(0, budget * 4)]


def assemble(
    *,
    system: str,
    skill_bodies: list[str],
    solved: list[dict],
    pins: list[dict],
    summary: str,
    rag_bits: list[str],
    working: list[dict],
    failed_notes: str,
    caps: dict,
    ctx: int = 4096,
) -> tuple[str, list[dict], dict]:
    stats = {
        "system_tokens": approx_tokens(system),
        "skill_tokens": sum(approx_tokens(s) for s in skill_bodies),
        "solved_tokens": 0,
        "pin_tokens": 0,
        "summary_tokens": 0,
        "rag_tokens": 0,
        "working_tokens": 0,
        "budget": ctx,
        "overflow": False,
    }
    parts = [system]
    for body in skill_bodies:
        parts.append(clip_tokens(body, caps.get("prompt_tok_each", 400)))
    sys_full = "\n\n".join(parts)

    solved_txt = []
    budget_s = caps.get("solved_tok", 400)
    for row in reversed(solved):
        line = f"- {row.get('issue','')}: {row.get('solution','')}"
        if stats["solved_tokens"] + approx_tokens(line) > budget_s:
            break
        solved_txt.append(line)
        stats["solved_tokens"] += approx_tokens(line)
    pin_txt = []
    budget_p = caps.get("pins_tok", 200)
    for pin in pins:
        line = f"- {pin.get('text','')}"
        if stats["pin_tokens"] + approx_tokens(line) > budget_p:
            break
        pin_txt.append(line)
        stats["pin_tokens"] += approx_tokens(line)
    summary_c = clip_tokens(summary, caps.get("summary_tok", 600))
    stats["summary_tokens"] = approx_tokens(summary_c)
    rag_c = clip_tokens("\n".join(rag_bits), caps.get("rag_tok", 800))
    stats["rag_tokens"] = approx_tokens(rag_c)

    extra = ""
    if solved_txt:
        extra += "Solved issues:\n" + "\n".join(reversed(solved_txt)) + "\n"
    if pin_txt:
        extra += "Pinned facts:\n" + "\n".join(pin_txt) + "\n"
    if summary_c:
        extra += "Summary:\n" + summary_c + "\n"
    if rag_c:
        extra += "Docs:\n" + rag_c + "\n"
    if failed_notes:
        extra += clip_tokens(failed_notes, 200)

    used = approx_tokens(sys_full) + approx_tokens(extra)
    remain = max(200, ctx - used - 64)
    kept: list[dict] = []
    for msg in reversed(working):
        t = approx_tokens(str(msg.get("content") or "") + str(msg.get("tool_calls") or ""))
        if stats["working_tokens"] + t > remain:
            stats["overflow"] = True
            break
        kept.append(msg)
        stats["working_tokens"] += t
    kept.reverse()
    return sys_full + "\n" + extra, kept, stats
