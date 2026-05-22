#!/usr/bin/env python3
"""Reproduce the numbers in agent-trajectory-token-anatomy.md.

Reads agent_v1 trajectory data from results/<split>/diagnoses/real-agent-v1/
and prints the 5 findings tables. Output should match what's in the
analysis doc exactly (numbers regenerated from committed manifests).

Usage:
    python3 docs/analysis/agent-trajectory-token-anatomy.py
"""
import json
import pathlib
from collections import defaultdict


SPLITS = ("dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def load_rows():
    rows = []
    for split in SPLITS:
        ddir = ROOT / f"results/{split}/diagnoses/real-agent-v1"
        if not ddir.exists():
            continue
        for f in ddir.glob("*.jsonl"):
            method = f.stem
            for line in f.read_text().splitlines():
                row = json.loads(line)
                ma = row.get("agent_metadata") or {}
                mu = (row.get("metadata", {}).get("model_info") or {}).get("usage") or {}
                rows.append({
                    "case": row["case_id"],
                    "method": method,
                    "split": split,
                    "iters": ma.get("iterations", 0),
                    "tool_calls": ma.get("tool_call_count", 0),
                    "total_in": ma.get("total_input_tokens_consumed", 0),
                    "total_out": ma.get("total_output_tokens_consumed", 0),
                    "or_cost": mu.get("cost", 0) or 0,
                    "tool_calls_list": ma.get("tool_calls", []),
                })
    return rows


def main():
    rows = load_rows()
    print(f"=== {len(rows)} agent_v1 rows ===\n")

    # ---- Finding 1: input vs output ----
    total_in = sum(r["total_in"] for r in rows)
    total_out = sum(r["total_out"] for r in rows)
    print("=== Finding 1: input vs output ratio ===")
    print(f"  input  : {total_in:>12,} ({total_in/(total_in+total_out)*100:.1f}%)")
    print(f"  output : {total_out:>12,} ({total_out/(total_in+total_out)*100:.1f}%)")
    print()

    # ---- Finding 2: per-method input ----
    per_method = defaultdict(lambda: {"in": 0, "out": 0, "iters": 0, "tools": 0, "cost": 0, "n": 0})
    for r in rows:
        pm = per_method[r["method"]]
        pm["in"] += r["total_in"]
        pm["out"] += r["total_out"]
        pm["iters"] += r["iters"]
        pm["tools"] += r["tool_calls"]
        pm["cost"] += r["or_cost"]
        pm["n"] += 1

    print("=== Finding 2: per-method input/output tokens (sorted asc) ===")
    print(f"{'method':<33} {'in/case':>9} {'out/case':>9} {'iters':>5} {'tools':>5} {'$/case':>8}")
    for m, pm in sorted(per_method.items(), key=lambda x: x[1]["in"] / max(x[1]["n"], 1)):
        if pm["n"] == 0:
            continue
        print(f"{m:<33} {pm['in']//pm['n']:>9,} {pm['out']//pm['n']:>9} "
              f"{pm['iters']/pm['n']:>5.1f} {pm['tools']/pm['n']:>5.2f} "
              f"${pm['cost']/pm['n']:>7.4f}")
    print()

    # ---- Finding 3: tokens per iteration ----
    print("=== Finding 3: tokens per iteration ===")
    print(f"{'method':<33} {'tok/iter':>10}")
    by_iter = defaultdict(lambda: {"total_in": 0, "total_iter": 0})
    for r in rows:
        if r["iters"] > 0:
            by_iter[r["method"]]["total_in"] += r["total_in"]
            by_iter[r["method"]]["total_iter"] += r["iters"]
    for m, pi in sorted(by_iter.items(),
                        key=lambda x: -x[1]["total_in"] / max(x[1]["total_iter"], 1)):
        avg = pi["total_in"] / pi["total_iter"]
        print(f"  {m:<33} {avg:>10,.0f}")
    print()

    # ---- Finding 4: tool usage distribution ----
    tool_count = defaultdict(int)
    for r in rows:
        for tc in r["tool_calls_list"]:
            tool_count[tc.get("tool", "?")] += 1
    total_tc = sum(tool_count.values()) or 1
    print(f"=== Finding 4: tool usage distribution ({total_tc} total invocations) ===")
    for t, n in sorted(tool_count.items(), key=lambda x: -x[1]):
        print(f"  {t:<22} {n:>5}  ({n/total_tc*100:5.1f}%)")
    print()

    # ---- Finding 5: worst-case agent runs ----
    print("=== Finding 5: top 5 most-expensive single agent runs ===")
    for r in sorted(rows, key=lambda x: -x["total_in"])[:5]:
        print(f"  {r['split']:<11} / {r['method']:<28} "
              f"{r['case'][:42]:<42} "
              f"in={r['total_in']:>7,} iters={r['iters']} "
              f"tools={r['tool_calls']} ${r['or_cost']:.4f}")


if __name__ == "__main__":
    main()
