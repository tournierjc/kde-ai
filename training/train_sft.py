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
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Install training extras on Spark: pip install torch (CUDA) then transformers peft trl datasets\n"
            + str(exc)
        ) from exc

    model_name = cfg["model_name"]
    train_file = str(Path(cfg["train_file"]))
    out_dir = cfg.get("output_dir", "checkpoints/sft")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model_kwargs = {
        "torch_dtype": dtype,
        "trust_remote_code": True,
        "attn_implementation": cfg.get("attn_implementation", "sdpa"),
    }
    if torch.cuda.is_available():
        model_kwargs["device_map"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    lora = LoraConfig(
        r=int(cfg.get("lora_r", 32)),
        lora_alpha=int(cfg.get("lora_alpha", 64)),
        lora_dropout=float(cfg.get("lora_dropout", 0.05)),
        target_modules=cfg.get("target_modules")
        or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
        bias="none",
    )
    raw = load_dataset("json", data_files=train_file, split="train")
    keep = [c for c in raw.column_names if c == "messages"]
    ds = raw.remove_columns([c for c in raw.column_names if c not in keep])

    sft_args = SFTConfig(
        output_dir=out_dir,
        per_device_train_batch_size=int(cfg.get("per_device_train_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("gradient_accumulation_steps", 16)),
        num_train_epochs=float(cfg.get("num_train_epochs", 2)),
        learning_rate=float(cfg.get("learning_rate", 2e-4)),
        lr_scheduler_type="cosine",
        warmup_ratio=float(cfg.get("warmup_ratio", 0.03)),
        bf16=bool(cfg.get("bf16", True)) and torch.cuda.is_available(),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_grad_norm=1.0,
        logging_steps=10,
        save_steps=int(cfg.get("save_steps", 500)),
        save_total_limit=3,
        report_to=[],
        max_length=int(cfg.get("max_seq_length", 4096)),
        packing=bool(cfg.get("packing", True)),
        assistant_only_loss=bool(cfg.get("assistant_only_loss", True)),
    )
    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=ds,
        peft_config=lora,
        processing_class=tok,
    )
    trainer.train()
    trainer.save_model(out_dir)
    tok.save_pretrained(out_dir)


if __name__ == "__main__":
    main()
