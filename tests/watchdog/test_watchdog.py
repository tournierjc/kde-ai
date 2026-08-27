from __future__ import annotations

from kde_ai.config import Config
from kde_ai.watchdog import GpuWatchdog


def test_force_run_clears_pause(xdg):
    cfg = Config()
    w = GpuWatchdog(cfg, {1})
    w.paused = True
    w.reason = "steam"
    cfg.set_path("daemon.force_run_during_pause", True)
    assert w.poll() is False
    assert w.paused is False


def test_graphics_allow_list_present(xdg):
    cfg = Config()
    allow = [a.lower() for a in cfg.get("gpu.graphics_allow")]
    for name in ("firefox", "kwin", "plasmashell", "chrome", "openlogi"):
        assert name in allow
    from kde_ai.config import gpu_allow_names

    assert "kwin" in gpu_allow_names(cfg)
    deny = cfg.get("gpu.denylist")
    assert any("comfy" in d for d in deny)
    assert any("steam" in d for d in deny)
