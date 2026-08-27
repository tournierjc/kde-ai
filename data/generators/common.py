"""Shared helpers for gold + full corpus generation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALLOW_TOOLS = {
    "system_info",
    "run_readonly_cmd",
    "search_bugzilla",
    "search_invent",
    "open_url",
    "kde_settings_hint",
    "search_docs",
    "propose_solved",
    "run_privileged_cmd",
    "pacman_mutate",
    "edit_config",
    "plasma_script",
    "screenshot_ocr",
}


@lru_cache(maxsize=32)
def system_for(skills: tuple[str, ...]) -> str:
    import sys

    src = REPO / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from kde_ai.prompting import clip_tokens, load_system_prompt
    from kde_ai.skills import load_skills_from

    text = load_system_prompt("en_US")
    allsk = load_skills_from(REPO / "skills")
    bodies = []
    for sid in skills:
        sk = allsk.get(sid)
        if sk:
            bodies.append(clip_tokens(sk.body, 400))
    if bodies:
        text = text + "\n\n" + "\n\n".join(bodies)
    return text


def call(name: str, args: dict, cid: str = "1") -> dict:
    return {
        "id": cid,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False, separators=(",", ":"))},
    }


def assistant_tools(calls: list[dict], content: str = "") -> dict:
    return {"role": "assistant", "content": content, "tool_calls": calls}


def assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": text}


def user(text: str) -> dict:
    return {"role": "user", "content": text}


def tool(name: str, payload) -> dict:
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return {"role": "tool", "name": name, "content": content}


def record(
    rid: str,
    domain: str,
    issue_mode: bool,
    skills: list[str],
    turns: list[dict],
    source: str = "gold",
    tags: list[str] | None = None,
    **extra,
) -> dict:
    rec = {
        "id": rid,
        "messages": [{"role": "system", "content": system_for(tuple(skills))}] + turns,
        "meta": {
            "domain": domain,
            "issue_mode": issue_mode,
            "skills": skills,
            "os": "cachyos",
            "plasma": "6",
            "source": source,
            "tags": tags or [],
            **extra,
        },
    }
    return rec


def dumps(rec: dict) -> str:
    return json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
