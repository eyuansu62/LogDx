"""
Validate reviewer label files for a batch.

Checks:
    - every label row has the required fields for its label_type
    - integer scores are in [0, 4]
    - every review_item_id exists in items.jsonl
    - `notes` / `reason` do not contain any locked method name
      (prevents silent unblinding)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


FORBIDDEN_METHOD_NAMES = [
    "raw", "tail", "grep", "rtk-read", "rtk-log", "rtk-err-cat",
    "llm-summary-v1-mock", "llm-summary-v1",
]

ABS_REQUIRED = {
    "root_cause_correctness", "evidence_support", "localization_quality",
    "actionability", "hallucination_severity", "overall_usefulness",
    "abstention_appropriateness",
}
ABS_INT_FIELDS = {
    "root_cause_correctness", "evidence_support", "localization_quality",
    "actionability", "hallucination_severity", "overall_usefulness",
}
ABS_APPROP = {"correct_abstention", "inappropriate_abstention", "not_applicable"}


def contains_forbidden(text: str) -> list[str]:
    hits: list[str] = []
    low = text.lower()
    for name in FORBIDDEN_METHOD_NAMES:
        # match the method name as a word-ish token so 'raw' doesn't hit
        # words like 'drawing'
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", low):
            hits.append(name)
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    args = ap.parse_args(argv)

    batch_dir = args.review_root / args.batch_id
    items_path = batch_dir / "items.jsonl"
    if not items_path.exists():
        print(f"ERROR: {items_path} missing.", file=sys.stderr)
        return 1
    item_ids = {json.loads(l)["review_item_id"]
                for l in items_path.read_text(encoding="utf-8").splitlines()
                if l.strip()}
    item_modes = {json.loads(l)["review_item_id"]: json.loads(l)["label_type"]
                  for l in items_path.read_text(encoding="utf-8").splitlines()
                  if l.strip()}

    labels_dir = batch_dir / "labels"
    if not labels_dir.is_dir():
        print(f"ERROR: {labels_dir} missing.", file=sys.stderr)
        return 1
    label_files = sorted(labels_dir.glob("*.jsonl"))
    if not label_files:
        print(f"ERROR: no reviewer_<id>.jsonl files under {labels_dir}.", file=sys.stderr)
        return 1

    errs: list[str] = []
    total = 0
    for lp in label_files:
        for line_no, line in enumerate(lp.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                label = json.loads(line)
            except json.JSONDecodeError as e:
                errs.append(f"{lp.name}:{line_no}: invalid JSON ({e})")
                continue
            total += 1
            rid = label.get("review_item_id")
            lt = label.get("label_type")
            if rid not in item_ids:
                errs.append(f"{lp.name}:{line_no}: unknown review_item_id {rid!r}")
                continue
            if lt != item_modes[rid]:
                errs.append(f"{lp.name}:{line_no}: {rid} is a {item_modes[rid]} item but label_type={lt}")
                continue
            if not label.get("reviewer_id"):
                errs.append(f"{lp.name}:{line_no}: missing reviewer_id")
            # Absolute mode required fields.
            if lt == "absolute":
                missing = [f for f in ABS_REQUIRED if f not in label]
                if missing:
                    errs.append(f"{lp.name}:{line_no}: missing absolute fields {missing}")
                for k in ABS_INT_FIELDS & set(label.keys()):
                    v = label[k]
                    if not isinstance(v, int) or not (0 <= v <= 4):
                        errs.append(f"{lp.name}:{line_no}: {k}={v!r} outside [0,4]")
                if label.get("abstention_appropriateness") not in ABS_APPROP:
                    errs.append(f"{lp.name}:{line_no}: abstention_appropriateness "
                                f"{label.get('abstention_appropriateness')!r} not in {sorted(ABS_APPROP)}")
            elif lt == "pairwise":
                signals = [label.get("winner") in ("A", "B"),
                            bool(label.get("tie")),
                            bool(label.get("both_bad")),
                            bool(label.get("insufficient_information"))]
                if not any(signals):
                    errs.append(f"{lp.name}:{line_no}: must set winner (A/B), tie, both_bad, or insufficient_information")
            # Anti-unblinding: scan notes + reason for forbidden method names.
            for fld in ("notes", "reason"):
                txt = label.get(fld) or ""
                hits = contains_forbidden(txt)
                if hits:
                    errs.append(f"{lp.name}:{line_no}: {fld} contains method name(s) {hits}")

    if errs:
        print(f"Validated {total} labels across {len(label_files)} reviewer file(s)",
              file=sys.stderr)
        print(f"- {len(errs)} issue(s)", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"Validated {total} labels across {len(label_files)} reviewer file(s): 0 issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
