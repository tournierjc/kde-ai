from __future__ import annotations

import pytest

from kde_ai.config import Config, as_str_list, apply_patch, gpu_allow_names
from kde_ai.errors import RpcError


def test_as_str_list_json_csv_and_lines():
    assert as_str_list(["kwin", " firefox "]) == ["kwin", "firefox"]
    assert as_str_list('["kwin","firefox"]') == ["kwin", "firefox"]
    assert as_str_list("kwin, firefox\nopenlogi") == ["kwin", "firefox", "openlogi"]
    assert as_str_list("") == []
    assert as_str_list(None) == []


def test_gpu_allow_names_keeps_desktop_core():
    assert "kwin" in gpu_allow_names(names=["openlogi"])
    assert "openlogi" in gpu_allow_names(names=["openlogi"])
    assert "x" not in gpu_allow_names(names=["x", "ok"])


def test_apply_patch_graphics_allow_and_denylist(xdg):
    cfg = Config()
    apply_patch(cfg, {"gpu.graphics_allow": "kwin,firefox,openlogi"})
    assert "firefox" in cfg.get("gpu.graphics_allow")
    assert "openlogi" in cfg.get("gpu.graphics_allow")
    apply_patch(cfg, {"gpu.denylist": "comfy\nblender"})
    assert cfg.get("gpu.denylist") == ["comfy", "blender"]
    with pytest.raises(RpcError) as exc:
        apply_patch(cfg, {"gpu.denylist": ["("]})
    assert exc.value.code == "VALIDATION"
