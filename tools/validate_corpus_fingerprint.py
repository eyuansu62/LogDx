#!/usr/bin/env python3
"""Verify the cases/ tree matches the committed corpus fingerprint.

A fingerprint is a deterministic sha256 over every per-case file
in `cases/<split>/<case_id>/{raw.log, case.json, ground_truth.json,
tags.json, privacy_audit.json}` for every case. If this hash changes,
the HuggingFace mirror at `eyuansu71/logdx-ci` will drift from the
local repo until someone re-runs `huggingface/upload.sh`.

This gate fails loudly when:
- cases/ tree has been modified but `huggingface/corpus_fingerprint.json`
  is stale
- the fingerprint file is missing

How to fix:
1. Run `bash huggingface/upload.sh` to push the new cases/ tree to HF.
2. Run `python3 tools/validate_corpus_fingerprint.py --update` to refresh
   the fingerprint file. Commit both changes (your cases/ change AND
   the fingerprint update) in the same PR.

The fingerprint file itself doesn't go to HF — it's a repo-side invariant
that ties the repo's cases/ snapshot to the corresponding HF snapshot.
"""
import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "cases"
FINGERPRINT_FILE = ROOT / "huggingface" / "corpus_fingerprint.json"

CASE_FILES = ("raw.log", "case.json", "ground_truth.json",
              "tags.json", "privacy_audit.json")


def hash_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def compute_corpus_fingerprint() -> dict:
    """Return {case_id: {file: sha256, ...}, ...} for every case under cases/."""
    out = {}
    for case_json in sorted(CASES_DIR.glob("**/case.json")):
        case_dir = case_json.parent
        split = case_dir.parent.relative_to(CASES_DIR).as_posix()
        case_id = case_dir.name
        key = f"{split}/{case_id}"
        per_case = {}
        for fname in CASE_FILES:
            fp = case_dir / fname
            if fp.exists():
                per_case[fname] = hash_file(fp)
        out[key] = per_case
    # Top-level digest = sha256 of the canonical-JSON dump
    canonical = json.dumps(out, sort_keys=True, separators=(",", ":"))
    return {
        "version": 1,
        "case_count": len(out),
        "top_level_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "per_case": out,
    }


def load_committed() -> dict | None:
    if not FINGERPRINT_FILE.exists():
        return None
    return json.loads(FINGERPRINT_FILE.read_text())


def write_fingerprint(fp: dict) -> None:
    FINGERPRINT_FILE.write_text(json.dumps(fp, indent=2, sort_keys=True) + "\n")


def validate() -> int:
    current = compute_corpus_fingerprint()
    committed = load_committed()
    if committed is None:
        print(
            "FAIL: huggingface/corpus_fingerprint.json is missing.\n"
            "Run `python3 tools/validate_corpus_fingerprint.py --update` "
            "to generate it, then commit.",
            file=sys.stderr,
        )
        return 1
    if current["top_level_sha256"] != committed["top_level_sha256"]:
        print(
            f"FAIL: cases/ tree fingerprint drifted.\n"
            f"  committed top_level_sha256: {committed['top_level_sha256']}\n"
            f"  actual    top_level_sha256: {current['top_level_sha256']}\n"
            f"  committed case_count: {committed['case_count']}\n"
            f"  actual    case_count: {current['case_count']}\n"
            f"\n"
            f"This means cases/ has been modified but huggingface/corpus_"
            f"fingerprint.json hasn't been refreshed. The HuggingFace mirror\n"
            f"at https://huggingface.co/datasets/eyuansu71/logdx-ci will be\n"
            f"out of sync with this repo's cases/ until someone re-runs\n"
            f"`bash huggingface/upload.sh`.\n"
            f"\n"
            f"To fix:\n"
            f"  1. Run `bash huggingface/upload.sh` (push to HF)\n"
            f"  2. Run `python3 tools/validate_corpus_fingerprint.py --update`\n"
            f"  3. Commit the updated corpus_fingerprint.json in the same PR\n"
            f"     as the cases/ change.",
            file=sys.stderr,
        )
        # Print which cases changed
        cur_per = current["per_case"]
        com_per = committed["per_case"]
        diff_cases = sorted(set(cur_per) ^ set(com_per))
        if diff_cases:
            print(f"\n  Cases added/removed: {diff_cases}", file=sys.stderr)
        else:
            changed = []
            for k in sorted(cur_per):
                if cur_per[k] != com_per.get(k):
                    changed.append(k)
            if changed:
                print(f"\n  Cases with file-level drift: {changed[:10]}"
                      f"{'…' if len(changed) > 10 else ''}", file=sys.stderr)
        return 1
    print(
        f"OK: corpus fingerprint matches ({committed['case_count']} cases, "
        f"top_level_sha256={committed['top_level_sha256'][:16]}…)"
    )
    return 0


def update() -> int:
    fp = compute_corpus_fingerprint()
    write_fingerprint(fp)
    print(
        f"Wrote {FINGERPRINT_FILE.relative_to(ROOT)} ({fp['case_count']} cases, "
        f"top_level_sha256={fp['top_level_sha256'][:16]}…)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--update", action="store_true",
        help="Recompute and overwrite huggingface/corpus_fingerprint.json. "
             "Use this after a corpus change once huggingface/upload.sh has "
             "pushed the new cases/ snapshot to HF.",
    )
    args = ap.parse_args()
    return update() if args.update else validate()


if __name__ == "__main__":
    sys.exit(main())
