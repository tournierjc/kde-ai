from __future__ import annotations

from pathlib import Path


class Dummy:
    def get(self, k, d=None):
        return d


def ctx(tmp_path):
    from kde_ai.tools import ToolContext

    cfg = Dummy()
    cfg.get = lambda k, d=None: {"memory.tool_result_chars": 2000}.get(k, d)
    att = tmp_path / "att"
    att.mkdir(parents=True, exist_ok=True)
    return ToolContext(cfg, None, "sid", att, lambda *a: None, lambda argv, reason: {"ok": True})


def test_display_settings_howto_and_kcm_match(tmp_path):
    from kde_ai.tools.kde_settings import (
        handle,
        is_display_settings_howto,
        prefer_display_settings_reply,
    )

    q = "how can i change my monitor resolution"
    assert is_display_settings_howto(q)
    assert is_display_settings_howto("Where is the display scaling setting?")
    assert not is_display_settings_howto("How many monitors do I have?")
    assert not is_display_settings_howto("take a screenshot")
    assert not is_display_settings_howto("where can i configure environment variable")
    assert not is_display_settings_howto("where can I configure git")
    got = handle({"query": "monitor resolution"}, ctx(tmp_path))
    assert got["ok"] and got.get("matched") is True
    assert got["kcm"] == "kcm_kscreen"
    assert "systemsettings kcm_kscreen" in got["command"]
    miss = handle({"query": "environment"}, ctx(tmp_path))
    assert miss["ok"] and miss.get("matched") is False
    assert not miss.get("kcm")
    assert not miss.get("command")
    short = handle({"query": "me"}, ctx(tmp_path))
    assert short.get("matched") is False
    dump = "The monitors are ASUS MG28U (HDMI-A-1) and Acer XB273K GP (DP-1)."
    rewritten = prefer_display_settings_reply(q, dump, got)
    assert "kcm_kscreen" in rewritten
    assert "Acer" not in rewritten
    assert "screenshot" not in rewritten.lower()
    kept = "Use ~/.config/environment.d/ for session env."
    env_q = "where can i configure environment variable"
    assert prefer_display_settings_reply(env_q, kept, miss) == kept
    assert prefer_display_settings_reply(q, dump, None) == dump
    assert prefer_display_settings_reply(q, dump, miss) == dump


def test_screenshot_request_rewrites_false_refusal(monkeypatch, tmp_path):
    from kde_ai.tools import ocr as mod

    q = "take a screenshot"
    assert mod.is_screenshot_request(q)
    assert mod.is_screenshot_request("OCR the current screen.")
    assert not mod.is_screenshot_request("how can i change my monitor resolution")
    refuse = (
        "I will not take screenshots. If you are the PC owner, "
        "click 'Take screenshot' in the assistant."
    )
    none = mod.prefer_screenshot_reply(q, refuse, None)
    assert "click" not in none.lower()
    assert "PC owner" not in none
    assert "screenshot_ocr" in none
    quoted = mod.prefer_screenshot_reply(
        q,
        refuse,
        {"ok": True, "text": "Unlock widgets", "path": "/tmp/shot.png"},
    )
    assert "Unlock widgets" in quoted
    assert "/tmp/shot.png" in quoted
    assert "will not take" not in quoted.lower()

    shot = tmp_path / "shot.png"

    def fake_run(argv, timeout=20):
        if argv[0] == "spectacle":
            shot.write_bytes(b"png")
            return {"ok": True, "stdout": "", "stderr": "", "code": 0}
        if argv[0] == "tesseract":
            return {"ok": True, "stdout": "Hello UI", "stderr": "", "code": 0}
        return {"ok": False, "stdout": "", "stderr": "", "code": 1}

    monkeypatch.setattr(mod, "run_argv", fake_run)
    monkeypatch.setattr(mod, "runtime_dir", lambda: tmp_path)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    c = ctx(tmp_path)
    c.attempt_dir = None
    got = mod.handle({}, c)
    assert got["ok"]
    assert got["text"] == "Hello UI"
    assert got["path"] == str(shot)
    assert Path(got["path"]).exists()
