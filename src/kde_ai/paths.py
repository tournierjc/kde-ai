from __future__ import annotations

import os
from pathlib import Path


def xdg_home() -> Path:
    return Path.home()


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kde-ai"


def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "kde-ai"


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kde-ai"


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base) / "kde-ai"
    return Path(f"/tmp/kde-ai-{os.getuid()}")


def socket_path() -> Path:
    return runtime_dir() / "kde-ai.sock"


def stopped_path() -> Path:
    return runtime_dir() / "stopped"


def pid_path() -> Path:
    return runtime_dir() / "daemon.pid"


def sessions_dir() -> Path:
    return data_dir() / "sessions"


def models_dir() -> Path:
    return data_dir() / "models"


def user_skills_dir() -> Path:
    return data_dir() / "skills"


def exports_dir() -> Path:
    return data_dir() / "exports"


def docs_db() -> Path:
    return cache_dir() / "docs.sqlite"


def config_path() -> Path:
    return config_dir() / "config.toml"


def invent_token_path() -> Path:
    return config_dir() / "invent.token"


def package_root() -> Path:
    return Path(__file__).resolve().parent


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "pyproject.toml").exists():
            return p
    return here.parents[2]


def shipped_skills_dirs() -> list[Path]:
    dirs: list[Path] = []
    bundled = package_root() / "shipped_skills"
    if bundled.is_dir():
        dirs.append(bundled)
    repo = repo_root() / "skills"
    if repo.is_dir() and repo.resolve() not in {p.resolve() for p in dirs}:
        dirs.append(repo)
    sys_dir = Path("/usr/share/kde-ai/skills")
    if sys_dir.is_dir():
        dirs.append(sys_dir)
    local = Path.home() / ".local/share/kde-ai-shipped-skills"
    if local.is_dir():
        dirs.append(local)
    return dirs


def ensure_dirs() -> None:
    for p in (
        config_dir(),
        data_dir(),
        cache_dir(),
        runtime_dir(),
        sessions_dir(),
        models_dir(),
        user_skills_dir(),
        exports_dir(),
    ):
        p.mkdir(parents=True, exist_ok=True)
        if p == runtime_dir():
            os.chmod(p, 0o700)
