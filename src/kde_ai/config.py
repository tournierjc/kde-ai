from __future__ import annotations

import copy
import json
import logging
import re
import tomllib
from typing import Any

from kde_ai.paths import config_path, ensure_dirs

log = logging.getLogger("kde-ai")

DEFAULTS: dict[str, Any] = {
    "daemon": {
        "enabled": True,
        "force_run_during_pause": False,
        "idle_unload_s": 15,
        "max_sessions": 50,
        "log_level": "info",
        "protocol_version": 1,
    },
    "llm": {
        "gguf": "~/.local/share/kde-ai/models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "llama_server": "llama-server",
        "host": "127.0.0.1",
        "ctx": 4096,
        "n_gpu_layers": 99,
        "threads": 8,
        "temperature": 0.3,
        "top_p": 0.9,
        "repeat_penalty": 1.05,
        "max_tool_rounds": 6,
        "request_timeout_s": 120,
        "load_timeout_s": 60,
    },
    "memory": {
        "solved_tok": 400,
        "pins_tok": 200,
        "summary_tok": 600,
        "rag_tok": 800,
        "tool_result_chars": 2000,
    },
    "issue": {
        "max_attempts": 3,
        "enter_on_fix_flag": True,
        "patterns": [
            "crash",
            "broken",
            "doesn't work",
            "does not work",
            "won't",
            "failed",
            "error",
            "regression",
            "after update",
            "after upgrade",
            "black screen",
            "no audio",
        ],
    },
    "gpu": {
        "poll_hz": 2,
        "resume_hold_s": 10,
        "vram_other_mb": 2048,
        "denylist": [
            "comfy",
            "comfyui",
            "blender",
            "steam",
            "llama-server",
            "ollama",
            "python.*train",
        ],
        "graphics_allow": [
            "kwin",
            "plasmashell",
            "Xorg",
            "firefox",
            "chrome",
            "chromium",
            "discord",
            "openlogi",
        ],
    },
    "rag": {
        "enabled": True,
        "k": 5,
        "man_sections": ["1", "5", "7", "8"],
        "doc_globs": [
            "/usr/share/doc/plasma*",
            "/usr/share/doc/kwin*",
            "/usr/share/doc/cachyos*",
        ],
        "reindex_on_boot": True,
    },
    "network": {
        "timeout_s": 10,
        "bugzilla_base": "https://bugs.kde.org",
        "invent_base": "https://invent.kde.org",
        "offline": False,
    },
    "privilege": {"frontend_default": "auto", "sudo_timestamp_ok": True},
    "cli": {"default_session": "last", "krunner_session": "last"},
    "plasma": {
        "prefix": "ai ",
        "global_shortcut": "",
        "default_page": "chat",
        "ui_surface": "panel",
    },
    "skills": {
        "max_enabled_per_session": 3,
        "prompt_tok_each": 400,
        "enabled": ["kde-desktop", "cachyos", "bugs"],
    },
}

CONFIG_SET_WHITELIST = {
    "daemon.enabled",
    "daemon.idle_unload_s",
    "daemon.log_level",
    "daemon.force_run_during_pause",
    "llm.gguf",
    "llm.temperature",
    "llm.top_p",
    "gpu.denylist",
    "gpu.graphics_allow",
    "rag.enabled",
    "rag.reindex_on_boot",
    "cli.default_session",
    "cli.krunner_session",
    "plasma.prefix",
    "plasma.global_shortcut",
    "plasma.default_page",
    "plasma.ui_surface",
    "skills.enabled",
    "network.offline",
    "privilege.frontend_default",
}

_LIST_KEYS = {"gpu.graphics_allow", "gpu.denylist", "skills.enabled"}
_PLASMA_UI_SURFACES = {"panel", "tray", "none"}
GPU_ALLOW_CORE = ("kwin", "plasmashell", "xorg")


def as_str_list(value: Any) -> list[str]:
    """Normalize JSON arrays, comma/newline lists, or Python lists to names."""
    if value is None or value is False:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return as_str_list(parsed)
        return [part.strip() for part in re.split(r"[\s,;]+", text) if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("expected a list of names")


def gpu_allow_names(cfg: Config | None = None, names: list[str] | None = None) -> list[str]:
    extra = names if names is not None else as_str_list((cfg.get("gpu.graphics_allow") if cfg else None) or [])
    extra = [name.lower() for name in extra]
    out: list[str] = []
    seen: set[str] = set()
    for name in (*GPU_ALLOW_CORE, *extra):
        if len(name) < 2 or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _toml_dump(data: dict, prefix: str = "") -> str:
    lines: list[str] = []
    scalars: dict = {}
    tables: dict = {}
    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            scalars[k] = v
    if prefix:
        lines.append(f"[{prefix}]")
    for k, v in scalars.items():
        lines.append(f"{k} = {_toml_value(v)}")
    if prefix and (scalars or not tables):
        lines.append("")
    for k, v in tables.items():
        key = f"{prefix}.{k}" if prefix else k
        lines.append(_toml_dump(v, key))
    return "\n".join(lines).rstrip() + "\n"


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        inner = ", ".join(_toml_value(x) for x in v)
        return f"[{inner}]"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


class Config:
    def __init__(self) -> None:
        self.data = copy.deepcopy(DEFAULTS)
        self.config_error: str | None = None
        self.load()

    def load(self) -> None:
        ensure_dirs()
        path = config_path()
        self.config_error = None
        if not path.exists():
            path.write_text(_toml_dump(DEFAULTS), encoding="utf-8")
            self.data = copy.deepcopy(DEFAULTS)
            return
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            self.data = _deep_merge(DEFAULTS, raw)
        except Exception as exc:
            log.warning("config parse error: %s", exc)
            self.config_error = str(exc)
            self.data = copy.deepcopy(DEFAULTS)

    def save(self) -> None:
        config_path().write_text(_toml_dump(self.data), encoding="utf-8")

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set_path(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        cur = self.data
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value

    def redacted(self) -> dict:
        return copy.deepcopy(self.data)


def apply_patch(cfg: Config, patch: dict) -> list[str]:
    changed: list[str] = []
    patch = dict(patch)
    if "plasma.global_shortcut" in patch and patch["plasma.global_shortcut"]:
        from kde_ai.global_shortcut import to_portable

        try:
            patch["plasma.global_shortcut"] = to_portable(str(patch["plasma.global_shortcut"]))
        except ValueError:
            pass
    for key, value in patch.items():
        if key not in CONFIG_SET_WHITELIST:
            from kde_ai.errors import VALIDATION, RpcError

            raise RpcError(VALIDATION, f"config key not allowed: {key}")
        if key in _LIST_KEYS:
            from kde_ai.errors import VALIDATION, RpcError

            try:
                value = as_str_list(value)
            except ValueError as exc:
                raise RpcError(VALIDATION, str(exc)) from exc
        if key == "gpu.denylist":
            from kde_ai.errors import VALIDATION, RpcError

            for pat in value:
                try:
                    re.compile(pat)
                except re.error as exc:
                    raise RpcError(VALIDATION, f"invalid gpu.denylist pattern {pat!r}: {exc}") from exc
        if key == "plasma.ui_surface":
            from kde_ai.errors import VALIDATION, RpcError

            surface = str(value or "").strip().lower()
            if surface not in _PLASMA_UI_SURFACES:
                raise RpcError(
                    VALIDATION,
                    f"plasma.ui_surface must be one of: {', '.join(sorted(_PLASMA_UI_SURFACES))}",
                )
            value = surface
        cfg.set_path(key, value)
        changed.append(key)
    cfg.save()
    if "plasma.global_shortcut" in changed:
        from kde_ai.global_shortcut import apply_launch_shortcut

        apply_launch_shortcut(str(cfg.get("plasma.global_shortcut") or ""))
    return changed
