from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from kde_ai.errors import NOT_FOUND, VALIDATION, RpcError
from kde_ai.paths import shipped_skills_dirs, user_skills_dir

ID_RE = re.compile(r"^[a-z0-9-]+$")
ALL_TOOLS = {
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


@dataclass
class Skill:
    id: str
    name: str
    description: str
    tools: list[str]
    enabled_default: bool
    body: str
    source: str  # shipped | user
    path: Path

    def as_dict(self, enabled: bool) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "enabled": enabled,
            "tools": self.tools,
        }


def _parse_skill(path: Path, source: str) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    meta = yaml.safe_load(parts[1]) or {}
    sid = str(meta.get("id") or path.parent.name)
    if not ID_RE.match(sid):
        return None
    tools = [t for t in meta.get("tools") or [] if t in ALL_TOOLS]
    return Skill(
        id=sid,
        name=str(meta.get("name") or sid),
        description=str(meta.get("description") or ""),
        tools=tools,
        enabled_default=bool(meta.get("enabled_default", True)),
        body=parts[2].strip(),
        source=source,
        path=path,
    )


def load_skills_from(root: Path, source: str = "shipped") -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    if not root.is_dir():
        return found
    for skill_md in root.glob("*/SKILL.md"):
        sk = _parse_skill(skill_md, source)
        if sk:
            found[sk.id] = sk
    return found


def load_all_skills() -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    for root in shipped_skills_dirs():
        found.update(load_skills_from(root, "shipped"))
    usd = user_skills_dir()
    found.update(load_skills_from(usd, "user"))
    return found


def enabled_ids(cfg_enabled: list[str], session_override: dict | None, skills: dict[str, Skill], max_n: int) -> list[str]:
    session_override = session_override or {}
    ids: list[str] = []
    seen = set()
    for sid in list(cfg_enabled) + list(session_override.keys()):
        if sid in seen or sid not in skills:
            continue
        on = session_override[sid] if sid in session_override else sid in cfg_enabled
        if on:
            ids.append(sid)
            seen.add(sid)
        if len(ids) >= max_n:
            break
    return ids


def allowed_tool_names(enabled: list[Skill]) -> list[str] | None:
    """Union of enabled skill `tools:` lists, still capped to ALL_TOOLS.

    A skill with an empty list does not constrain. No enabled skills, or none
    that list tools, means None (daemon allowlist / all registered tools).
    """
    sets = [set(sk.tools) for sk in enabled if sk.tools]
    if not sets:
        return None
    allowed = set.union(*sets) & ALL_TOOLS
    return sorted(allowed) if allowed else list(ALL_TOOLS)


def install_skill(src: str) -> str:
    p = Path(src).expanduser().resolve()
    if p.is_file():
        sk = _parse_skill(p, "user")
        if not sk:
            raise RpcError(VALIDATION, "invalid SKILL.md")
        if sk.id in {s.id for s in load_all_skills().values() if s.source == "shipped"}:
            raise RpcError(VALIDATION, "cannot overwrite shipped skill")
        dest = user_skills_dir() / sk.id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        return sk.id
    if p.is_dir() and (p / "SKILL.md").exists():
        folder = p
        sk = _parse_skill(folder / "SKILL.md", "user")
        if not sk:
            raise RpcError(VALIDATION, "invalid SKILL.md")
        if sk.id in {s.id for s in load_all_skills().values() if s.source == "shipped"}:
            raise RpcError(VALIDATION, "cannot overwrite shipped skill")
        dest = user_skills_dir() / sk.id
        if dest.exists():
            shutil.rmtree(dest)
        if dest.resolve() in folder.resolve().parents or dest.resolve() == folder.resolve():
            raise RpcError(VALIDATION, "skill source cannot contain the install destination")
        shutil.copytree(folder, dest, ignore=shutil.ignore_patterns(".git"))
        return sk.id
    raise RpcError(VALIDATION, "skill path must be SKILL.md or a skill directory")


def remove_skill(sid: str) -> None:
    dest = user_skills_dir() / sid
    if not dest.exists():
        raise RpcError(NOT_FOUND, "user skill not found")
    shutil.rmtree(dest)
