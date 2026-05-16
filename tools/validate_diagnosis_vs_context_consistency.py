#!/usr/bin/env python3
"""Release check: every committed
`results/<split>/diagnoses/<diagnoser>/<method>.jsonl` must have a
diagnosis row for every case in the source context manifest
`results/<split>/<method>.jsonl`, OR the missing case must be
listed in `configs/historical_provider_error_exclusions.json`.

Per Codex 2026-06-14 F1 [high]: the 2026-06-09 + 2026-06-10 cleanup
tools removed 20 non-allowlisted provider_error rows from diagnosis
manifests, which silently shrank the eval denominator (failures were
dropped instead of counted as zero-score). This release gate ensures
that going forward, any case missing from a diagnosis manifest must
be explicitly documented in the exclusion file with a justification.

Works recursively across both flat (`results/<split>/`) and nested
(`results/v2/<split>/`) layouts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def manifest_case_ids(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = row.get("case_id")
            if cid:
                out.add(cid)
    return out


def load_exclusions(path: Path) -> set[tuple[str, str, str, str]]:
    """Return a set of (split, diagnoser, method, case_id) tuples."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    out: set[tuple[str, str, str, str]] = set()
    for entry in data.get("exclusions") or []:
        out.add((
            entry["split"], entry["diagnoser"],
            entry["method"], entry["case_id"],
        ))
    return out


def split_of_diagnosis_root(diag_root: Path, results_dir: Path) -> str:
    """`results/dev/diagnoses` → "dev"; `results/v2/holdout/diagnoses` →
    "v2/holdout"."""
    return str(diag_root.parent.relative_to(results_dir))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=REPO / "results")
    ap.add_argument(
        "--exclusions",
        type=Path,
        default=REPO / "configs" / "historical_provider_error_exclusions.json",
    )
    ap.add_argument("--diagnoser-prefix", default="real-debugger-")
    args = ap.parse_args()

    exclusions = load_exclusions(args.exclusions)

    failures: list[str] = []
    diagnoses_roots = sorted(
        p for p in args.results_dir.rglob("diagnoses") if p.is_dir()
    )
    for diag_root in diagnoses_roots:
        split = split_of_diagnosis_root(diag_root, args.results_dir)
        split_dir = args.results_dir / split
        for diag_dir in sorted(diag_root.iterdir()):
            if not diag_dir.is_dir():
                continue
            name = diag_dir.name
            if not name.startswith(args.diagnoser_prefix):
                continue
            for diag_manifest in sorted(diag_dir.glob("*.jsonl")):
                method = diag_manifest.stem
                ctx_manifest = split_dir / f"{method}.jsonl"
                if not ctx_manifest.exists():
                    # No source context manifest — skip (this can
                    # happen for synthetic method names; not the
                    # invariant we're enforcing).
                    continue
                ctx_cases = manifest_case_ids(ctx_manifest)
                diag_cases = manifest_case_ids(diag_manifest)
                missing = ctx_cases - diag_cases
                for case in sorted(missing):
                    if (split, name, method, case) in exclusions:
                        continue
                    failures.append(
                        f"{diag_manifest.relative_to(args.results_dir)}: "
                        f"missing case {case!r} present in source "
                        f"context manifest {ctx_manifest.relative_to(args.results_dir)} "
                        f"(not in exclusion list)"
                    )
                # Also flag extras (diag has cases not in context)
                extras = diag_cases - ctx_cases
                for case in sorted(extras):
                    failures.append(
                        f"{diag_manifest.relative_to(args.results_dir)}: "
                        f"extra case {case!r} NOT in source context "
                        f"manifest {ctx_manifest.relative_to(args.results_dir)}"
                    )

    if failures:
        print(
            "FAIL: diagnosis-vs-context consistency violations:",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(
            f"\nTotal violations: {len(failures)}. Fix options:\n"
            f"  - Re-run the diagnoser on the missing cases so they\n"
            f"    appear in the manifest (preferred — failures get\n"
            f"    counted in the denominator).\n"
            f"  - OR add the (split, diagnoser, method, case_id) tuple\n"
            f"    to `configs/historical_provider_error_exclusions.json`\n"
            f"    with a justification.",
            file=sys.stderr,
        )
        return 1

    print(
        "OK: every diagnosis manifest's case set matches its source "
        f"context manifest in {args.results_dir} (or is explicitly "
        f"excluded)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
