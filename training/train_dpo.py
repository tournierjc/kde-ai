#!/usr/bin/env python3
"""DPO on 200 pairs (call vs no-call, propose vs not, privilege-cancel vs proceed)."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    args = p.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    try:
        from datasets import load_dataset
        from peft import LoraConfig, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise SystemExit("Install training extras on Spark: pip install -e '.[train]'\n" + str(exc)) from exc

    model_name = cfg["model_name"]
    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="bfloat16", trust_remote_code=True)
    ds = load_dataset("json", data_files=cfg["train_file"], split="train")

    def row(ex):
        prompt = ex.get("prompt") or ex["messages"][:2]
        chosen = ex["chosen"]
        rejected = ex["rejected"]
        if isinstance(chosen, dict):
            chosen = tok.apply_chat_template(prompt + [chosen], tokenize=False, add_generation_prompt=False)
        if isinstance(rejected, dict):
            rejected = tok.apply_chat_template(prompt + [rejected], tokenize=False, add_generation_prompt=False)
        prompt_txt = tok.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
        return {"prompt": prompt_txt, "chosen": chosen, "rejected": rejected}

    ds = ds.map(row)
    lora = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
    )
    targs = DPOConfig(
        output_dir=cfg.get("output_dir", "checkpoints/dpo"),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=1,
        learning_rate=float(cfg.get("learning_rate", 5e-7)),
        bf16=True,
        beta=float(cfg.get("beta", 0.1)),
        report_to=[],
    )
    trainer = DPOTrainer(
        model=model,
        args=targs,
        train_dataset=ds,
        processing_class=tok,
        peft_config=lora,
    )
    trainer.train()
    trainer.save_model(cfg.get("output_dir", "checkpoints/dpo"))


if __name__ == "__main__":
    main()
