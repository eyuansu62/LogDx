"""
Validate that a protocol lock still matches current repository state.

Recomputes SHA-256 for every path listed under `schemas`, `prompts`,
`evaluators` in the lock, and confirms split manifests still describe
cases that exist. Fails non-zero on the first mismatch with a
diff-style message.

Usage:
    python tools/validate_protocol_lock.py --protocol protocols/cilogbench-v1.lock.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_hash_block(label: str, block: dict[str, dict]) -> list[str]:
    errs: list[str] = []
    for key, entry in block.items():
        path = ROOT / entry["path"]
        if not path.exists():
            errs.append(f"MISSING: {entry['path']} (lock key: {label}.{key})")
            continue
        actual = sha256_path(path)
        if actual != entry["sha256"]:
            errs.append(
                f"CHANGED: {entry['path']}\n"
                f"  expected sha256: {entry['sha256']}\n"
                f"  actual sha256:   {actual}\n"
                f"  lock key: {label}.{key}"
            )
    return errs


def check_splits(splits_block: dict) -> list[str]:
    errs: list[str] = []
    for split_name, spec in splits_block.items():
        manifest_path = ROOT / spec["manifest_path"]
        if not manifest_path.exists():
            errs.append(f"MISSING split manifest: {spec['manifest_path']}")
            continue
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if m.get("case_count") != spec.get("case_count"):
            errs.append(
                f"CHANGED split {split_name} case_count: "
                f"expected {spec.get('case_count')}, got {m.get('case_count')}"
            )
        # Verify each case's files exist + hashes match the manifest.
        for case in m.get("cases", []):
            cd = ROOT / "cases" / split_name / case["case_id"]
            for kind, fname, key in [
                ("raw.log", "raw.log", "raw_log_sha256"),
                ("case.json", "case.json", "case_json_sha256"),
                ("ground_truth.json", "ground_truth.json", "ground_truth_sha256"),
            ]:
                fpath = cd / fname
                if not fpath.exists():
                    errs.append(f"MISSING {fname} for case {case['case_id']}")
                    continue
                actual = sha256_path(fpath)
                if actual != case[key]:
                    errs.append(
                        f"CHANGED case {case['case_id']} / {fname}:\n"
                        f"  expected {case[key]}\n"
                        f"  actual   {actual}"
                    )
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a CILogBench protocol lock.")
    ap.add_argument("--protocol", required=True, type=Path)
    args = ap.parse_args(argv)

    if not args.protocol.exists():
        print(f"ERROR: lock file not found: {args.protocol}", file=sys.stderr)
        return 1
    lock = json.loads(args.protocol.read_text(encoding="utf-8"))

    errs: list[str] = []
    errs += check_hash_block("schemas",    lock.get("schemas") or {})
    errs += check_hash_block("prompts",    lock.get("prompts") or {})
    errs += check_hash_block("evaluators", lock.get("evaluators") or {})
    errs += check_splits(lock.get("splits") or {})

    if errs:
        print(f"Protocol lock FAILED ({len(errs)} issue(s)):", file=sys.stderr)
        for e in errs:
            print(e, file=sys.stderr)
            print("", file=sys.stderr)
        return 1

    total = (
        len(lock.get("schemas") or {})
        + len(lock.get("prompts") or {})
        + len(lock.get("evaluators") or {})
    )
    split_cases = sum(
        int(s.get("case_count", 0)) for s in (lock.get("splits") or {}).values()
    )
    print(f"Protocol lock OK: {lock.get('protocol_id')}")
    print(f"  {total} hashes match ({len(lock.get('schemas') or {})} schemas, "
          f"{len(lock.get('prompts') or {})} prompts, "
          f"{len(lock.get('evaluators') or {})} evaluators)")
    print(f"  {split_cases} cases across {len(lock.get('splits') or {})} split(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
