from __future__ import annotations

from kde_ai.skills import ALL_TOOLS, enabled_ids, install_skill, load_all_skills, remove_skill


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
