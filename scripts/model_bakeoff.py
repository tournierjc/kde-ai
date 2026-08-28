#!/usr/bin/env python3
"""Run holdout/daily predictions through llama-server and score model candidates."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scripts.bakeoff_lib import compare_predictions, load_jsonl  # noqa: E402


def _prompt_prefix(messages: list[dict]) -> list[dict]:
    """Messages through the first user turn (first model decision point)."""
    out: list[dict] = []
    for m in messages:
        out.append(m)
        if m.get("role") == "user":
            break
    return out


def _allowed_tools(meta: dict) -> list[str] | None:
    from kde_ai.tools.registry import SCHEMAS

    skills = meta.get("skills") or []
    if not skills:
        return None
    from kde_ai.skills import load_skills_from

    allsk = load_skills_from(ROOT / "skills")
    names: set[str] = set()
    for sid in skills:
        sk = allsk.get(sid)
        if sk and sk.tools:
            names.update(sk.tools)
    if not names:
        return None
    allow = {s["name"] for s in SCHEMAS}
    return sorted(names & allow)


def cmd_predict(args: argparse.Namespace) -> None:
    from kde_ai.config import load_config
    from kde_ai.llm import LlamaRuntime

    rows = load_jsonl(args.suite)
    cfg = load_config()
    if args.gguf:
        cfg["llm.gguf"] = str(args.gguf)
    runtime = LlamaRuntime(cfg)
    out_rows: list[dict] = []
    timings: list[float] = []

    try:
        for i, rec in enumerate(rows):
            meta = rec.get("meta") or {}
            prefix = _prompt_prefix(rec["messages"])
            allowed = _allowed_tools(meta)
            t0 = time.perf_counter()
            resp = runtime.chat(prefix, tools=None, allowed_tool_names=allowed)
            timings.append(time.perf_counter() - t0)
            msg = (resp.get("choices") or [{}])[0].get("message") or {}
            pred_messages = prefix + [
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    **({"tool_calls": msg["tool_calls"]} if msg.get("tool_calls") else {}),
                }
            ]
            out_rows.append(
                {
                    "id": rec["id"],
                    "messages": pred_messages,
                    "meta": meta,
                    "checks": rec.get("checks"),
                }
            )
            if args.limit and i + 1 >= args.limit:
                break
    finally:
        runtime.unload()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "n": len(out_rows),
        "gguf": cfg.get("llm.gguf"),
        "suite": str(args.suite),
        "p50_s": sorted(timings)[len(timings) // 2] if timings else 0,
        "p95_s": sorted(timings)[int(len(timings) * 0.95)] if timings else 0,
        "mean_s": sum(timings) / len(timings) if timings else 0,
    }
    timing_path = args.out.with_suffix(".timing.json")
    timing_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def cmd_score(args: argparse.Namespace) -> None:
    gold = load_jsonl(args.gold)
    pred = load_jsonl(args.predictions)
    metrics = compare_predictions(gold, pred)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    if args.strict:
        from scripts.eval_holdout import GATES

        fmt = metrics["format"]
        fail = []
        for k, thr in GATES.items():
            val = fmt.get(k, 0)
            if k in ("invented_bugzilla", "rag_hallucination"):
                if val > thr:
                    fail.append(k)
            elif val < thr:
                fail.append(k)
        if metrics["daily_substance"] < args.min_substance:
            fail.append("daily_substance")
        if fail:
            raise SystemExit("score gate failed: " + ",".join(fail))


def cmd_compare(args: argparse.Namespace) -> None:
    table = []
    for path in args.metrics:
        data = json.loads(path.read_text(encoding="utf-8"))
        table.append(
            {
                "file": str(path),
                "composite_hint": data.get("composite_hint"),
                "daily_substance": data.get("daily_substance"),
                "tool_match_at1": data.get("tool_match_at1"),
                "valid_tool_json": data.get("format", {}).get("valid_tool_json"),
            }
        )
    table.sort(key=lambda r: r.get("composite_hint") or 0, reverse=True)
    print(json.dumps(table, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("predict", help="Run suite through llama-server")
    pp.add_argument("--suite", type=Path, required=True)
    pp.add_argument("--out", type=Path, required=True)
    pp.add_argument("--gguf", type=Path, default=None)
    pp.add_argument("--limit", type=int, default=0)
    pp.set_defaults(func=cmd_predict)

    ps = sub.add_parser("score", help="Score predictions vs gold")
    ps.add_argument("--gold", type=Path, required=True)
    ps.add_argument("--predictions", type=Path, required=True)
    ps.add_argument("--out", type=Path, default=Path("data/out/bakeoff_score.json"))
    ps.add_argument("--strict", action="store_true")
    ps.add_argument("--min-substance", type=float, default=0.85)
    ps.set_defaults(func=cmd_score)

    pc = sub.add_parser("compare", help="Rank metrics JSON files")
    pc.add_argument("metrics", type=Path, nargs="+")
    pc.set_defaults(func=cmd_compare)

    args = p.parse_args()
    if args.cmd == "predict" and os.environ.get("KDE_AI_FAKE_LLM") != "1":
        gguf = args.gguf or Path(os.path.expanduser("~/.local/share/kde-ai/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"))
        if not gguf.exists():
            print(f"warning: GGUF not found at {gguf}; set --gguf or KDE_AI_FAKE_LLM=1", file=sys.stderr)
    args.func(args)


if __name__ == "__main__":
    main()
