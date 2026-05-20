#!/usr/bin/env python3
"""Compute per-method per-case USD cost across all 6 splits.

Reads pinned provider list prices from
configs/pricing/snapshot_<date>.json and folds in:
  - reducer-side tokens from llm-summary-v1-*.jsonl manifests (real
    per-call API usage from Anthropic / OpenAI / OpenRouter)
  - diagnoser-side tokens from eval_diagnosis_*.json macro fields
    (consistent estimates derived from byte-size // 4)

Output: a markdown table suitable for paste into docs/leaderboard.md
plus per-family $/case for audit.

Why eval-manifest estimates for the diagnoser side?  Some older
diagnosis rows have _backfilled=True with usage=None (pre-2026-05-14
F2 fix in the Claude shim).  Eval-manifest macros are consistent
across all methods × diagnosers and treat every row identically.
The reducer-side numbers ARE from provider-reported usage because
that's what dominates llm-summary-v1-haiku's end-to-end cost.

Usage:
    python3 tools/compute_usd_costs.py
    python3 tools/compute_usd_costs.py --pricing configs/pricing/snapshot_2026_05_20.json
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

DEFAULT_PRICING = ROOT / "configs/pricing/snapshot_2026_05_20.json"

DIAG_TO_FAMILY_MODEL = {
    "real-debugger-v1": "claude-haiku-4-5",
    "real-debugger-v2": "claude-sonnet-4-6",
    "real-debugger-v3": "gpt-5-mini-2025-08-07",
}

SPLITS = ("dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress")


def load_pricing(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def reducer_haiku_per_case(pricing: dict) -> tuple[float, int]:
    p = pricing["models"]["claude-haiku-4-5"]
    total_in = total_out = n = 0
    for split in SPLITS:
        fp = ROOT / f"results/{split}/llm-summary-v1-haiku.jsonl"
        if not fp.exists():
            continue
        for line in fp.read_text().splitlines():
            row = json.loads(line)
            u = row.get("metadata", {}).get("usage") or {}
            total_in += u.get("input_tokens", 0)
            total_out += u.get("output_tokens", 0)
            n += 1
    if n == 0:
        return 0.0, 0
    cost = (total_in * p["input_per_million_usd"]
            + total_out * p["output_per_million_usd"]) / 1_000_000
    return cost / n, n


def diagnoser_per_method_per_family(pricing: dict) -> dict:
    """Return {(method, family_model): $/case avg case-weighted across splits}."""
    accum = {}
    for split in SPLITS:
        for diag, family_model in DIAG_TO_FAMILY_MODEL.items():
            ev = ROOT / f"results/{split}/eval_diagnosis_{diag}.json"
            if not ev.exists():
                continue
            d = json.loads(ev.read_text())
            n = d["case_count"]
            p = pricing["models"][family_model]
            for m in d["methods"]:
                method = m["context_method"]
                ctx = m.get("macro_context_tokens") or 0
                outp = m.get("macro_diagnosis_tokens") or 0
                usd_per_case = (ctx * p["input_per_million_usd"]
                                + outp * p["output_per_million_usd"]) / 1_000_000
                key = (method, family_model)
                accum.setdefault(key, {"sum": 0.0, "n": 0})
                accum[key]["sum"] += usd_per_case * n
                accum[key]["n"] += n
    return {k: v["sum"] / v["n"] if v["n"] else 0.0 for k, v in accum.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pricing", type=pathlib.Path, default=DEFAULT_PRICING)
    args = ap.parse_args()

    pricing = load_pricing(args.pricing)
    print(f"# USD costs from pricing snapshot: {pricing['snapshot_date']}")
    print(f"# Source note: {pricing['source_note'][:120]}…")
    print()

    reducer, n = reducer_haiku_per_case(pricing)
    print(f"# Reducer cost (haiku-summary): ${reducer:.4f}/case over {n} cases")
    print()

    fam_costs = diagnoser_per_method_per_family(pricing)
    methods = sorted(set(k[0] for k in fam_costs.keys()))

    print("| Method | Haiku $ | Sonnet $ | gpt-5-mini $ | Avg single-shot $ | Reducer $ | **Total $** |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for m in methods:
        h = fam_costs.get((m, "claude-haiku-4-5"), 0)
        s = fam_costs.get((m, "claude-sonnet-4-6"), 0)
        g = fam_costs.get((m, "gpt-5-mini-2025-08-07"), 0)
        avg = (h + s + g) / 3
        red = reducer if m == "llm-summary-v1-haiku" else 0
        total = avg + red
        red_s = f"${red:.4f}" if red else "—"
        print(f"| `{m}` | ${h:.4f} | ${s:.4f} | ${g:.4f} | ${avg:.4f} | {red_s} | **${total:.4f}** |")

    return 0


if __name__ == "__main__":
    sys.exit(main())
