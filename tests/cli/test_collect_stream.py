from __future__ import annotations

from kde_ai.cli import collect_stream


def test_collect_stream_joins_tokens_and_done():
    notes = [
        {"method": "stream.token", "params": {"text": "You have "}},
        {"method": "stream.tool", "params": {"name": "system_info"}},
        {"method": "stream.token", "params": {"text": "2 monitors."}},
        {"method": "stream.done", "params": {"reason": "complete", "error": None}},
    ]
    got = collect_stream(notes)
    assert got["text"] == "You have 2 monitors."
    assert got["reason"] == "complete"
    assert got["error"] is None


def test_collect_stream_empty():
    assert collect_stream([]) == {"text": "", "reason": None, "error": None}