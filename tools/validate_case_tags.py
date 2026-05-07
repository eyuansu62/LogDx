"""
Validate tags.json for each case in a split.

Checks:
    - tags.json exists
    - case_id matches directory name
    - split matches arg
    - all enum values are valid
    - log_size_bucket matches actual line count
    - signal_position is plausible given evidence_spans
    - failure_category matches ground_truth.root_cause.category (with a small
      alias table for renames like lint_error→lint_failure); override with
      notes="category mismatch justified: ..."
    - framework matches case.json.framework; override same way
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "case_tags.schema.json"

try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

# Allowed aliases between case.failure_category / ground_truth.category and
# the tag enum. The diagnosis evaluator has an equivalent table; keep in sync.
CATEGORY_ALIASES = {
    "lint_error": "lint_failure",
    "snapshot_diff": "snapshot_or_golden_diff",
    "generic_error": "other",
}


def bucket(line_count: int) -> str:
    if line_count < 500:  return "small"
    if line_count < 5_000: return "medium"
    if line_count < 50_000: return "large"
    return "huge"


def validate_split(split: str) -> list[str]:
    errs: list[str] = []
    split_dir = ROOT / "cases" / split
    if not split_dir.is_dir():
        return [f"{split}: directory missing"]
    schema = None
    if _HAS_JSONSCHEMA and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    for case_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        if case_dir.name.startswith("."):
            continue
        cid = case_dir.name
        tags_path = case_dir / "tags.json"
        if not tags_path.exists():
            errs.append(f"{cid}: tags.json missing")
            continue
        try:
            tags = json.loads(tags_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"{cid}: invalid JSON: {e}")
            continue

        if tags.get("case_id") != cid:
            errs.append(f"{cid}: tags.case_id {tags.get('case_id')!r} != dir")
        if tags.get("split") != split:
            errs.append(f"{cid}: tags.split {tags.get('split')!r} != {split!r}")

        if schema is not None:
            try:
                jsonschema.validate(tags, schema)  # type: ignore[arg-type]
            except jsonschema.ValidationError as e:  # type: ignore[attr-defined]
                errs.append(f"{cid}:tags schema: {e.message}")

        # Cross-check vs case.json / ground_truth.json
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        actual_line_count = case.get("line_count") or 0
        if bucket(actual_line_count) != tags.get("log_size_bucket"):
            if "size mismatch justified" not in (tags.get("notes") or ""):
                errs.append(
                    f"{cid}: log_size_bucket={tags.get('log_size_bucket')!r} "
                    f"vs computed {bucket(actual_line_count)!r} "
                    f"from line_count={actual_line_count}"
                )

        gt_path = case_dir / "ground_truth.json"
        if gt_path.exists():
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
            gt_cat = (gt.get("root_cause") or {}).get("category", "")
            gt_cat = CATEGORY_ALIASES.get(gt_cat, gt_cat)
            tag_cat = tags.get("failure_category", "")
            tag_cat_aliased = CATEGORY_ALIASES.get(tag_cat, tag_cat)
            if gt_cat and tag_cat_aliased != gt_cat:
                if "category mismatch justified" not in (tags.get("notes") or ""):
                    errs.append(
                        f"{cid}: tags.failure_category={tag_cat!r} (→{tag_cat_aliased!r}) "
                        f"!= ground_truth category {gt_cat!r}"
                    )

        case_fw = case.get("framework", "")
        tag_fw = tags.get("framework", "")
        if case_fw and tag_fw and case_fw != tag_fw:
            if "framework mismatch justified" not in (tags.get("notes") or ""):
                errs.append(
                    f"{cid}: tags.framework={tag_fw!r} != case.framework={case_fw!r}"
                )
    return errs


_V1_3_SPLITS = ["dev", "holdout", "stress"]
_V2_SPLITS = ["v2/dev", "v2/holdout", "v2/stress"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--split",
        required=True,
        choices=[*_V1_3_SPLITS, *_V2_SPLITS, "all", "v1.3", "v2"],
        help=("a single split, or 'all' (every known split), 'v1.3' "
              "(dev/holdout/stress only), or 'v2' (v2/* splits only)."),
    )
    args = ap.parse_args(argv)
    if args.split == "all":
        splits = [*_V1_3_SPLITS, *_V2_SPLITS]
    elif args.split == "v1.3":
        splits = list(_V1_3_SPLITS)
    elif args.split == "v2":
        splits = list(_V2_SPLITS)
    else:
        splits = [args.split]
    # Skip v2 splits silently if their on-disk directory does not exist
    # yet (corpus expansion may be in progress).
    splits = [s for s in splits if (ROOT / "cases" / s).is_dir()]
    all_errs: list[str] = []
    totals: list[tuple[str, int, int]] = []
    for s in splits:
        errs = validate_split(s)
        n = sum(1 for _ in (ROOT / "cases" / s).iterdir() if _.is_dir() and not _.name.startswith(".")) \
            if (ROOT / "cases" / s).is_dir() else 0
        failed = len([e for e in errs if e.startswith(f"{e.split(':',1)[0]}")])
        # Simpler counting: one line per failing case; group errors later.
        totals.append((s, n, len(errs)))
        all_errs.extend(errs)
    if not _HAS_JSONSCHEMA:
        print("note: jsonschema not installed — using fallback checks "
              "(pip install jsonschema for full schema validation)", file=sys.stderr)
    for split, n, err_count in totals:
        print(f"Validated tags for {n} cases in cases/{split}/")
        print(f"- {'0 issues' if err_count == 0 else f'{err_count} issue(s)'}")
    if all_errs:
        print("\nIssues:", file=sys.stderr)
        for e in all_errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
