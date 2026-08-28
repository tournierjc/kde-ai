# Model bake-off — best-in-class daily agent (CachyOS + KDE)

Goal: a **daily driver** on the user's laptop — fix Plasma issues, answer CachyOS questions, search bugs, refuse unsafe asks, and use tools instead of guessing. Spark trains; desktop runs `llama-server` + GGUF on an RTX 3090 (24 GB).

## What is wrong today

| Gap | Impact |
| --- | --- |
| Holdout gate scores **labeled** `eval.jsonl`, not model output | CI passes at 1.0 even when the shipped GGUF is still base Qwen |
| Only **1.5B** (+ 3B SFT fallback) in the recipe | Too small for open-ended how-tos (env vars, resolution, cross-domain) |
| **200** DPO pairs | Too thin for call-vs-guess, propose discipline, privilege cancel |
| No **substance** metrics | Format-perfect answers can still say `export` / `allowlisted` on env how-tos |
| No **latency / VRAM** comparison | A 7B winner that stalls the GPU loses daily-driver value |
| Template mix ≠ **real failure modes** | Missing “you didn’t answer”, follow-ups, kernel+Wi‑Fi combos |

## Candidate models (inference on 3090)

Train and export all that fit Spark VRAM; desktop-eval Q4_K_M unless noted.

| Tier | Model | GGUF weights | Loaded @ 4k ctx (est.) | Role |
| --- | --- | --- | --- | --- |
| A (current) | `Qwen/Qwen2.5-1.5B-Instruct` | ~1.1 GB | ~2 GB | Baseline speed |
| B | `Qwen/Qwen2.5-3B-Instruct` | ~2.0 GB | ~3 GB | Better tool JSON |
| C | `Qwen/Qwen2.5-7B-Instruct` | ~4.5 GB | ~6 GB | Qwen2.5 ceiling |
| **D (recommended)** | **`Qwen/Qwen3.5-9B-Instruct`** | **~5.5–6 GB Q4_K_M** | **~8–9 GB** | **Primary challenger — best daily-driver quality on 3090** |
| E | `Qwen/Qwen3-4B-Instruct` | ~2.5 GB | ~4 GB | Smaller Qwen3 cross-check |

**Default hypothesis (updated):** **Qwen3.5-9B Q4_K_M** on RTX 3090. Weights ~6 GB + KV @ 4096 ~1 GB → ~8 GB loaded, ~16 GB free for ComfyUI / games. Idle unload (`daemon.idle_unload_s=15`) drops VRAM to 0 between chats; smaller/faster quants (Q4_K_S, Q3_K_XL) shorten reload time if needed.

### Qwen3.5-9B quant ladder (3090)

| Quant | File ~size | Weights VRAM | When to use |
| --- | --- | --- | --- |
| Q4_K_M | ~5.8 GB | ~6 GB | **Default** — best quality/size for tool calling |
| Q4_K_S | ~5.5 GB | ~5.5 GB | Faster load/unload, tiny quality trade |
| Q3_K_XL | ~4.7 GB | ~5 GB | Max headroom if ComfyUI shares the GPU |
| Q6_K | ~7.9 GB | ~8 GB | If you rarely unload and want near-Q8 |
| Q2_K / IQ3 | ~3.5 GB | ~4 GB | Avoid for tool JSON — format errors rise |

GGUF source: `bartowski/Qwen_Qwen3.5-9B-GGUF` (imatrix quants). Requires **recent llama.cpp** with Qwen3.5 + `--jinja` (verify CachyOS `llama-cpp` ≥ build with Qwen3.5 support).

```bash
huggingface-cli download bartowski/Qwen_Qwen3.5-9B-GGUF \
  --include 'Qwen_Qwen3.5-9B-Q4_K_M.gguf' \
  --local-dir ~/.local/share/kde-ai/models/
```

**Before Spark SFT:** run base Instruct GGUF through `daily_scenarios.jsonl` bakeoff. If untrained 9B already beats fine-tuned 1.5B on substance, train **on 9B**, not 7B.

**Training note:** Qwen3.5-9B uses a hybrid GDN architecture (not plain Transformer). Spark recipe stays LoRA r=32 on language layers; may need micro-batch 1, SDPA not FA2, and lr ~1e-4–2e-5 (community tool-calling SFT uses lower lr than Qwen2.5). Configs: `training/configs/sft_qwen35_9b.yaml` (to add). Cannot reuse Qwen2.5 adapters.

**Disable thinking mode** for the agent (`--reasoning-budget 0` or equivalent in llama-server if the model emits `` blocks — test with a dry run).

## Training method matrix (Spark)

Run the same `data/out/train.jsonl` / `eval.jsonl` / `dpo.jsonl` for every row unless noted.

| ID | SFT base | Epochs | LoRA r | DPO | Notes |
| --- | --- | --- | --- | --- | --- |
| M0 | 1.5B | 2 | 32 | 200 pairs | Current shipping recipe |
| M1 | 3B | 2 | 32 | — | SFT-only control |
| M2 | 3B | 2 | 32 | 200 | Current fallback path |
| M3 | 7B | 2 | 32 | 200 | Qwen2.5 ceiling |
| **M8** | **3.5-9B** | **2** | **32** | **200** | **Recommended main experiment** |
| M9 | 3.5-9B | 2 | 32 | 500+ | DPO expanded from bakeoff failures |
| M10 | 3.5-9B base GGUF | — | — | — | **Zero-shot gate** before any Spark run |

Configs: `training/configs/sft_qwen25_{1_5b,3b,7b}.yaml`, `training/configs/dpo_qwen25_{1_5b,3b,7b}.yaml`, `training/configs/sft_qwen35_9b.yaml` (to add).

Teacher (optional): `Qwen/Qwen2.5-32B-Instruct` fills `data/templates/` for **new** gold only — never overwrite reviewed gold. Compare M3 vs M3+teacher-augmented corpus in a second pass.

## Evaluation suites

### 1. Format gate (existing)

```bash
python scripts/eval_holdout.py --predictions runs/<model>/eval_predictions.jsonl
```

Six gates: valid JSON, tool @1, irrelevance, propose_solved discipline, invented Bugzilla, RAG cite.

### 2. Gold alignment (new)

```bash
python scripts/model_bakeoff.py score \
  --gold data/out/eval.jsonl \
  --predictions runs/<model>/eval_predictions.jsonl \
  --out runs/<model>/score.json
```

Adds: `tool_match_at1`, `answer_overlap`, per-domain breakdown, **daily substance** checks.

### 3. Daily scenarios (curated)

```bash
python scripts/model_bakeoff.py predict --suite data/eval/daily_scenarios.jsonl ...
python scripts/model_bakeoff.py score --gold data/eval/daily_scenarios.jsonl ...
```

~40 hand-picked desktop tasks: env vars, resolution, screenshot, nft, GPU driver, refuse, Wi‑Fi, panel, pacman, multi-turn repair. Each row has explicit `checks` (required tools, forbidden phrases, required substrings).

### 4. Live agent smoke (manual)

From `docs/qa-matrix.md`: issue loop, privilege cancel, RAG reindex, GPU yield. Run once per finalist GGUF.

## Scoring weights (pick a winner)

| Metric | Weight | Pass bar |
| --- | --- | --- |
| `daily_substance` | 30% | ≥ 85% |
| `tool_match_at1` vs gold | 25% | ≥ 65% |
| Format gates (all six) | 20% | all pass |
| `refuse_clean` | 10% | ≥ 95% |
| p95 time-to-first-token (daily suite) | 10% | ≤ 2.5 s |
| Q4_K_M size | 5% | tie-break toward smaller |

A model that passes format gates but fails `daily_substance` (env → `export`, resolution → EDID dump) **does not ship**.

## Recommended workflow

```bash
# 1. Corpus (laptop or CI)
./scripts/build_dataset.sh

# 2. For each Spark run (M0…M7)
python training/train_sft.py --config training/configs/sft_qwen25_7b.yaml
./training/export_gguf.sh   # set SFT_ADAPTER / BASE_MODEL
python training/train_dpo.py --config training/configs/dpo_qwen25_7b.yaml
./training/export_gguf.sh

# 3. Copy GGUF to desktop; predict + score
export KDE_AI_GGUF=~/.local/share/kde-ai/models/kde-ai-7b-q4_k_m.gguf
python scripts/model_bakeoff.py predict \
  --gguf "$KDE_AI_GGUF" \
  --suite data/out/eval.jsonl \
  --out runs/m3/eval_predictions.jsonl

python scripts/model_bakeoff.py predict \
  --suite data/eval/daily_scenarios.jsonl \
  --out runs/m3/daily_predictions.jsonl

python scripts/model_bakeoff.py score \
  --gold data/eval/daily_scenarios.jsonl \
  --predictions runs/m3/daily_predictions.jsonl \
  --out runs/m3/daily_score.json

# 4. Compare finalists
python scripts/model_bakeoff.py compare runs/m0/score.json runs/m3/score.json
```

## Dataset improvements tied to bake-off failures

When a model fails, add **training signal**, not runtime hacks:

| Failure | Training fix |
| --- | --- |
| Env how-to → `export` / allowlist talk | More `questions.py` paraphrases + DPO reject pairs |
| Resolution → `system_info` EDID dump | DPO: chosen=kcm_kscreen path, rejected=brand dump |
| Screenshot → invented UI button | Tool-scene weight ↑ in `TOOL_SCENES` |
| Unmatched KCM → generic systemsettings | Gold + DPO on `matched: false` → `search_docs` |
| “You didn’t answer” follow-up | Multi-turn rows in `write_gold.py` (resolution example) |
| Cross-domain (kernel + Wi‑Fi) | New expert cases, not new skills |

Expand DPO to **500+** rows sourced from bakeoff `rejected` generations (human or 32B teacher on Spark).

## Ship decision

1. Winner must pass **all format gates** on `eval.jsonl` predictions.
2. Winner must beat M0 on `daily_substance` by ≥ 10 points.
3. Deploy Q4_K_M; keep Q5_K_M for A/B if within 2% substance.
4. Store `holdout_metrics.json` + `daily_score.json` next to the GGUF in `dist/`.

Until a fine-tuned GGUF beats base Qwen on **daily scenarios**, the agent remains a tool harness around a generic small model — not best-in-class.
