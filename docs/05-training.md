# Training (DGX Spark)

Spark is **training-only**. Desktop inference is local `llama-server`.

- Base (ship default): `Qwen/Qwen2.5-1.5B-Instruct`
- **Primary train target:** `Qwen/Qwen3.5-4B` — LoRA SFT+DPO, export Q4_K_M GGUF for desktop
- LoRA r=32 α=64 dropout 0.05 on `q/k/v/o/gate/up/down_proj`
- lr 2e-4 cosine, warmup 0.03, 2 epochs, grad clip 1.0, bf16, grad checkpoint
- effective batch 16, seq 4096, packing on
- loss on assistant+tool tokens only
- TRL+PEFT, **no Unsloth**
- DPO β=0.1, lr 5e-7, 1 epoch on 200 pairs
- If the eval gate fails on 1.5B: same recipe on `Qwen/Qwen2.5-3B-Instruct`

```bash
python scripts/challenge_dataset.py
python training/train_sft.py --config training/configs/sft_qwen35_4b.yaml
./training/export_gguf.sh
python training/train_dpo.py --config training/configs/dpo_qwen35_4b.yaml
python scripts/eval_holdout.py --eval data/out/eval.jsonl
```

Fallback 3B config: `training/configs/sft_qwen25_3b.yaml`.  
Qwen3.5-4B (recommended): `training/configs/sft_qwen35_4b.yaml` + `training/configs/dpo_qwen35_4b.yaml`.  
Spark launcher: `training/spark_train_4b.sh` (checks MemAvailable ≥ 25 GiB first).

## Eval gate (must all pass to ship 1.5B)

| Metric | Threshold |
| --- | --- |
| Valid tool JSON rate | ≥ 90% |
| Correct tool name @1 (eval tool turns) | ≥ 70% |
| Irrelevance / no-tool when none needed | ≥ 80% |
| `propose_solved` only if issue_mode | ≥ 95% |
| Invented Bugzilla id rate | ≤ 2% |
| RAG path hallucination (eval) | ≤ 10% |

Desktop still serves Q4_K_M. Context 4096. Idle unload is the VRAM story.
