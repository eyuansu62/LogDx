#!/usr/bin/env python3
"""Build per-split metadata jsonl files for the HuggingFace dataset viewer.

For each case under cases/<split>/<case_id>/, emit one flat JSON row to
huggingface/metadata/<split>.jsonl combining selected fields from
case.json, tags.json, and the two scalar fields of ground_truth.json.

The per-case bundle (raw.log + ground_truth.json + tags.json +
privacy_audit.json) remains the authoritative format and is fetched via
huggingface_hub.snapshot_download. These jsonl files exist solely so the
HF dataset viewer can render a schema-clean preview.
"""
from __future__ import annotations

import json
from pathlib import Path

# Fields lifted as-is from each per-case source file. All scalars or
# list[str] — nothing nested.
CASE_FIELDS = [
    "case_id", "repo", "source", "framework", "failure_category",
    "line_count", "byte_size", "workflow_name", "job_name", "notes",
]
TAGS_FIELDS = [
    "ecosystem", "primary_language", "ci_provider", "origin",
    "log_size_bucket", "signal_position", "diagnosis_difficulty",
    "multi_failure", "flaky_or_transient", "requires_repo_context",
    "evidence_formats", "noise_profile", "repo_visibility",
]

SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]


def build_row(case_dir: Path, split: str) -> dict:
    case = json.loads((case_dir / "case.json").read_text())
    tags = json.loads((case_dir / "tags.json").read_text())
    gt = json.loads((case_dir / "ground_truth.json").read_text())
    row = {"split": split, "case_dir": f"cases/{split}/{case_dir.name}"}
    for f in CASE_FIELDS:
        row[f] = case.get(f)
    for f in TAGS_FIELDS:
        row[f] = tags.get(f)
    rc = gt.get("root_cause") or {}
    row["root_cause_category"] = rc.get("category")
    row["root_cause_summary"] = rc.get("summary")
    return row


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "huggingface" / "metadata"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for split in SPLITS:
        split_dir = repo_root / "cases" / split
        if not split_dir.exists():
            print(f"  skip: {split} (no directory)")
            continue
        rows = [
            build_row(case_dir, split)
            for case_dir in sorted(split_dir.iterdir())
            if case_dir.is_dir() and (case_dir / "case.json").exists()
        ]
        out_path = out_dir / f"{split.replace('/', '_')}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        rel = out_path.relative_to(repo_root)
        print(f"  {split:14s} → {len(rows):2d} cases → {rel}")
        total += len(rows)
    print(f"Wrote {total} cases across {len(SPLITS)} splits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
