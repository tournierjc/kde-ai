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
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, PeftModel, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise SystemExit(
            "Install training extras on Spark: pip install torch (CUDA) then transformers peft trl datasets\n"
            + str(exc)
        ) from exc

    model_name = cfg["model_name"]
    out_dir = cfg.get("output_dir", "checkpoints/dpo")
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

    sft_adapter = cfg.get("sft_adapter")
    if sft_adapter:
        sft_path = Path(sft_adapter)
        if not (sft_path / "adapter_config.json").is_file():
            raise SystemExit(f"SFT adapter missing at {sft_path}")
        model = PeftModel.from_pretrained(model, str(sft_path))
        model = model.merge_and_unload()

    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    raw = load_dataset("json", data_files=str(Path(cfg["train_file"])), split="train")

    def row(ex):
        prompt = ex.get("prompt") or ex["messages"][:2]
        chosen = ex["chosen"]
        rejected = ex["rejected"]
        if isinstance(chosen, dict):
            chosen = [chosen]
        if isinstance(rejected, dict):
            rejected = [rejected]
        return {"prompt": prompt, "chosen": chosen, "rejected": rejected}

    ds = raw.map(row, remove_columns=raw.column_names)

    lora = LoraConfig(
        r=int(cfg.get("lora_r", 32)),
        lora_alpha=int(cfg.get("lora_alpha", 64)),
        lora_dropout=float(cfg.get("lora_dropout", 0.05)),
        target_modules=cfg.get("target_modules")
        or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
        bias="none",
    )
    targs = DPOConfig(
        output_dir=out_dir,
        per_device_train_batch_size=int(cfg.get("per_device_train_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("gradient_accumulation_steps", 8)),
        num_train_epochs=float(cfg.get("num_train_epochs", 1)),
        learning_rate=float(cfg.get("learning_rate", 5e-7)),
        lr_scheduler_type="cosine",
        warmup_steps=int(cfg.get("warmup_steps", 2)),
        bf16=bool(cfg.get("bf16", True)) and torch.cuda.is_available(),
        beta=float(cfg.get("beta", 0.1)),
        max_length=int(cfg.get("max_seq_length", 4096)),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=1,
        save_steps=int(cfg.get("save_steps", 50)),
        save_total_limit=2,
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
    trainer.save_model(out_dir)
    tok.save_pretrained(out_dir)


if __name__ == "__main__":
    main()
