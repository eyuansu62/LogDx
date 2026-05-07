"""
Convert filled E9 review CSVs back into the standard
`review/batches/.../labels/reviewer_<id>.jsonl` format that
`tools/validate_human_review_labels.py` and
`tools/analyze_human_review.py` consume.

Reads:
    review/batches/<batch_id>/e9_absolute_<reviewer_id>.csv
    review/batches/<batch_id>/e9_pairwise_<reviewer_id>.csv

Writes:
    review/batches/<batch_id>/labels/reviewer_<reviewer_id>.jsonl

Usage:
    python3 tools/build_e9_labels_from_csv.py \
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


INT_FIELDS = (
    "root_cause_correctness", "evidence_support", "localization_quality",
    "actionability", "hallucination_severity", "overall_usefulness",
)
ABSTENTION_VALUES = ("appropriate", "not_appropriate", "not_applicable",
                     # validator's exact accepted values are different; remap below
                     "correct_abstention", "inappropriate_abstention")


def normalize_abstention(v: str) -> str:
    """The label validator expects exactly one of:
        correct_abstention | inappropriate_abstention | not_applicable

    The plan-facing rubric uses 'appropriate' / 'not_appropriate' /
    'not_applicable' for human readability. Translate."""
    s = (v or "").strip().lower()
    if s in ("appropriate", "correct_abstention"):
        return "correct_abstention"
    if s in ("not_appropriate", "inappropriate_abstention"):
        return "inappropriate_abstention"
    if s in ("not_applicable", "n/a", "na", ""):
        return "not_applicable"
    raise ValueError(f"unrecognized abstention value: {v!r}")


def to_int_strict(v: str, *, field: str, row_id: str) -> int:
    s = (v or "").strip()
    if s == "":
        raise ValueError(f"{row_id}: empty value for required field {field!r}")
    try:
        n = int(s)
    except ValueError:
        raise ValueError(f"{row_id}: non-integer {v!r} for {field!r}")
    if not (0 <= n <= 4):
        raise ValueError(f"{row_id}: {field!r} = {n} outside [0,4]")
    return n


def to_bool_lenient(v: str) -> bool:
    s = (v or "").strip().lower()
    return s in ("true", "1", "yes", "y", "t")


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
    abs_csv = batch_dir / f"e9_absolute_{args.reviewer_id}.csv"
    pair_csv = batch_dir / f"e9_pairwise_{args.reviewer_id}.csv"
    if not abs_csv.exists():
        print(f"ERROR: {abs_csv} missing.", file=sys.stderr)
        return 1
    if not pair_csv.exists():
        print(f"ERROR: {pair_csv} missing.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    errors: list[str] = []

    # Absolute
    with abs_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rid = r.get("review_item_id", "")
            try:
                row = {
                    "review_item_id": rid,
                    "reviewer_id": args.reviewer_id,
                    "label_type": "absolute",
                }
                for fld in INT_FIELDS:
                    row[fld] = to_int_strict(r.get(fld, ""), field=fld, row_id=rid)
                row["abstention_appropriateness"] = normalize_abstention(
                    r.get("abstention_appropriateness", "")
                )
                notes = (r.get("notes") or "").strip()
                if notes:
                    row["notes"] = notes
                rows.append(row)
            except ValueError as e:
                errors.append(str(e))

    # Pairwise
    with pair_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rid = r.get("review_item_id", "")
            try:
                row: dict = {
                    "review_item_id": rid,
                    "reviewer_id": args.reviewer_id,
                    "label_type": "pairwise",
                }
                w = (r.get("winner_A_or_B") or "").strip().upper()
                tie = to_bool_lenient(r.get("tie", ""))
                bb = to_bool_lenient(r.get("both_bad", ""))
                ii = to_bool_lenient(r.get("insufficient_information", ""))
                signals = [w in ("A", "B"), tie, bb, ii]
                if sum(1 for x in signals if x) != 1:
                    raise ValueError(
                        f"{rid}: pairwise must set exactly ONE of "
                        f"{{winner=A|B, tie=true, both_bad=true, "
                        f"insufficient_information=true}}; got "
                        f"winner={w!r}, tie={tie}, both_bad={bb}, "
                        f"insufficient_information={ii}"
                    )
                if w in ("A", "B"):
                    row["winner"] = w
                if tie:
                    row["tie"] = True
                if bb:
                    row["both_bad"] = True
                if ii:
                    row["insufficient_information"] = True
                reason = (r.get("reason") or "").strip()
                if reason:
                    row["reason"] = reason
                rows.append(row)
            except ValueError as e:
                errors.append(str(e))

    if errors:
        print(f"ERROR: {len(errors)} row(s) failed validation:", file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ...and {len(errors) - 20} more", file=sys.stderr)
        return 1

    out_p = batch_dir / "labels" / f"reviewer_{args.reviewer_id}.jsonl"
    out_p.parent.mkdir(exist_ok=True)
    with out_p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {out_p.relative_to(ROOT)}  ({len(rows)} labels)")
    print(f"  - {sum(1 for r in rows if r['label_type'] == 'absolute')} absolute")
    print(f"  - {sum(1 for r in rows if r['label_type'] == 'pairwise')} pairwise")
    print()
    print("Now run:")
    print(f"  python3 tools/validate_human_review_labels.py --batch-id {args.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
