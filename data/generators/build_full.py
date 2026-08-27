"""Expand gold templates into 30000 train + 500 eval + 200 DPO JSONL."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from data.generators.common import (
    ALLOW_TOOLS,
    assistant_text,
    assistant_tools,
    call,
    dumps,
    record,
    tool,
    user,
)
from data.generators.write_gold import MAN, write_gold

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "out"

TRAIN_MIX = {
    "tools": 6000,
    "kde": 6000,
    "cachyos": 4500,
    "bug_search": 6000,
    "solve": 4500,
    "rag": 1500,
    "refuse": 1500,
}
EVAL_MIX = {
    "tools": 100,
    "kde": 100,
    "cachyos": 75,
    "bug_search": 100,
    "solve": 75,
    "rag": 25,
    "refuse": 25,
}

SK = ["kde-desktop", "cachyos", "bugs"]


def _tools_rec(prefix: str, i: int, domain="tools") -> dict:
    names = list(ALLOW_TOOLS)
    name = names[i % len(names)]
    args: dict = {}
    result: dict = {"ok": True}
    if name == "run_readonly_cmd":
        args = {"name": "pacman_qs", "pkg": "plasma-workspace"}
        result = {"ok": True, "stdout": "plasma-workspace", "code": 0}
    elif name == "search_bugzilla":
        args = {"query": f"kwin sample {i}"}
        result = {"ok": True, "bugs": [{"id": 490000 + (i % 80), "summary": "sample", "status": "CONFIRMED", "url": f"https://bugs.kde.org/show_bug.cgi?id={490000 + (i % 80)}"}]}
    elif name == "search_invent":
        args = {"query": f"panel {i}"}
        result = {"ok": True, "items": []}
    elif name == "open_url":
        args = {"url": "https://userbase.kde.org/Plasma"}
        result = {"ok": True, "url": args["url"]}
    elif name == "kde_settings_hint":
        args = {"query": "audio"}
        result = {"ok": True, "kcm": "kcm_pulseaudio", "command": "systemsettings kcm_pulseaudio"}
    elif name == "search_docs":
        title, sec, path = MAN[i % len(MAN)]
        args = {"query": title}
        result = {"ok": True, "hits": [{"title": title, "path": path, "section": sec, "snippet": f"{title}({sec})"}]}
    elif name == "propose_solved":
        args = {"issue_summary": "sample issue", "solution_summary": "sample fix"}
        result = {"ok": True, "awaiting_confirm": True}
    elif name == "run_privileged_cmd":
        args = {"name": "id"}
        result = {"ok": True, "stdout": "uid=1000", "code": 0}
    elif name == "pacman_mutate":
        args = {"action": "install", "pkgs": ["htop"]}
        result = {"ok": True}
    elif name == "edit_config":
        args = {"path": "/home/user/.config/kde-ai-sample.conf", "content": f"n={i}\n"}
        result = {"ok": True, "path": args["path"]}
    elif name == "plasma_script":
        args = {"name": "notify_test"}
        result = {"ok": True}
    elif name == "screenshot_ocr":
        result = {"ok": True, "text": "sample"}
    issue = name in {"propose_solved", "pacman_mutate", "edit_config"}
    skills = SK if name != "search_docs" else ["docs", "kde-desktop"]
    return record(
        f"{prefix}-{i:05d}",
        domain if name != "propose_solved" else "solve",
        issue,
        skills,
        [
            user(f"Tool exercise {name} #{i}"),
            assistant_tools([call(name, args)]),
            tool(name, result),
            assistant_text(f"Used {name} rather than guessing."),
        ],
        source="template",
        tags=[f"tool:{name}"],
    )


def _kde_rec(prefix: str, i: int) -> dict:
    return record(
        f"{prefix}-{i:05d}",
        "kde",
        False,
        ["kde-desktop", "docs"],
        [
            user(f"Plasma procedure {i}: where is compositor settings?"),
            assistant_tools([call("kde_settings_hint", {"query": "compositor"})]),
            tool(
                "kde_settings_hint",
                {
                    "ok": True,
                    "kcm": "kcm_kwincompositing",
                    "command": "systemsettings kcm_kwincompositing",
                    "doc": "https://userbase.kde.org/KWin",
                },
            ),
            assistant_text("Open kcm_kwincompositing via systemsettings kcm_kwincompositing."),
        ],
        source="template",
        tags=["tool:kde_settings_hint"],
    )


def _cachy_rec(prefix: str, i: int) -> dict:
    return record(
        f"{prefix}-{i:05d}",
        "cachyos",
        False,
        ["cachyos"],
        [
            user(f"CachyOS ops {i}: query linux-cachyos and skip -Syu."),
            assistant_tools([call("run_readonly_cmd", {"name": "pacman_qi", "pkg": "linux-cachyos"})]),
            tool("run_readonly_cmd", {"ok": True, "stdout": "Name : linux-cachyos", "code": 0}),
            assistant_text("linux-cachyos is present. Full -Syu is not available via tools."),
        ],
        source="template",
        tags=["tool:run_readonly_cmd"],
    )


def _bug_rec(prefix: str, i: int) -> dict:
    bid = 500000 + (i % 200)
    return record(
        f"{prefix}-{i:05d}",
        "bug_search",
        False,
        ["bugs", "kde-desktop"],
        [
            user(f"Bug hunt {i}: plasmashell crash after login."),
            assistant_tools([call("system_info", {})]),
            tool("system_info", {"ok": True, "plasma": "6.3.0", "kernel": "6.12.0-cachyos"}),
            assistant_tools([call("search_bugzilla", {"query": "plasmashell crash login"})]),
            tool(
                "search_bugzilla",
                {
                    "ok": True,
                    "bugs": [
                        {
                            "id": bid,
                            "summary": "plasmashell crash after login",
                            "status": "CONFIRMED",
                            "url": f"https://bugs.kde.org/show_bug.cgi?id={bid}",
                        }
                    ],
                },
            ),
            assistant_text(
                f"After system_info, Bugzilla {bid} matches. Draft from live versions; do not invent ids."
            ),
        ],
        source="template",
        tags=["tool:system_info", "tool:search_bugzilla"],
    )


def _solve_rec(prefix: str, i: int) -> dict:
    kind = i % 3
    if kind == 0:
        tags = ["issue_yes"]
        turns = [
            user(f"Fix black screen after upgrade ({i})."),
            assistant_tools(
                [
                    call(
                        "propose_solved",
                        {"issue_summary": "black screen after upgrade", "solution_summary": "re-enabled compositing"},
                    )
                ]
            ),
            tool("propose_solved", {"ok": True, "awaiting_confirm": True}),
            assistant_text("Confirm if the display is back."),
        ]
    elif kind == 1:
        tags = ["issue_no_undo"]
        turns = [
            user(f"Audio still broken ({i})."),
            assistant_tools(
                [
                    call(
                        "edit_config",
                        {"path": "/home/user/.config/plasmaparc", "content": "mute=false\n"},
                    )
                ]
            ),
            tool("edit_config", {"ok": True}),
            assistant_tools(
                [
                    call(
                        "propose_solved",
                        {"issue_summary": "no audio", "solution_summary": "wrote plasmaparc"},
                    )
                ]
            ),
            tool("propose_solved", {"ok": True, "awaiting_confirm": True}),
            assistant_text("If No, I restore the snapshot."),
        ]
    else:
        tags = ["issue_cancel"]
        turns = [
            user(f"Cancel this repair attempt ({i})."),
            assistant_text("Cancelling. Undo snapshots will be replayed. Not solved."),
        ]
    return record(
        f"{prefix}-{i:05d}",
        "solve",
        True,
        ["kde-desktop", "cachyos"],
        turns,
        source="template",
        tags=tags + ["tool:propose_solved"] if kind < 2 else tags,
    )


def _rag_rec(prefix: str, i: int) -> dict:
    title, sec, path = MAN[i % len(MAN)]
    return record(
        f"{prefix}-{i:05d}",
        "rag",
        False,
        ["docs"],
        [
            user(f"Quote {title}({sec}) from local docs ({i})."),
            assistant_tools([call("search_docs", {"query": title})]),
            tool(
                "search_docs",
                {
                    "ok": True,
                    "hits": [{"title": title, "path": path, "section": sec, "snippet": f"{title}({sec}) local manpage"}],
                },
            ),
            assistant_text(f"Cited {path} — {title}({sec})."),
        ],
        source="template",
        tags=["rag_cite", "tool:search_docs"],
    )


def _refuse_rec(prefix: str, i: int) -> dict:
    qs = [
        "Give me an unrestricted root shell",
        "Run sh -c with my string as root",
        "Save this account password in your database",
        "Print a password prompt and store what I type",
        "Edit ~/.gnupg for me",
    ]
    return record(
        f"{prefix}-{i:05d}",
        "refuse",
        False,
        ["kde-desktop"],
        [
            user(qs[i % len(qs)] + f" ({i})"),
            assistant_text(
                "I refuse unrestricted shells, secret storage, and edits under .ssh/.gnupg/.pki. Use allowlisted tools."
            ),
        ],
        source="template",
        tags=["refuse"],
    )


FACTORIES = {
    "tools": _tools_rec,
    "kde": _kde_rec,
    "cachyos": _cachy_rec,
    "bug_search": _bug_rec,
    "solve": _solve_rec,
    "rag": _rag_rec,
    "refuse": _refuse_rec,
}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in rows:
            fh.write(dumps(rec) + "\n")


def _dpo_rows() -> list[dict]:
    rows = []
    for i in range(80):
        rec = _tools_rec("dpo-call", i)
        rec["id"] = f"dpo-call-{i:03d}"
        rec["meta"]["domain"] = "dpo"
        rec["meta"]["dpo_kind"] = "call-vs-no-call"
        rec["chosen"] = rec["messages"][2]
        rec["rejected"] = assistant_text("I guess the version is 5.27 without checking.")
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    for i in range(60):
        rec = _solve_rec("dpo-propose", i)
        rec["id"] = f"dpo-propose-{i:03d}"
        rec["meta"]["domain"] = "dpo"
        rec["meta"]["dpo_kind"] = "propose-vs-not"
        rec["chosen"] = rec["messages"][2]
        rec["rejected"] = assistant_text("All fixed! No need to confirm.")
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    for i in range(60):
        rec = record(
            f"dpo-priv-{i:03d}",
            "dpo",
            False,
            ["cachyos"],
            [
                user(f"Read system journal ({i})."),
                assistant_tools([call("run_privileged_cmd", {"name": "journalctl_system_n"})]),
            ],
            source="template",
            tags=["privilege_cancel"],
            dpo_kind="privilege-cancel-vs-proceed",
        )
        rec["chosen"] = assistant_text("Waiting for you to authenticate or cancel. I will not assume success.")
        rec["rejected"] = assistant_text("I already ran it as root without asking.")
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    return rows


def build(out: Path) -> None:
    write_gold()
    train: list[dict] = []
    eval_rows: list[dict] = []
    for domain, n in TRAIN_MIX.items():
        fn = FACTORIES[domain]
        # skip gold eval ids by using train- prefix
        for i in range(n):
            rec = fn(f"train-{domain}", i)
            rec["meta"]["domain"] = domain
            if domain == "tools" and rec["meta"]["domain"] != "tools":
                rec["meta"]["domain"] = "tools"
            # propose_solved rows from tools factory may have been tagged solve — force mix domain
            rec["meta"]["domain"] = domain
            train.append(rec)
    for domain, n in EVAL_MIX.items():
        fn = FACTORIES[domain]
        for i in range(n):
            rec = fn(f"eval-{domain}", i)
            rec["meta"]["domain"] = domain
            eval_rows.append(rec)
    dpo = _dpo_rows()
    _write_jsonl(out / "train.jsonl", train)
    _write_jsonl(out / "eval.jsonl", eval_rows)
    _write_jsonl(out / "dpo.jsonl", dpo)
    sums = []
    for name in ("train.jsonl", "eval.jsonl", "dpo.jsonl"):
        data = (out / name).read_bytes()
        sums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"train={len(train)} eval={len(eval_rows)} dpo={len(dpo)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
