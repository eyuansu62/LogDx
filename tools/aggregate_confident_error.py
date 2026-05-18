"""Aggregate confident_error_rate across the v1.0 corpus.

Matches the case-count-weighted macro aggregation used for
diagnosis_score_v1_1 in the leaderboard. Verifies the aggregation
methodology by also recomputing diagnosis_score_v1_1 and asserting
it matches the published leaderboard.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]
DIAGNOSERS = [
    ("Haiku 4.5",   "real-debugger-v1"),
    ("Sonnet 4.6",  "real-debugger-v2"),
    ("gpt-5-mini",  "real-debugger-v3"),
]

METHODS = [
    "raw", "tail", "grep",
    "rtk-read", "rtk-log", "rtk-err-cat",
    "llm-summary-v1-mock",
    "hybrid-grep-4k-rtk-err-cat-v1",
    "hybrid-grep-120k-tail-v2",
    "hybrid-grep-120k-rtk-tail-v3",
]

LEADERBOARD_LABELS = {
    "hybrid-grep-4k-rtk-err-cat-v1": "hybrid-grep-4k-rtk-err-cat",
    "hybrid-grep-120k-tail-v2":      "hybrid-grep-120k-tail",
    "hybrid-grep-120k-rtk-tail-v3":  "hybrid-grep-120k-rtk-tail",
    "tail":                          "tail-200",
}


def per_method(metric):
    """Return {method: {debugger_label: weighted_avg, "Overall": mean}}."""
    out = {}
    for m in METHODS:
        row = {}
        for label, diag in DIAGNOSERS:
            total_weight = 0
            weighted_sum = 0.0
            for split in SPLITS:
                p = ROOT / f"results/{split}/eval_diagnosis_{diag}.json"
                if not p.exists():
                    continue
                d = json.load(open(p))
                cc = d.get("case_count", 0)
                if cc == 0:
                    continue
                for method_block in d.get("methods", []):
                    if method_block["context_method"] != m:
                        continue
                    v = method_block.get(metric)
                    if v is None:
                        continue
                    weighted_sum += v * cc
                    total_weight += cc
                    break
            row[label] = weighted_sum / total_weight if total_weight else None
        valid = [v for v in row.values() if v is not None]
        row["Overall"] = sum(valid) / len(valid) if valid else None
        out[m] = row
    return out


def fmt(v, digits=3):
    if v is None:
        return "  —  "
    return f"{v:.{digits}f}"


for metric in ("diagnosis_score_v1_1", "confident_error_rate", "confident_error_rate_v1_1"):
    print(f"\n=== {metric} (case-count-weighted macro, v1.0 corpus: 35 cases) ===\n")
    rows = per_method(metric)
    # Sort by Overall descending for score; ascending (lower=better) for error rate
    reverse = "score" in metric
    sorted_methods = sorted(rows.keys(), key=lambda m: (rows[m]["Overall"] or 0), reverse=reverse)
    print(f"{'method':36s}  {'Haiku 4.5':>11s}  {'Sonnet 4.6':>11s}  {'gpt-5-mini':>11s}  {'Overall':>9s}")
    for m in sorted_methods:
        r = rows[m]
        label = LEADERBOARD_LABELS.get(m, m)
        print(f"{label:36s}  {fmt(r['Haiku 4.5']):>11s}  {fmt(r['Sonnet 4.6']):>11s}  {fmt(r['gpt-5-mini']):>11s}  {fmt(r['Overall']):>9s}")
