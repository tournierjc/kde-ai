"""Expand gold templates into 30000 train + 500 eval + 500 DPO JSONL."""

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
from data.generators.expert import (
    MAN,
    TOOL_SCENES,
    cachyos_cases,
    kde_dev_cases,
    kde_user_cases,
    linux_eng_cases,
    network_cases,
    record_from_case,
    refuse_extra_cases,
    sysadmin_cases,
)
from data.generators.questions import manpage_howto
from data.generators.write_gold import write_gold

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
DPO_MIX = {
    "call-vs-no-call": 200,
    "propose-vs-not": 150,
    "privilege-cancel-vs-proceed": 150,
}

_CALL_REJECTED = [
    "I guess the version is 5.27 without checking.",
    "Plasma 6.3 is installed; no need to look it up.",
    "The package is probably linux-cachyos — I did not query pacman.",
    "Bug 487001 is likely the cause; I did not search Bugzilla.",
    "Your GPU is an RTX 4090 with 24 GB VRAM.",
    "Night Light is off in System Settings already.",
    "Run `export KDEHOME=~/.config` in your shell.",
    "Open System Settings and search for the module.",
]
_PROPOSE_REJECTED = [
    "All fixed! No need to confirm.",
    "That should resolve it — closing the issue.",
    "I applied the fix; you're good to go.",
    "Marked solved. Reboot if it still happens.",
    "Done — no further steps needed.",
]
_PRIV_REJECTED = [
    "I already ran it as root without asking.",
    "Authenticated and applied the change.",
    "Ran journalctl as root; here is the output…",
    "Executed the privileged command successfully.",
    "Root shell completed; firewall updated.",
]
_PRIV_SCENES = [
    ("Read system journal ({i}).", "journalctl_system_n"),
    ("Show nftables firewall rules.", "nft_list_ruleset"),
    ("Run dmesg for kernel messages.", "dmesg"),
    ("Check systemd unit status for NetworkManager.", "systemctl_status_unit"),
    ("Run id as root to verify privileges.", "id"),
]

SK = ["kde-desktop", "cachyos", "bugs"]


def _from_pool(prefix: str, i: int, pool: list[dict], domain: str) -> dict:
    spec = pool[i % len(pool)]
    rec = record_from_case(
        f"{prefix}-{i:05d}", spec, source="template", variant=i // len(pool)
    )
    rec["meta"]["domain"] = domain
    return rec


def _tools_rec(prefix: str, i: int, domain="tools") -> dict:
    names = list(ALLOW_TOOLS)
    name = names[i % len(names)]
    scenes = TOOL_SCENES.get(name) or []
    if scenes:
        spec = scenes[i % len(scenes)]
        rec = record_from_case(
            f"{prefix}-{i:05d}", spec, source="template", variant=i // len(scenes)
        )
        rec["meta"]["domain"] = domain
        if name == "propose_solved":
            rec["meta"]["issue_mode"] = True
        return rec
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
    pool = (
        kde_user_cases()
        + [c for c in kde_dev_cases() if c["domain"] == "kde"]
        + [c for c in network_cases() if c["domain"] == "kde"]
    )
    return _from_pool(prefix, i, pool, "kde")


def _cachy_rec(prefix: str, i: int) -> dict:
    return _from_pool(prefix, i, cachyos_cases() + sysadmin_cases(), "cachyos")


def _bug_rec(prefix: str, i: int) -> dict:
    return _from_pool(
        prefix,
        i,
        [c for c in kde_dev_cases() if c["domain"] == "bug_search"],
        "bug_search",
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
    pool = [c for c in linux_eng_cases() + network_cases() if c["domain"] == "rag"]
    if pool and i % 2 == 0:
        return _from_pool(prefix, i, pool, "rag")
    title, sec, path = MAN[i % len(MAN)]
    q, answer = manpage_howto(title, sec, path, i // len(MAN))
    return record(
        f"{prefix}-{i:05d}",
        "rag",
        False,
        ["docs"],
        [
            user(q),
            assistant_tools([call("search_docs", {"query": title})]),
            tool(
                "search_docs",
                {
                    "ok": True,
                    "hits": [{"title": title, "path": path, "section": sec, "snippet": f"{title}({sec}) local manpage"}],
                },
            ),
            assistant_text(answer),
        ],
        source="template",
        tags=["rag_cite", "tool:search_docs"],
    )


def _refuse_rec(prefix: str, i: int) -> dict:
    extras = refuse_extra_cases()
    if extras and i % 2 == 0:
        rec = record_from_case(
            f"{prefix}-{i:05d}",
            extras[i % len(extras)],
            source="template",
            variant=i // len(extras),
        )
        rec["meta"]["domain"] = "refuse"
        return rec
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
            user(qs[i % len(qs)]),
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
    for i in range(DPO_MIX["call-vs-no-call"]):
        rec = _tools_rec("dpo-call", i)
        rec["id"] = f"dpo-call-{i:03d}"
        rec["meta"]["domain"] = "dpo"
        rec["meta"]["dpo_kind"] = "call-vs-no-call"
        rec["chosen"] = rec["messages"][2]
        rec["rejected"] = assistant_text(_CALL_REJECTED[i % len(_CALL_REJECTED)])
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    for i in range(DPO_MIX["propose-vs-not"]):
        rec = _solve_rec("dpo-propose", i)
        rec["id"] = f"dpo-propose-{i:03d}"
        rec["meta"]["domain"] = "dpo"
        rec["meta"]["dpo_kind"] = "propose-vs-not"
        rec["chosen"] = rec["messages"][2]
        rec["rejected"] = assistant_text(_PROPOSE_REJECTED[i % len(_PROPOSE_REJECTED)])
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    for i in range(DPO_MIX["privilege-cancel-vs-proceed"]):
        prompt, priv_name = _PRIV_SCENES[i % len(_PRIV_SCENES)]
        rec = record(
            f"dpo-priv-{i:03d}",
            "dpo",
            False,
            ["cachyos"],
            [
                user(prompt.format(i=i)),
                assistant_tools([call("run_privileged_cmd", {"name": priv_name})]),
            ],
            source="template",
            tags=["privilege_cancel"],
            dpo_kind="privilege-cancel-vs-proceed",
        )
        rec["chosen"] = assistant_text(
            "Waiting for you to authenticate or cancel. I will not assume success."
        )
        rec["rejected"] = assistant_text(_PRIV_REJECTED[i % len(_PRIV_REJECTED)])
        rec["prompt"] = rec["messages"][:2]
        rows.append(rec)
    return rows


def _refresh_sha256sums(out: Path, names: tuple[str, ...] = ("train.jsonl", "eval.jsonl", "dpo.jsonl")) -> None:
    sums_path = out / "SHA256SUMS"
    listed: dict[str, str] = {}
    if sums_path.exists():
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h, name = line.split(maxsplit=1)
                listed[name] = h
    for name in names:
        listed[name] = hashlib.sha256((out / name).read_bytes()).hexdigest()
    order = ("train.jsonl", "eval.jsonl", "dpo.jsonl")
    sums_path.write_text(
        "\n".join(f"{listed[name]}  {name}" for name in order if name in listed) + "\n",
        encoding="utf-8",
    )


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
    _refresh_sha256sums(out)
    print(f"train={len(train)} eval={len(eval_rows)} dpo={len(dpo)}")


def build_dpo_only(out: Path) -> None:
    dpo = _dpo_rows()
    _write_jsonl(out / "dpo.jsonl", dpo)
    _refresh_sha256sums(out, ("dpo.jsonl",))
    print(f"dpo={len(dpo)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--dpo-only", action="store_true", help="Regenerate dpo.jsonl and update its SHA256 only")
    args = p.parse_args()
    if args.dpo_only:
        build_dpo_only(args.out)
    else:
        build(args.out)


if __name__ == "__main__":
    main()
