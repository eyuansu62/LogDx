#!/usr/bin/env python3
"""Release check: assert that every committed `eval_diagnosis_*.json`
file's per-method case-ID set exactly matches its corresponding
diagnosis manifest's case-ID set.

Per Codex 2026-06-11 F1 [high]: cleanup tools that remove rows from
`results/<split>/diagnoses/<diagnoser>/<method>.jsonl` (e.g. the
2026-06-09 and 2026-06-10 provider_error cleanups) must be paired
with eval-file regeneration. Otherwise the eval file scores rows
that no longer exist in the manifest; downstream reports publish
metrics that cannot be reproduced from shipped manifests.

Exits 0 on consistent state. Exits 1 with a per-method diff
otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def manifest_case_ids(manifest: Path) -> set[str]:
    out: set[str] = set()
    if not manifest.exists():
        return out
    with manifest.open(encoding="utf-8") as f:
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


def eval_case_ids(eval_path: Path) -> dict[str, set[str]]:
    """Return {context_method: {case_id...}}."""
    out: dict[str, set[str]] = {}
    if not eval_path.exists():
        return out
    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return out
    methods = data.get("methods") or []
    for m in methods:
        ctx_method = m.get("context_method")
        if not ctx_method:
            continue
        cases = m.get("cases") or []
        out[ctx_method] = {c.get("case_id") for c in cases if c.get("case_id")}
    return out


def _load_exclusion_set(path: Path) -> set[tuple[str, str, str, str]]:
    """Per Codex 2026-06-15 F1 [high]: synthesized excluded rows
    appear in eval files (as zero-score abstentions injected by
    evaluate_diagnosis.py) but NOT in diagnosis manifests. The
    consistency check needs to know about them so the synthesized
    rows don't get flagged as "in eval but not manifest"."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {
        (e["split"], e["diagnoser"], e["method"], e["case_id"])
        for e in (data.get("exclusions") or [])
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=REPO / "results")
    ap.add_argument(
        "--exclusions",
        type=Path,
        default=REPO / "configs" / "historical_provider_error_exclusions.json",
        help="Historical-exclusion manifest; synthesized eval rows for these "
             "(split, diagnoser, method, case_id) tuples are not required to "
             "appear in diagnosis manifests.",
    )
    args = ap.parse_args()
    exclusion_set = _load_exclusion_set(args.exclusions)

    failures: list[str] = []
    # Walk recursively for every eval_diagnosis_*.json.
    for eval_path in sorted(args.results_dir.rglob("eval_diagnosis_*.json")):
        # Locate the diagnosis dir alongside the eval file:
        # results/<split>/eval_diagnosis_<diagnoser>.json
        # results/<split>/diagnoses/<diagnoser>/<method>.jsonl
        split_dir = eval_path.parent
        diagnoser = eval_path.stem.removeprefix("eval_diagnosis_")
        diag_root = split_dir / "diagnoses" / diagnoser
        if not diag_root.exists():
            # eval file with no corresponding diagnoses dir → orphaned
            failures.append(
                f"{eval_path.relative_to(args.results_dir)}: orphaned "
                f"(no {diag_root.relative_to(args.results_dir)})"
            )
            continue
        # The eval path is `results/<split>/eval_diagnosis_<diag>.json`;
        # extract <split> for exclusion-set lookups.
        split_label = str(split_dir.relative_to(args.results_dir))
        eval_methods = eval_case_ids(eval_path)
        # Per Codex 2026-06-12 F2 [medium]: also assert the SET of
        # methods matches between eval file and manifest directory.
        # Pre-fix, the check only iterated over methods present in the
        # eval file; a manifest method missing from a stale eval file
        # was silently ignored. Now we compare both directions.
        manifest_method_set = {
            m.stem for m in diag_root.glob("*.jsonl")
        }
        eval_method_set = set(eval_methods.keys())
        only_in_eval = eval_method_set - manifest_method_set
        only_in_manifest = manifest_method_set - eval_method_set
        for m in sorted(only_in_eval):
            failures.append(
                f"{eval_path.relative_to(args.results_dir)} "
                f"method={m!r}: in eval but no manifest "
                f"{diag_root.relative_to(args.results_dir)}/{m}.jsonl"
            )
        for m in sorted(only_in_manifest):
            failures.append(
                f"{eval_path.relative_to(args.results_dir)} "
                f"method={m!r}: manifest exists but eval omits this method"
            )
        for method, eval_set in eval_methods.items():
            if method not in manifest_method_set:
                # Already reported above; skip per-case detail.
                continue
            manifest = diag_root / f"{method}.jsonl"
            manifest_set = manifest_case_ids(manifest)
            if eval_set != manifest_set:
                missing_in_manifest_raw = eval_set - manifest_set
                # Per Codex 2026-06-15 F1 [high]: filter out cases
                # that ARE listed in the historical exclusion
                # manifest — those are intentionally injected by
                # evaluate_diagnosis.py as zero-score abstentions
                # and don't have a corresponding manifest row.
                missing_in_manifest = {
                    cid for cid in missing_in_manifest_raw
                    if (split_label, diagnoser, method, cid)
                       not in exclusion_set
                }
                missing_in_eval = manifest_set - eval_set
                if not missing_in_manifest and not missing_in_eval:
                    continue
                detail = []
                if missing_in_manifest:
                    detail.append(
                        f"in eval but not manifest (and not in exclusions): "
                        f"{sorted(missing_in_manifest)}"
                    )
                if missing_in_eval:
                    detail.append(
                        f"in manifest but not eval: "
                        f"{sorted(missing_in_eval)}"
                    )
                failures.append(
                    f"{eval_path.relative_to(args.results_dir)} "
                    f"method={method!r}: {'; '.join(detail)}"
                )

    if failures:
        print(
            "FAIL: eval-vs-manifest case-ID mismatches:", file=sys.stderr
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(
            f"\nTotal mismatches: {len(failures)}. Regenerate the affected "
            f"eval files with `python3 tools/evaluate_diagnosis.py "
            f"--split <split> --diagnoser <diagnoser>` after any manifest "
            f"row removal/cleanup.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: every eval_diagnosis_*.json case-ID set matches its "
        f"corresponding manifest in {args.results_dir}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
