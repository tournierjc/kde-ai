#!/usr/bin/env python3
"""Merge PEFT LoRA adapters into a full Hugging Face model directory."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="HF model id or local dir")
    p.add_argument(
        "--adapter",
        action="append",
        dest="adapters",
        required=True,
        help="LoRA adapter dir (repeat in merge order, e.g. SFT then DPO)",
    )
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("Need torch, transformers, peft on this machine") from exc

    for adapter in args.adapters:
        if not (Path(adapter) / "adapter_config.json").is_file():
            raise SystemExit(f"adapter missing: {adapter}")

    args.out.mkdir(parents=True, exist_ok=True)
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    print(f"loading base {args.base}", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype=dtype, trust_remote_code=True
    )
    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    for adapter in args.adapters:
        print(f"merging {adapter}", flush=True)
        model = PeftModel.from_pretrained(model, adapter)
        model = model.merge_and_unload()
    print(f"saving {args.out}", flush=True)
    model.save_pretrained(args.out, safe_serialization=True)
    tok.save_pretrained(args.out)
    print("done", flush=True)


if __name__ == "__main__":
    main()
