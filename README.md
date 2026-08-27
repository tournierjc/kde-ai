# kde-ai

[![CI](https://github.com/tournierjc/kde-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/tournierjc/kde-ai/actions/workflows/ci.yml)

Local KDE / CachyOS system agent: Plasma plasmoid (Chat, Memory, Skills, Config), SSH CLI, tool calling, manpage RAG, GPU yield, and a Spark-trained Qwen2.5 GGUF.

Weights live in VRAM only while answering. Privileged tools prompt on a TTY (`sudo`) or the session polkit agent. Passwords never enter logs, RPC, or the model.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
sudo pacman -S llama-cpp          # provides llama-server
./scripts/install.sh              # plasmoid, user daemon (window shortcut unset)
kde-ai doctor
kde-ai chat "What Plasma version am I on?"
# optional GUI: pip install -e ".[ui]" && kde-ai-ui
```

Install the plasmoid (Plasma 6):

```bash
./scripts/install.sh --prefix ~/.local
```

Fetch a GGUF (after install or into `~/.local/share/kde-ai/models/`):

```bash
./scripts/fetch-gguf.sh
```

Build the training corpus (30k + eval + DPO):

```bash
./scripts/build_dataset.sh
```

Fine-tune on a DGX Spark:

```bash
# on Spark
python training/train_sft.py --config training/configs/sft_qwen25_1_5b.yaml
./training/export_gguf.sh
python training/train_dpo.py --config training/configs/dpo_qwen25_1_5b.yaml
python scripts/eval_holdout.py --eval data/out/eval.jsonl
```

## Layout

See `docs/` for the protocol, tools, dataset, training, and packaging specifications.

## License

GPL-2.0-or-later for Plasma/C++/QML. Apache-2.0 for Python training scripts. Qwen weights remain under their own license.
