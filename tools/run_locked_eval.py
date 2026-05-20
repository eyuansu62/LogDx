"""
Run locked-parameter baselines + signal-recall evaluation over a split.

This thin wrapper reads `protocols/<protocol>.lock.json` and invokes the
existing method runners with the baseline parameters declared in the
lock, not with ad-hoc CLI defaults. This is how M8 guarantees that
holdout evaluations use the same knobs as dev.

Usage:
    python tools/run_locked_eval.py \\
        --protocol protocols/legacy/cilogbench-v1.lock.json \\
        --split dev --methods raw,tail,grep

    python tools/run_locked_eval.py \\
        --protocol protocols/legacy/cilogbench-v1.lock.json \\
        --split holdout \\
        --methods raw,tail,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock

If RTK is not installed, rtk-* methods are recorded as
`skipped_missing_external_tool` and the overall run still succeeds.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(argv: list[str], *, label: str, ok_rc: set[int] | None = None) -> int:
    print(f"\n$ {' '.join(argv)}")
    res = subprocess.run(argv, cwd=ROOT)
    if res.returncode in (ok_rc or {0}):
        return 0
    return res.returncode


def rtk_available() -> bool:
    return shutil.which("rtk") is not None


def baseline_to_argv(name: str, params: dict, split: str) -> list[str]:
    if name in ("raw", "tail-200", "tail", "grep"):
        method = "raw" if name == "raw" else ("tail" if name.startswith("tail") else "grep")
        argv = [
            sys.executable, "tools/run_baseline.py",
            "--method", method, "--split", split,
        ]
        if method == "tail":
            argv += ["--tail-lines", str(params.get("tail_lines", 200))]
        if method == "grep":
            argv += [
                "--before", str(params.get("before", 3)),
                "--after",  str(params.get("after", 8)),
                "--regex",  params.get(
                    "regex",
                    "error|failed|failure|traceback|exception|assert|panic|exit code|##\\[error\\]",
                ),
            ]
        return argv
    if name.startswith("rtk-"):
        return [
            sys.executable, "tools/run_rtk_baseline.py",
            "--method", name, "--split", split,
        ]
    if name == "llm-summary-v1-mock":
        return [
            sys.executable, "tools/run_llm_summary_baseline.py",
            "--split", split, "--provider", "mock",
            "--method", "llm-summary-v1-mock",
        ]
    raise ValueError(f"unknown baseline method: {name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run locked baselines over a split.")
    ap.add_argument("--protocol", required=True, type=Path)
    ap.add_argument("--split", required=True,
                    help="Split to run under the lock (dev, holdout, stress, ...).")
    ap.add_argument("--methods", required=True,
                    help="Comma-separated method names. Must be listed "
                         "under `baselines` in the protocol lock.")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    # Validate lock first so we never run against a drifted protocol.
    rc = run(
        [sys.executable, "tools/validate_protocol_lock.py",
         "--protocol", str(args.protocol)],
        label="validate_protocol_lock",
    )
    if rc != 0:
        print(f"\nERROR: protocol lock validation failed; refusing to run "
              f"locked eval.", file=sys.stderr)
        return rc

    lock = json.loads(args.protocol.read_text(encoding="utf-8"))
    baselines = lock.get("baselines") or {}
    requested = [m.strip() for m in args.methods.split(",") if m.strip()]

    skipped: list[tuple[str, str]] = []
    run_methods: list[str] = []
    for name in requested:
        if name not in baselines:
            print(f"WARNING: method {name} is not declared in the protocol "
                  f"lock; skipping.", file=sys.stderr)
            skipped.append((name, "not_in_protocol_lock"))
            continue
        params = baselines[name]
        if not params.get("enabled", True):
            skipped.append((name, "disabled_in_protocol"))
            continue
        if name.startswith("rtk-") and not rtk_available():
            print(f"  skip {name}: rtk binary not on PATH "
                  f"→ skipped_missing_external_tool", file=sys.stderr)
            skipped.append((name, "skipped_missing_external_tool"))
            continue
        step = baseline_to_argv(name, params, args.split)
        rc = run(step, label=f"run {name}")
        if rc != 0:
            print(f"\nERROR: baseline {name} exited {rc}", file=sys.stderr)
            return rc
        run_methods.append(name)

    # Signal-recall evaluation
    for name in run_methods:
        # Normalize rtk-* method name differences — the method name passed to
        # evaluate_signal_recall matches the manifest stem, which already
        # equals `name` for every baseline we handle.
        method_for_eval = "tail" if name == "tail-200" else name
        rc = run(
            [sys.executable, "tools/evaluate_signal_recall.py",
             "--split", args.split, "--method", method_for_eval,
             "--results-dir", str(args.results_dir)],
            label=f"evaluate_signal_recall {method_for_eval}",
        )
        if rc != 0:
            print(f"\nERROR: signal eval for {method_for_eval} exited {rc}",
                  file=sys.stderr)
            return rc

    # Cross-method signal-recall report
    eval_methods = [("tail" if m == "tail-200" else m) for m in run_methods]
    rc = run(
        [sys.executable, "tools/render_report.py",
         "--split", args.split,
         "--methods", *eval_methods,
         "--results-dir", str(args.results_dir),
         "--reports-dir", str(args.reports_dir)],
        label="render_report",
    )
    if rc != 0:
        return rc

    summary = {
        "protocol_id": lock.get("protocol_id"),
        "split": args.split,
        "methods_run": run_methods,
        "methods_skipped": [{"method": n, "reason": r} for n, r in skipped],
    }
    summary_path = args.results_dir / args.split / f"locked_eval_{lock.get('protocol_id','unknown')}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"\nLocked eval summary → {summary_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
