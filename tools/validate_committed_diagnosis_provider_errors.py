#!/usr/bin/env python3
"""Release check: scan committed real-debugger-* manifests under
`results/<split>/diagnoses/` and fail if any row carries a
`metadata.provider_error` whose prefix is NOT in the diagnoser
config's `provider_policy.non_fatal_provider_error_prefixes`
allowlist.

Per Codex 2026-06-09 F1 [high]: prior to this check, the 2026-06-08
F1 fix ensured fresh-run provider_error rows fail the runner, but
historical artifacts committed under `real-debugger-*` could still
ship with non-allowlisted error classes (e.g. `post_api_error:
JSONDecodeError ...`). That meant a future `evaluate_diagnosis` /
`render_report` invocation would treat them as model abstentions
rather than experiment failures.

This script is a release gate, not a fixer. Run it in CI / pre-commit
hooks. Exits 0 when every real-debugger row is either (a) a success
row with no provider_error, OR (b) a provider_error row whose prefix
matches the config's allowlist. Exits 1 with a per-row report
otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import run_diagnosis as rd  # noqa: E402


def scan_manifest(
    manifest: Path, allowlist: list[str]
) -> list[tuple[str, str]]:
    """Return list of (case_id, provider_error) for non-allowlisted rows."""
    bad: list[tuple[str, str]] = []
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
            if not pe:
                continue
            matched = any(
                isinstance(p, str) and pe.startswith(p) for p in allowlist
            )
            if not matched:
                bad.append((row.get("case_id", "?"), pe))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results-dir", type=Path, default=REPO / "results",
        help="Root of committed results to scan."
    )
    ap.add_argument(
        "--diagnoser-prefix",
        default="real-debugger-,real-agent-",
        help="Comma-separated list of diagnoser_name prefixes to check. "
             "Defaults to both real-debugger-* (single-shot) and "
             "real-agent-* (multi-turn agent-loop variant added in v1.1)."
    )
    args = ap.parse_args()
    allowed_prefixes = tuple(
        p.strip() for p in args.diagnoser_prefix.split(",") if p.strip()
    )

    findings: list[tuple[str, str, str]] = []
    # Per Codex 2026-06-10 F1 [high]: walk recursively for ALL
    # `diagnoses/` directories under results-root, not just direct
    # children of a single-segment split. The v2 protocol uses a
    # nested layout (`results/v2/<split>/diagnoses/`) which the
    # 2026-06-09 single-level scanner skipped entirely. 12
    # non-allowlisted RuntimeError rows were hiding under
    # `results/v2/<split>/diagnoses/real-debugger-v1/` because of
    # this gap.
    diagnoses_roots = sorted(p for p in args.results_dir.rglob("diagnoses") if p.is_dir())
    for diag_root in diagnoses_roots:
        rel_root = diag_root.relative_to(args.results_dir)
        for diag_dir in sorted(diag_root.iterdir()):
            if not diag_dir.is_dir():
                continue
            name = diag_dir.name
            if not name.startswith(allowed_prefixes):
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
                for case_id, pe in scan_manifest(manifest, allowlist):
                    findings.append((
                        str(rel_root.parent / name),
                        manifest.name,
                        f"{case_id} :: {pe[:120]}",
                    ))

    if findings:
        print(
            "FAIL: committed real-debugger artifacts contain "
            "non-allowlisted provider_error rows:",
            file=sys.stderr,
        )
        for rel_diag, manifest, detail in findings:
            print(
                f"  results/{rel_diag}/{manifest} :: {detail}",
                file=sys.stderr,
            )
        print(
            f"\nTotal violations: {len(findings)}. Fix options:\n"
            f"  - regenerate the affected results under a fixed runner,\n"
            f"  - or remove the offending rows from the manifest +\n"
            f"    per-case JSON if the failure is unrecoverable.\n"
            f"  - Or, only if the failure class is documented as a\n"
            f"    graceful refusal, add its prefix to "
            f"`provider_policy.non_fatal_provider_error_prefixes` in\n"
            f"    the diagnoser config.",
            file=sys.stderr,
        )
        return 1

    print("OK: no non-allowlisted provider_error rows under "
          f"{args.diagnoser_prefix} manifests in {args.results_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
