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

Gold coverage (enforced by `tests/data/test_gold_coverage.py`):

- ≥ 1 trajectory per tool
- ≥ 10 issue Yes, ≥ 10 issue No+undo, ≥ 5 cancel
- ≥ 5 privilege-cancel, ≥ 5 RAG with real man page names
- ≥ 5 refuse unrestricted shell / password
- ≥ 3 skill-narrowed tool lists

See `data/DATASET.md`, `data/SOURCES.md`, `data/schema/record.schema.json`.
