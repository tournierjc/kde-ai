#!/usr/bin/env python3
"""SFT on DGX Spark with TRL+PEFT (no Unsloth)."""

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
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Install training extras on Spark: pip install -e '.[train]'\n" + str(exc)
        ) from exc

    model_name = cfg["model_name"]
    train_file = cfg["train_file"]
    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="bfloat16",
        trust_remote_code=True,
    )
    lora = LoraConfig(
        r=int(cfg.get("lora_r", 32)),
        lora_alpha=int(cfg.get("lora_alpha", 64)),
        lora_dropout=float(cfg.get("lora_dropout", 0.05)),
        target_modules=cfg.get("target_modules")
        or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
    )
    ds = load_dataset("json", data_files=train_file, split="train")

    def to_text(ex):
        return {"text": tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}

    ds = ds.map(to_text, remove_columns=[c for c in ds.column_names if c != "text"])
    targs = TrainingArguments(
        output_dir=cfg.get("output_dir", "checkpoints/sft"),
        per_device_train_batch_size=int(cfg.get("per_device_train_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("gradient_accumulation_steps", 16)),
        num_train_epochs=float(cfg.get("num_train_epochs", 2)),
        learning_rate=float(cfg.get("learning_rate", 2e-4)),
        lr_scheduler_type="cosine",
        warmup_ratio=float(cfg.get("warmup_ratio", 0.03)),
        bf16=True,
        gradient_checkpointing=True,
        max_grad_norm=1.0,
        logging_steps=10,
        save_steps=int(cfg.get("save_steps", 500)),
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model,
        args=targs,
        train_dataset=ds,
        peft_config=lora,
        processing_class=tok,
    )
    trainer.train()
    trainer.save_model(cfg.get("output_dir", "checkpoints/sft"))
    tok.save_pretrained(cfg.get("output_dir", "checkpoints/sft"))


if __name__ == "__main__":
    main()
