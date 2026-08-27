from __future__ import annotations

from kde_ai.prompting import assemble


def test_assemble_reserves_tool_tokens():
    working = [
        {"role": "user", "content": "old " * 800},
        {"role": "assistant", "content": "reply " * 800},
        {"role": "user", "content": "What GPU do I have?"},
    ]
    caps = {
        "solved_tok": 0,
        "pins_tok": 0,
        "summary_tok": 0,
        "rag_tok": 0,
        "prompt_tok_each": 10,
        "tool_reserve": 1500,
    }
    _, kept, stats = assemble(
        system="sys",
        skill_bodies=["skill"],
        solved=[],
        pins=[],
        summary="",
        rag_bits=[],
        working=working,
        failed_notes="",
        caps=caps,
        ctx=2048,
    )
    assert stats["overflow"] is True
    assert kept
    assert kept[-1]["content"] == "What GPU do I have?"
    used = stats["system_tokens"] + stats["skill_tokens"] + stats["working_tokens"]
    assert used + 1500 <= 2048
