"""
Generate flat CSVs for E9 review — one row per item, suitable for opening
in Excel / Numbers / Google Sheets / etc. and filling in the score columns.

Outputs two files in the batch dir:

  e9_absolute_<reviewer_id>.csv   one row per absolute item (32 rows)
  e9_pairwise_<reviewer_id>.csv   one row per pairwise item (16 rows)

The CSVs include the case ground-truth summary, the diagnosis bodies (or
both A/B for pairwise), and empty score columns the reviewer fills in.

After labeling, run:
  tools/build_e9_labels_from_csv.py
to materialize the proper jsonl labels file.

Usage:
    python3 tools/render_e9_review_csv.py \
        --batch-id e9_v1_3_hybrid_vs_grep_human_001 \
        --reviewer-id human_a
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def fmt_diagnosis_inline(diag: dict) -> str:
    """Compact one-cell representation of a diagnosis suitable for CSV."""
    parts = []
    parts.append(f"summary: {diag.get('summary', '').strip()}")
    parts.append(f"category: {diag.get('root_cause_category', '')}")
    parts.append(f"root_cause: {diag.get('root_cause', '')}")
    parts.append(f"confidence: {diag.get('confidence', 0)}")
    if diag.get("relevant_files"):
        parts.append(f"files: {diag['relevant_files']}")
    if diag.get("relevant_tests"):
        parts.append(f"tests: {diag['relevant_tests']}")
    if diag.get("evidence"):
        ev_parts = []
        for ev in diag["evidence"]:
            q = (ev.get("quote") or "").strip()
            r = (ev.get("reason") or "").strip()
            ev_parts.append(f"  - quote: {q[:200]} | reason: {r[:120]}")
        parts.append("evidence:\n" + "\n".join(ev_parts))
    if diag.get("suggested_fix"):
        parts.append(f"fix: {diag['suggested_fix']}")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--reviewer-id", required=True)
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    args = ap.parse_args(argv)

    if args.reviewer_id.startswith(("claude", "gpt", "sonnet", "opus", "haiku")) \
            or "expert" in args.reviewer_id:
        print(f"ERROR: reviewer_id {args.reviewer_id!r} looks like a model identifier; "
              f"use a human-shaped name like 'human_a' or your initials.",
              file=sys.stderr)
        return 1

    batch_dir = args.review_root / args.batch_id
    items = load_jsonl(batch_dir / "items.jsonl")
    if not items:
        print(f"ERROR: no items in {batch_dir}", file=sys.stderr)
        return 1

    abs_items = sorted(
        [it for it in items if it["label_type"] == "absolute"],
        key=lambda x: x["review_item_id"],
    )
    pair_items = sorted(
        [it for it in items if it["label_type"] == "pairwise"],
        key=lambda x: x["review_item_id"],
    )

    # ---- Absolute CSV ----
    abs_path = batch_dir / f"e9_absolute_{args.reviewer_id}.csv"
    with abs_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "review_item_id", "case_id", "framework", "ground_truth_summary",
            "diagnosis",
            # Score columns to fill
            "root_cause_correctness", "evidence_support", "localization_quality",
            "actionability", "hallucination_severity", "overall_usefulness",
            "abstention_appropriateness", "notes",
        ])
        for it in abs_items:
            cp = it.get("case_packet") or {}
            w.writerow([
                it["review_item_id"],
                it["case_id"],
                cp.get("framework", ""),
                cp.get("allowed_ground_truth_summary", ""),
                fmt_diagnosis_inline(it.get("diagnosis") or {}),
                # empty score cells
                "", "", "", "", "", "", "", "",
            ])

    # ---- Pairwise CSV ----
    pair_path = batch_dir / f"e9_pairwise_{args.reviewer_id}.csv"
    with pair_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "review_item_id", "case_id", "framework", "ground_truth_summary",
            "diagnosis_A", "diagnosis_B",
            # Score columns to fill — exactly one of {winner, tie, both_bad, insufficient_information}
            "winner_A_or_B",  # "A" or "B" or "" if not winner
            "tie",  # "true" or ""
            "both_bad",  # "true" or ""
            "insufficient_information",  # "true" or ""
            "reason",
        ])
        for it in pair_items:
            cp = it.get("case_packet") or {}
            w.writerow([
                it["review_item_id"],
                it["case_id"],
                cp.get("framework", ""),
                cp.get("allowed_ground_truth_summary", ""),
                fmt_diagnosis_inline(it.get("diagnosis_a") or {}),
                fmt_diagnosis_inline(it.get("diagnosis_b") or {}),
                "", "", "", "", "",
            ])

    print(f"Wrote {abs_path.relative_to(ROOT)}  ({len(abs_items)} rows)")
    print(f"Wrote {pair_path.relative_to(ROOT)}  ({len(pair_items)} rows)")
    print()
    print("Next:")
    print(f"  1. Open both CSVs in your spreadsheet tool of choice.")
    print(f"  2. Fill in the score columns (do NOT touch the first 4-6 columns).")
    print(f"  3. Save back as CSV (UTF-8).")
    print(f"  4. Run:")
    print(f"       python3 tools/build_e9_labels_from_csv.py --batch-id {args.batch_id} --reviewer-id {args.reviewer_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
