# Dataset

The MVP **includes the training data**, not only generator code.

| Layer | Location | Count | In git? |
| --- | --- | --- | --- |
| Gold seed | `data/gold/*.jsonl` | ≥ 400 | yes |
| Full corpus | `data/out/train.jsonl` | 30 000 | LFS / tree |
| Holdout | `data/out/eval.jsonl` | 500 | LFS / tree |
| DPO | `data/out/dpo.jsonl` | 200 | LFS / tree |

Build:

```bash
./scripts/build_dataset.sh
./scripts/build_dataset.sh --gold-only   # laptop unit tests only; not product acceptance
```

## Train mix (30 000)

| Slice | N | `meta.domain` |
| --- | --- | --- |
| Tool-call general | 6000 | `tools` |
| KDE Q&A + procedures | 6000 | `kde` |
| CachyOS / Arch ops | 4500 | `cachyos` |
| Bug search/report | 6000 | `bug_search` |
| Solve confirm / retry | 4500 | `solve` |
| RAG / manpage cite | 1500 | `rag` |
| No-tool / refuse | 1500 | `refuse` |

Eval 500 uses the same proportions (100/100/75/100/75/25/25).
DPO 200: 80 call-vs-no-call, 60 propose-vs-not, 60 privilege-cancel-vs-proceed.

Every record uses the shipped `system.txt` plus the skill ids in `meta.skills`.

## Skills vs training

Skills (`skills/*/SKILL.md`, copied into the package as `shipped_skills/`) are optional **domain playbooks**: how to hunt a KCM, how to query pacman on CachyOS, Bugzilla-then-invent order, RAG-first docs. Frontmatter `tools:` subsets the daemon allowlist. Several enabled skills **union** those lists (still cannot add unknown tools).

The GGUF learns the **tool contract** from gold + `system.txt` + tool schemas: which tool to call, which JSON fields to quote, when to refuse, when `propose_solved` is legal. Do not put “call system_info and quote gpu/ram/uptime” in a skill — add a gold trajectory instead.

Gold and the 30k templates (`data/generators/expert.py`) also teach **domain expertise** inside the existing mix slices: Linux engineering (cgroups, capabilities, journal/dmesg), KDE user + dev (KCMs, KWin/Wayland, invent/Bugzilla), CachyOS (kernels, NVIDIA, pacman, Limine), sysadmin (systemd user vs system, units, fstab), and network admin (NetworkManager, ip/ss/nft/resolvectl *via man citations* — those CLIs are not allowlisted tools).

Gold coverage (enforced by `tests/data/test_gold_coverage.py`):

- ≥ 1 trajectory per tool
- ≥ 10 issue Yes, ≥ 10 issue No+undo, ≥ 5 cancel
- ≥ 5 privilege-cancel, ≥ 5 RAG with real man page names
- ≥ 5 refuse unrestricted shell / password
- ≥ 3 skill-narrowed tool lists

See `data/DATASET.md`, `data/SOURCES.md`, `data/schema/record.schema.json`.
