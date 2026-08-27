from __future__ import annotations

from kde_ai.chatlog import visible_chat_messages


def test_visible_chat_skips_tool_json_and_empty_stubs():
    rows = visible_chat_messages(
        [
            {"role": "user", "content": "how many monitor do i have"},
            {"role": "assistant", "content": "I have 2 monitors."},
            {"role": "user", "content": "can you give me their brand"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "system_info"}}]},
            {
                "role": "tool",
                "name": "system_info",
                "content": '{"ok": true, "summary": "2 monitors", "gpu": "RTX 3090", "monitors": []}',
            },
            {"role": "assistant", "content": "I do not have information about the brand of the monitors."},
        ]
    )
    assert [m["role"] for m in rows] == ["user", "assistant", "user", "assistant"]
    assert "ok" not in rows[-1]["content"]
    assert rows[-1]["content"].startswith("I do not")
    assert all("\"ok\"" not in m["content"] for m in rows)
