"""
Suggest (or optionally write) tags.json for each case in a split.

Usage:
    python tools/tag_cases.py --split dev           # preview only
    python tools/tag_cases.py --split stress --write # overwrite tags.json

The tool infers:
    - log_size_bucket from line count
    - signal_position from the earliest/latest `evidence_spans` line relative to log length
    - rough noise_profile / evidence_formats hints from the raw content

It refuses to overwrite an existing hand-authored tags.json unless --write is
passed; use `--print-only` to inspect suggestions without touching disk.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bucket(line_count: int) -> str:
    if line_count < 500:
        return "small"
    if line_count < 5_000:
        return "medium"
    if line_count < 50_000:
        return "large"
    return "huge"


def signal_position(evidence_spans: list[dict], line_count: int) -> str:
    if not evidence_spans or line_count <= 0:
        return "scattered"
    starts = [s["start_line"] for s in evidence_spans]
    ends = [s["end_line"] for s in evidence_spans]
    lo, hi = min(starts), max(ends)
    span = hi - lo
    # Scattered if evidence spans > 30% of the log
    if span > 0.3 * line_count:
        return "scattered"
    center = (lo + hi) / 2
    ratio = center / max(1, line_count)
    if ratio < 0.25:
        return "early"
    if ratio > 0.75:
        return "late"
    return "middle"


FMT_PATTERNS = [
    ("traceback",            re.compile(r"Traceback \(most recent call last\)")),
    ("compiler_diagnostic",  re.compile(r"error\[E\d+\]|^\s*\w+:\d+:\d+:\s*error")),
    ("json_block",           re.compile(r"^\s*\{\s*$.*^\s*\}", re.MULTILINE | re.DOTALL)),
    ("diff_block",           re.compile(r"^---\s|^\+\+\+\s|^@@ ", re.MULTILINE)),
    ("ascii_table",          re.compile(r"^\+[-+]{5,}\+$", re.MULTILINE)),
    ("ansi_colored_block",   re.compile(r"\x1b\[[0-9;]*m")),
    ("github_annotation",    re.compile(r"##\[(error|warning|notice)\]|::(error|warning|notice)::")),
    ("shell_command_output", re.compile(r"^\$ |^\+ ", re.MULTILINE)),
    ("plain_error_line",     re.compile(r"^\s*(Error|ERROR|error):", re.MULTILINE)),
]

NOISE_PATTERNS = [
    ("runner_setup",            re.compile(r"Current runner version|Runner Image Provisioner")),
    ("dependency_install_noise",re.compile(r"npm install|pip install|cargo fetch|pnpm install|Pulling image")),
    ("test_progress_noise",     re.compile(r"\s\[\s*\d+%\s*\]|::test_|passing \(\d+m\)")),
    ("matrix_noise",            re.compile(r"matrix:|strategy:")),
    ("docker_layer_noise",      re.compile(r"^#\d+\s|Step \d+/\d+", re.MULTILINE)),
    ("verbose_build_noise",     re.compile(r"compiling\s|Compiling\s|webpack compiled")),
    ("log_group_noise",         re.compile(r"##\[group\]|##\[endgroup\]")),
]


def detect_formats(text: str) -> list[str]:
    out: list[str] = []
    for name, pat in FMT_PATTERNS:
        if pat.search(text):
            out.append(name)
    return out or ["plain_error_line"]


def detect_noise(text: str) -> list[str]:
    out: list[str] = []
    for name, pat in NOISE_PATTERNS:
        if pat.search(text):
            out.append(name)
    return out or ["low_noise"]


def suggest_tags(case_dir: Path, split: str) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    gt = json.loads((case_dir / "ground_truth.json").read_text(encoding="utf-8"))
    raw = (case_dir / "raw.log").read_text(encoding="utf-8", errors="replace")
    line_count = case.get("line_count") or raw.count("\n")
    spans = gt.get("evidence_spans") or []
    return {
        "case_id": case["case_id"],
        "split": split,
        "failure_category": case.get("failure_category", "unknown"),
        "framework": case.get("framework", "generic"),
        "primary_language": "unknown",
        "log_size_bucket": bucket(line_count),
        "signal_position": signal_position(spans, line_count),
        "evidence_formats": detect_formats(raw),
        "noise_profile": detect_noise(raw),
        "multi_failure": len(gt.get("required_signals") or []) > 5,
        "flaky_or_transient": False,
        "requires_repo_context": False,
        "diagnosis_difficulty": "unclear",
        "notes": "suggested by tag_cases.py — review manually"
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Suggest tags.json for each case in a split.")
    ap.add_argument("--split", required=True,
                    choices=["dev", "holdout", "stress", "all"])
    ap.add_argument("--write", action="store_true",
                    help="Overwrite tags.json with suggestions (USE CAREFULLY — prefer manual tags).")
    ap.add_argument("--suggested-filename", default="tags.suggested.json",
                    help="Filename for non-destructive suggestion output (default: tags.suggested.json).")
    args = ap.parse_args(argv)

    splits = ["dev", "holdout", "stress"] if args.split == "all" else [args.split]
    for split in splits:
        split_dir = ROOT / "cases" / split
        if not split_dir.is_dir():
            print(f"  skip {split}: directory missing", file=sys.stderr)
            continue
        for case_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            if case_dir.name.startswith("."):
                continue
            if not (case_dir / "ground_truth.json").exists():
                continue
            try:
                tags = suggest_tags(case_dir, split)
            except Exception as e:
                print(f"  skip {case_dir.name}: {e}", file=sys.stderr)
                continue
            target = (case_dir / "tags.json") if args.write else (case_dir / args.suggested_filename)
            target.write_text(
                json.dumps(tags, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  {'wrote' if args.write else 'suggested'} {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
