"""
Build cases/<split>/split_manifest.json — per-case content hashes + tallies.

Used by M8 protocol freezing + contamination checks.

Usage:
    python tools/build_split_manifest.py --split dev
    python tools/build_split_manifest.py --split holdout
    python tools/build_split_manifest.py --split all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_split(split: str) -> dict:
    split_dir = ROOT / "cases" / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"split directory not found: {split_dir}")
    cases: list[dict] = []
    for case_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        if case_dir.name.startswith("."):
            continue
        raw_path = case_dir / "raw.log"
        case_path = case_dir / "case.json"
        gt_path = case_dir / "ground_truth.json"
        for p in (raw_path, case_path, gt_path):
            if not p.exists():
                raise FileNotFoundError(f"missing {p.relative_to(ROOT)} in {case_dir}")
        case = json.loads(case_path.read_text(encoding="utf-8"))
        cases.append({
            "case_id": case["case_id"],
            "raw_log_sha256":      sha256_path(raw_path),
            "case_json_sha256":    sha256_path(case_path),
            "ground_truth_sha256": sha256_path(gt_path),
            "line_count":       int(case.get("line_count", 0)),
            "byte_size":        int(case.get("byte_size", 0)),
            "framework":        case.get("framework", "unknown"),
            "failure_category": case.get("failure_category", "unknown"),
        })
    manifest = {
        "split": split,
        "case_count": len(cases),
        "cases": cases,
        "framework_counts": dict(Counter(c["framework"] for c in cases)),
        "category_counts":  dict(Counter(c["failure_category"] for c in cases)),
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a split manifest JSON.")
    ap.add_argument("--split", required=True,
                    help="Split name (dev, holdout, stress, ...) or 'all'.")
    args = ap.parse_args(argv)
    if args.split == "all":
        splits = [p.name for p in sorted((ROOT / "cases").iterdir())
                  if p.is_dir() and not p.name.startswith(".")
                  and any(q.is_dir() for q in p.iterdir())]
    else:
        splits = [args.split]
    ok = True
    for split in splits:
        try:
            manifest = build_split(split)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            ok = False
            continue
        out_path = ROOT / "cases" / split / "split_manifest.json"
        out_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {out_path.relative_to(ROOT)}  "
              f"({manifest['case_count']} cases, "
              f"frameworks={manifest['framework_counts']}, "
              f"categories={manifest['category_counts']})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
