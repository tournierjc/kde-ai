from __future__ import annotations

import pytest

from kde_ai.config import Config, apply_patch
from kde_ai.errors import RpcError


def test_plasma_ui_surface_default():
    cfg = Config()
    assert cfg.get("plasma.ui_surface") == "panel"


def test_plasma_ui_surface_rejects_invalid():
    cfg = Config()
    with pytest.raises(RpcError, match="plasma.ui_surface"):
        apply_patch(cfg, {"plasma.ui_surface": "both"})


def test_plasma_ui_surface_accepts_tray():
    cfg = Config()
    apply_patch(cfg, {"plasma.ui_surface": "tray"})
    assert cfg.get("plasma.ui_surface") == "tray"
