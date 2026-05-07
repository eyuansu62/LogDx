"""
Check for contamination between dev and holdout splits.

Checks performed:
    1. Exact raw.log SHA-256 duplicates between splits  — FAIL.
    2. Case-ID collisions — FAIL.
    3. Ground-truth SHA-256 duplicates — FAIL.
    4. Normalized (timestamp-stripped, whitespace-collapsed) raw-log
       SHA-256 duplicates — FAIL (same content different timestamps).
    5. Line-level Jaccard similarity ≥ 0.80 — flagged in report,
       non-fatal.
    6. Holdout case_id must not already appear under any
       results/dev/*.jsonl manifest (would mean we already ran methods
       on a case that was supposed to be held out) — FAIL.

Outputs:
    results/holdout_contamination_check.json
    reports/holdout_contamination_check.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GHA_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s?")
WS_RUN_RE = re.compile(r"[ \t]+")

JACCARD_THRESHOLD = 0.80


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_raw(text: str) -> str:
    lines = [
        WS_RUN_RE.sub(" ", GHA_TIMESTAMP_RE.sub("", ln)).strip()
        for ln in text.splitlines()
    ]
    return "\n".join(ln for ln in lines if ln)


def line_set(text: str) -> set[str]:
    return set(
        WS_RUN_RE.sub(" ", GHA_TIMESTAMP_RE.sub("", ln)).strip()
        for ln in text.splitlines()
        if ln.strip()
    )


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_cases(split: str) -> list[dict]:
    split_dir = ROOT / "cases" / split
    out: list[dict] = []
    if not split_dir.is_dir():
        return out
    for case_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        if case_dir.name.startswith("."):
            continue
        raw = (case_dir / "raw.log").read_bytes()
        gt = (case_dir / "ground_truth.json").read_bytes()
        out.append({
            "split": split,
            "case_id": case_dir.name,
            "raw_sha": sha256_bytes(raw),
            "norm_sha": sha256_bytes(normalize_raw(raw.decode("utf-8", errors="replace")).encode("utf-8")),
            "gt_sha": sha256_bytes(gt),
            "line_set": line_set(raw.decode("utf-8", errors="replace")),
        })
    return out


def dev_results_uses_holdout_case_id(holdout_ids: set[str]) -> list[str]:
    """If a holdout case_id already shows up in results/dev/*.jsonl it means
    a method was run on it before it was held out — which is contamination."""
    leaks: list[str] = []
    dev_results = ROOT / "results" / "dev"
    if not dev_results.is_dir():
        return leaks
    for p in dev_results.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("case_id") in holdout_ids:
                leaks.append(f"{p.relative_to(ROOT)}:{row['case_id']}")
    return leaks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check dev/holdout contamination.")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    dev = load_cases("dev")
    holdout = load_cases("holdout")

    failures: list[dict] = []
    warnings: list[dict] = []

    # Exact raw-log duplicate
    dev_raw_shas = {c["raw_sha"]: c["case_id"] for c in dev}
    for c in holdout:
        if c["raw_sha"] in dev_raw_shas:
            failures.append({
                "kind": "exact_raw_duplicate",
                "holdout_case": c["case_id"],
                "dev_case": dev_raw_shas[c["raw_sha"]],
                "raw_sha": c["raw_sha"],
            })

    # Case-ID collision
    dev_ids = {c["case_id"] for c in dev}
    for c in holdout:
        if c["case_id"] in dev_ids:
            failures.append({
                "kind": "case_id_collision",
                "case_id": c["case_id"],
            })

    # Ground-truth duplicate
    dev_gt = {c["gt_sha"]: c["case_id"] for c in dev}
    for c in holdout:
        if c["gt_sha"] in dev_gt:
            failures.append({
                "kind": "ground_truth_duplicate",
                "holdout_case": c["case_id"],
                "dev_case": dev_gt[c["gt_sha"]],
            })

    # Normalized raw duplicate
    dev_norm = {c["norm_sha"]: c["case_id"] for c in dev}
    for c in holdout:
        if c["norm_sha"] in dev_norm and c["raw_sha"] not in dev_raw_shas:
            failures.append({
                "kind": "normalized_raw_duplicate",
                "holdout_case": c["case_id"],
                "dev_case": dev_norm[c["norm_sha"]],
            })

    # Jaccard similarity flag
    for hc in holdout:
        for dc in dev:
            sim = jaccard(hc["line_set"], dc["line_set"])
            if sim >= JACCARD_THRESHOLD and hc["raw_sha"] != dc["raw_sha"]:
                warnings.append({
                    "kind": "near_duplicate",
                    "holdout_case": hc["case_id"],
                    "dev_case": dc["case_id"],
                    "line_jaccard": round(sim, 4),
                })

    # Leakage into results/dev/ manifests
    holdout_ids = {c["case_id"] for c in holdout}
    results_leaks = dev_results_uses_holdout_case_id(holdout_ids)
    for leak in results_leaks:
        failures.append({
            "kind": "holdout_case_id_in_dev_results",
            "detail": leak,
        })

    summary = {
        "dev_case_count": len(dev),
        "holdout_case_count": len(holdout),
        "jaccard_threshold": JACCARD_THRESHOLD,
        "failures": failures,
        "warnings": warnings,
        "disclaimer": (
            "This check is heuristic. Absence of failures does not prove the "
            "holdout was never peeked at; warnings are diagnostic flags only."
        ),
    }
    out_json = args.results_dir / "holdout_contamination_check.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    md: list[str] = []
    md.append("# Holdout contamination check")
    md.append("")
    md.append(f"- Dev cases: **{len(dev)}**")
    md.append(f"- Holdout cases: **{len(holdout)}**")
    md.append(f"- Jaccard near-duplicate threshold: **{JACCARD_THRESHOLD}**")
    md.append(f"- Hard failures: **{len(failures)}**")
    md.append(f"- Soft warnings: **{len(warnings)}**")
    md.append("")
    if failures:
        md.append("## Failures (fatal)")
        md.append("")
        for f in failures:
            md.append(f"- `{f['kind']}` — {json.dumps({k: v for k, v in f.items() if k != 'kind'}, ensure_ascii=False)}")
        md.append("")
    if warnings:
        md.append("## Warnings (diagnostic flags)")
        md.append("")
        for w in warnings:
            md.append(f"- `{w['kind']}` — holdout `{w['holdout_case']}` "
                      f"↔ dev `{w['dev_case']}` (line_jaccard={w['line_jaccard']})")
        md.append("")
    if not failures and not warnings:
        md.append("No contamination patterns detected.")
        md.append("")
    md.append("## Disclaimer")
    md.append("")
    md.append(
        "This scanner is heuristic. It detects the specific duplication "
        "patterns listed above; it cannot prove that holdout was never "
        "used during method development. Protocol integrity ultimately "
        "depends on the holdout-policy doc being followed."
    )
    out_md = args.reports_dir / "holdout_contamination_check.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    print(f"  failures={len(failures)} warnings={len(warnings)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
