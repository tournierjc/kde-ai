from __future__ import annotations

from data.generators.build_full import _kde_rec, _rag_rec
from data.generators.expert import kde_user_cases
from data.generators.questions import (
    MAN_HOWTO,
    manpage_howto,
    paraphrase_pool,
    paraphrase_question,
)


def _env_case():
    rows = [
        c
        for c in kde_user_cases()
        if "environment" in (c.get("q") or "").lower() or any("environment" in t for t in c.get("topics") or [])
    ]
    assert len(rows) == 1, rows
    return rows[0]


def test_one_env_expert_case_not_phrase_gold():
    spec = _env_case()
    pool = paraphrase_pool(spec)
    blob = "\n".join(pool).lower()
    assert "i want to" in blob
    assert "best way" in blob
    assert "example" in blob
    assert "define an env variable" in blob
    assert any(paraphrase_question(spec, i).lower().startswith("i want to") for i in range(len(pool)))


def test_manpage_howto_teaches_environment_d_procedure():
    qs, answers = [], []
    for i in range(80):
        q, a = manpage_howto("environment.d", "5", "/usr/share/man/man5/environment.d.5", i)
        qs.append(q)
        answers.append(a)
    qblob = "\n".join(qs).lower()
    assert "i want to" in qblob
    assert "best way" in qblob
    assert not any("from local docs (" in q for q in qs)
    assert all("~/.config/environment.d/" in a for a in answers)
    assert all("KEY=value" in a for a in answers)


def test_every_manpage_has_howto_topics():
    from data.generators.expert import MAN

    for title, _sec, _path in MAN:
        assert title in MAN_HOWTO, title
        assert MAN_HOWTO[title].get("topics")
        assert MAN_HOWTO[title].get("answer")


def test_kde_and_rag_factories_cover_speech_acts():
    from data.generators.expert import kde_dev_cases, network_cases

    pool = (
        kde_user_cases()
        + [c for c in kde_dev_cases() if c["domain"] == "kde"]
        + [c for c in network_cases() if c["domain"] == "kde"]
    )
    env_idx = next(i for i, c in enumerate(pool) if "environment" in c["q"].lower())
    kde_qs = [
        _kde_rec("train-kde", env_idx + k * len(pool))["messages"][1]["content"]
        for k in range(40)
    ]
    rag_qs = [_rag_rec("train-rag", i)["messages"][1]["content"] for i in range(80)]
    kde_blob = "\n".join(kde_qs).lower()
    rag_blob = "\n".join(rag_qs).lower()
    assert "i want to" in kde_blob
    assert "best way" in kde_blob
    assert "give me an example" in kde_blob
    assert not any("from local docs (" in q for q in rag_qs)
    assert "environment" in rag_blob or "env" in rag_blob
    rag_answers = [
        m["content"]
        for rec in (_rag_rec("train-rag", i) for i in range(80))
        for m in rec["messages"]
        if m.get("role") == "assistant" and not m.get("tool_calls")
    ]
    assert any("~/.config/environment.d/" in a for a in rag_answers)


def test_gold_has_no_phrase_env_ids():
    from pathlib import Path
    import json

    gold = Path(__file__).resolve().parents[2] / "data" / "gold"
    ids = []
    for path in gold.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.append(json.loads(line)["id"])
    banned = {"gold-kcm-env", "gold-env-define", "gold-env-best-way"}
    assert not (banned & set(ids)), banned & set(ids)
