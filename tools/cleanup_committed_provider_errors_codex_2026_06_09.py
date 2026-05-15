#!/usr/bin/env python3
"""One-shot cleanup: Codex 2026-06-09 F1 [high]. Removes from committed
`results/<split>/diagnoses/real-debugger-*/` manifests + per-case JSONs
any row whose `metadata.provider_error` prefix is NOT in the diagnoser
config's `provider_policy.non_fatal_provider_error_prefixes` allowlist.

These rows correspond to transient model/CLI failures during the
2026-04..05 canonical sweeps:
- v1: claude CLI `RuntimeError: ... exited 1` (transient subprocess)
- v2: `JSONDecodeError: Invalid \\escape` (model output parse)
- v3: `post_api_error: JSONDecodeError ...` (OpenAI response parse)

Before the 2026-06-08 F1 fail-closed fix landed, those rows were
written under the canonical diagnoser name as "unknown" diagnoses
with `metadata.provider_error` set — downstream evaluation treated
them like abstentions. Post-fix, a fresh run would have exited
non-zero, but historical artifacts predate the fix and stayed in
the tree. This script removes them so the release check
(`tools/validate_committed_diagnosis_provider_errors.py`) passes.

Affected cases are reported in the §3i disclosure block. The
removed cases will appear as missing from manifests on next
evaluate_diagnosis pass — that's intentional: they did NOT produce
usable diagnoses and shouldn't be treated as model abstentions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import run_diagnosis as rd  # noqa: E402


def clean_manifest(
    manifest: Path, allowlist: list[str], dry_run: bool
) -> tuple[int, list[str]]:
    kept: list[dict] = []
    removed_cases: list[str] = []
    with manifest.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            pe = (row.get("metadata") or {}).get("provider_error")
            if pe and not any(
                isinstance(p, str) and pe.startswith(p) for p in allowlist
            ):
                removed_cases.append(row.get("case_id", "?"))
                continue
            kept.append(row)
    if dry_run:
        return len(removed_cases), removed_cases
    with manifest.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(removed_cases), removed_cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=REPO / "results")
    ap.add_argument("--diagnoser-prefix", default="real-debugger-")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_removed = 0
    affected: list[str] = []
    for split_dir in sorted(args.results_dir.iterdir()):
        if not split_dir.is_dir():
            continue
        diag_root = split_dir / "diagnoses"
        if not diag_root.exists():
            continue
        for diag_dir in sorted(diag_root.iterdir()):
            if not diag_dir.is_dir():
                continue
            name = diag_dir.name
            if not name.startswith(args.diagnoser_prefix):
                continue
            try:
                config = rd.load_diagnoser_config(name)
            except rd.DiagnoserConfigError:
                config = None
            allowlist = (
                ((config or {}).get("provider_policy") or {})
                .get("non_fatal_provider_error_prefixes") or []
            )
            for manifest in sorted(diag_dir.glob("*.jsonl")):
                count, cases = clean_manifest(
                    manifest, allowlist, args.dry_run
                )
                if count:
                    print(
                        f"  {'WOULD remove' if args.dry_run else 'removed'} "
                        f"{count} row(s) from "
                        f"{manifest.relative_to(REPO)}: {cases}"
                    )
                    total_removed += count
                    method = manifest.stem
                    for case_id in cases:
                        affected.append(f"{name}/{method}/{case_id}")
                        per_case = diag_dir / method / f"{case_id}.json"
                        if per_case.exists():
                            if args.dry_run:
                                print(
                                    f"    WOULD also remove per-case "
                                    f"{per_case.relative_to(REPO)}"
                                )
                            else:
                                per_case.unlink()
                                print(
                                    f"    removed per-case "
                                    f"{per_case.relative_to(REPO)}"
                                )
    print(
        f"\n{'WOULD remove' if args.dry_run else 'Removed'} "
        f"{total_removed} row(s) across "
        f"{len(set(affected))} (diagnoser, method, case) tuple(s)."
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
