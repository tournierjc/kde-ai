from __future__ import annotations

from kde_ai.skills import (
    ALL_TOOLS,
    allowed_tool_names,
    enabled_ids,
    install_skill,
    load_all_skills,
    remove_skill,
)


def test_shipped_skills_exist(xdg):
    skills = load_all_skills()
    for sid in ("kde-desktop", "cachyos", "bugs", "docs"):
        assert sid in skills
        assert set(skills[sid].tools) <= ALL_TOOLS


def test_max_three_enabled(xdg):
    skills = load_all_skills()
    ids = enabled_ids(
        ["kde-desktop", "cachyos", "bugs", "docs"],
        None,
        skills,
        3,
    )
    assert len(ids) == 3
    assert "docs" not in ids


def test_unknown_tools_dropped(xdg, tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text(
        "---\nid: user-demo\nname: demo\ntools: [system_info, not_a_real_tool, run_privileged_cmd]\n---\nHi\n",
        encoding="utf-8",
    )
    sid = install_skill(str(md))
    assert sid == "user-demo"
    sk = load_all_skills()["user-demo"]
    assert "not_a_real_tool" not in sk.tools
    assert "run_privileged_cmd" in sk.tools  # still a real tool name; argv allowlist stays in daemon
    remove_skill("user-demo")


def test_cannot_overwrite_shipped(xdg, tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("---\nid: kde-desktop\nname: nope\n---\nsteal\n", encoding="utf-8")
    import pytest

    from kde_ai.errors import RpcError

    with pytest.raises(RpcError):
        install_skill(str(md))


def test_allowed_tools_union_not_intersection(xdg):
    skills = load_all_skills()
    kde = skills["kde-desktop"]
    cachy = skills["cachyos"]
    bugs = skills["bugs"]
    union = set(allowed_tool_names([kde, cachy, bugs]) or [])
    assert "kde_settings_hint" in union
    assert "pacman_mutate" in union
    assert "search_bugzilla" in union
    assert "run_privileged_cmd" not in union
    assert allowed_tool_names([]) is None
    docs_only = set(allowed_tool_names([skills["docs"]]) or [])
    assert docs_only == set(skills["docs"].tools)


def test_repo_and_shipped_skill_bodies_match():
    from kde_ai.paths import package_root, repo_root

    repo = repo_root() / "skills"
    bundled = package_root() / "shipped_skills"
    for sid in ("kde-desktop", "cachyos", "bugs", "docs"):
        a = (repo / sid / "SKILL.md").read_text(encoding="utf-8")
        b = (bundled / sid / "SKILL.md").read_text(encoding="utf-8")
        assert a == b, sid


def test_skill_bodies_are_playbooks_not_tool_contracts(xdg):
    banned = (
        "quote those fields",
        "come from system_info",
        "quote uptime",
        "kernel_cmdline",
    )
    for sid in ("kde-desktop", "cachyos", "bugs", "docs"):
        body = load_all_skills()[sid].body.lower()
        for needle in banned:
            assert needle not in body, f"{sid} still teaches {needle!r}"
