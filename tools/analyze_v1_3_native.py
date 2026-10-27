#!/usr/bin/env python3
"""Compare one SDK native-long raw panel with compatibility results."""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TRANSFER_PATH = ROOT / "tools" / "analyze_v1_3_transfer.py"
SPEC = importlib.util.spec_from_file_location("v1_3_transfer", TRANSFER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {TRANSFER_PATH}")
TRANSFER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSFER)


def paired_delta(
    left: dict, left_method: str, right: dict, right_method: str
) -> dict:
    deltas = []
    for (split, method, case_id), metrics in left.items():
        right_key = (split, right_method, case_id)
        if method == left_method:
            if right_key not in right:
                raise ValueError(f"missing paired comparison row: {right_key}")
            deltas.append(
                metrics["diagnosis_score_v1_1"]
                - right[right_key]["diagnosis_score_v1_1"]
            )
    return TRANSFER.paired_bootstrap(deltas)


def subset_comparison(native: dict, compat: dict, cases: set) -> dict:
    """Keep the same case denominator for raw, hybrid, and tail comparisons."""
    selected = {
        key: row for key, row in native.items()
        if key[1] == "raw" and (key[0], key[2]) in cases
    }
    if len(selected) != len(cases):
        raise ValueError("native panel does not contain every selected case")
    comparisons = {}
    for method in ("raw", "hybrid-grep-120k-rtk-tail-v3", "tail"):
        delta = paired_delta(selected, "raw", compat, method)
        scores = [compat[(s, method, c)]["diagnosis_score_v1_1"] for s, c in sorted(cases)]
        comparisons[method] = {
            "compat_mean_score": round(statistics.fmean(scores), 6) if scores else None,
            "paired_delta_native_minus_compat": delta,
        }
    scores = [row["diagnosis_score_v1_1"] for row in selected.values()]
    return {
        "case_count": len(cases),
        "cases": [{"split": s, "case_id": c} for s, c in sorted(cases)],
        "native_raw_mean_score": round(statistics.fmean(scores), 6) if scores else None,
        "comparisons": comparisons,
    }


def coverage_analysis(native: dict, compat: dict, native_accepted: set, compat_accepted: set) -> dict:
    all_cases = {(s, c) for s, method, c in native if method == "raw"}
    compat_cases = {(s, c) for s, method, c in compat if method == "raw"}
    if all_cases != compat_cases:
        raise ValueError("native and compatibility raw panels have different case sets")
    if not native_accepted <= all_cases or not compat_accepted <= all_cases:
        raise ValueError("accepted case set contains unknown cases")
    groups = {
        "both_accepted": native_accepted & compat_accepted,
        "newly_accepted_native": native_accepted - compat_accepted,
        "compat_only_accepted": compat_accepted - native_accepted,
        "neither_accepted": all_cases - (native_accepted | compat_accepted),
        "native_accepted": native_accepted,
    }
    return {name: subset_comparison(native, compat, cases) for name, cases in groups.items()}


def ranking_sensitivity(compat: dict, historical: dict, cases: set) -> dict:
    methods = {key[1] for key in compat} & {key[1] for key in historical}
    def means(rows: dict) -> dict:
        return {
            method: statistics.fmean(
                rows[(split, method, case)]["diagnosis_score_v1_1"]
                for split, case in sorted(cases)
            ) for method in sorted(methods)
        } if cases else {}
    rho, count = TRANSFER.spearman(means(compat), means(historical))
    return {"case_count": len(cases), "common_methods": count,
            "rho": round(rho, 6) if rho is not None else None,
            "interpretation": "exploratory subset sensitivity, not a replacement for the full-corpus estimate"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-diagnoser", required=True)
    parser.add_argument("--compat-diagnoser", required=True)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    native, native_means = TRANSFER.load_eval(args.native_diagnoser, args.results_dir)
    compat, compat_means = TRANSFER.load_eval(args.compat_diagnoser, args.results_dir)
    native_runtime = TRANSFER.load_runtime(args.native_diagnoser, args.results_dir)
    if set(native_means) != {"raw"}:
        raise RuntimeError(f"native panel must contain only raw: {sorted(native_means)}")
    hybrid = "hybrid-grep-120k-rtk-tail-v3"
    native_accepted = TRANSFER.accepted_cases(args.native_diagnoser, "raw", args.results_dir)
    compat_accepted = TRANSFER.accepted_cases(args.compat_diagnoser, "raw", args.results_dir)
    historical, _ = TRANSFER.historical_panel(
        ["real-debugger-v1", "real-debugger-v2", "real-debugger-v3"], args.results_dir
    )
    output = {
        "native_diagnoser": args.native_diagnoser,
        "compat_diagnoser": args.compat_diagnoser,
        "case_count": len(native),
        "native_raw": {
            **{
                f"{metric}_mean": value
                for metric, value in native_means["raw"].items()
            },
            "runtime": native_runtime["raw"],
        },
        "compat_raw_score_v1_1_mean": compat_means["raw"]["diagnosis_score_v1_1"],
        "compat_hybrid_v3_score_v1_1_mean": compat_means[hybrid]["diagnosis_score_v1_1"],
        "paired_delta_native_raw_vs_compat_raw": paired_delta(
            native, "raw", compat, "raw"
        ),
        "paired_delta_native_raw_vs_compat_hybrid_v3": paired_delta(
            native, "raw", compat, hybrid
        ),
        "paired_delta_native_raw_vs_compat_tail": paired_delta(native, "raw", compat, "tail"),
        "coverage_analysis": coverage_analysis(native, compat, native_accepted, compat_accepted),
        "compat_ranking_on_both_accepted_cases": ranking_sensitivity(
            compat, historical, native_accepted & compat_accepted
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
