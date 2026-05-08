"""
Run an RTK context-provider baseline over a case split.

RTK is treated as an *external* baseline. This script shells out to a
pre-installed `rtk` binary (default: whichever is on $PATH). It never
auto-installs RTK and never modifies the user's agent/hook configuration.

Supported methods:

    rtk-read    ->  rtk read <raw.log>
    rtk-log     ->  rtk log  <raw.log>
    rtk-err-cat ->  rtk err cat <raw.log>

Usage:

    python tools/run_rtk_baseline.py --method rtk-log     --split dev
    python tools/run_rtk_baseline.py --method rtk-read    --split dev
    python tools/run_rtk_baseline.py --method rtk-err-cat --split dev

Optional:

    --rtk-bin /path/to/rtk
    --results-dir results
    --timeout-seconds 30
    --allow-missing            (skip cleanly if rtk isn't installed)
    --allow-nonzero            (don't fail when rtk returns non-zero)
    --case-id CASE_ID          (single-case debug run)

All three required methods set `line_mapping_available: false`. RTK
reshapes content (dedup grouping, binary-blob elision, ANSI strip,
format rewriting) in ways that do not preserve original raw line
numbers. The evaluator scores these methods via text-based preservation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "method_output.schema.json"

DEFAULT_TIMEOUT_S = 30

try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# method -> argv builder (given the raw.log path). Each entry returns the
# tail of argv after `rtk` itself. Keep this table flat and explicit so an
# auditor can see exactly which RTK invocation the manifest refers to.
def _argv_rtk_read(raw: Path)    -> list[str]: return ["read", str(raw)]
def _argv_rtk_log(raw: Path)     -> list[str]: return ["log", str(raw)]
def _argv_rtk_err_cat(raw: Path) -> list[str]: return ["err", "cat", str(raw)]

METHODS: dict[str, Callable[[Path], list[str]]] = {
    "rtk-read":    _argv_rtk_read,
    "rtk-log":     _argv_rtk_log,
    "rtk-err-cat": _argv_rtk_err_cat,
}


# ---------------------------------------------------------------------------
# RTK discovery
# ---------------------------------------------------------------------------


def resolve_rtk(rtk_bin: str | None) -> tuple[Path, str] | None:
    """Return (binary_path, version_string) or None if rtk is unavailable."""
    if rtk_bin:
        path = Path(rtk_bin)
        if not path.exists():
            return None
    else:
        which = shutil.which("rtk")
        if not which:
            return None
        path = Path(which)
    try:
        out = subprocess.run(
            [str(path), "--version"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    version = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""
    return path, version


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def validate_row(row: dict) -> None:
    """Structural sanity + optional full JSON Schema validation."""
    if row["mode"] != "context_provider":
        raise ValueError(f"[{row['case_id']}] mode must be context_provider")
    if row["input_line_count"] < row["output_line_count"]:
        # This is plausible for RTK (adds summary header lines), so relax
        # the strict M2 check to a warning rather than an error, but only
        # when line_mapping_available is False.
        if row.get("line_mapping_available", True):
            raise ValueError(
                f"[{row['case_id']}] output_line_count {row['output_line_count']} "
                f"exceeds input_line_count {row['input_line_count']} "
                f"(line_mapping_available=true)"
            )
    if not (0.0 <= row["reduction_ratio"] <= 1.0):
        raise ValueError(
            f"[{row['case_id']}] reduction_ratio out of [0,1]: {row['reduction_ratio']}"
        )
    for i, rng in enumerate(row.get("included_line_ranges", [])):
        if len(rng) != 2 or rng[0] < 1 or rng[1] < rng[0]:
            raise ValueError(
                f"[{row['case_id']}] bad included_line_ranges[{i}]: {rng}"
            )
    if row.get("external_tool") and row["external_tool"].get("name") != "rtk":
        raise ValueError(
            f"[{row['case_id']}] external_tool.name must be 'rtk' for RTK methods"
        )
    if _HAS_JSONSCHEMA and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)  # type: ignore[arg-type]


def run_one(
    *,
    method: str,
    case_dir: Path,
    method_results_dir: Path,
    rtk_path: Path,
    rtk_version: str,
    timeout_seconds: float,
    allow_nonzero: bool,
) -> dict:
    case_id = case_dir.name
    raw_path = case_dir / "raw.log"
    argv_tail = METHODS[method](raw_path)
    argv = [str(rtk_path), *argv_tail]

    ctx_path = method_results_dir / f"{case_id}.txt"
    stderr_path = method_results_dir / f"{case_id}.stderr.txt"

    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"[{case_id}] rtk timed out after {timeout_seconds}s: "
            f"{' '.join(argv)}"
        ) from e
    runtime_ms = (time.perf_counter() - t0) * 1000

    if res.returncode != 0 and not allow_nonzero:
        raise RuntimeError(
            f"[{case_id}] rtk returned non-zero ({res.returncode}). "
            f"argv={argv}. stderr={(res.stderr or b'').decode('utf-8', 'replace')[:400]}"
        )

    ctx_path.write_bytes(res.stdout)
    stderr_path_out: str | None = None
    stderr_text = ""
    if res.stderr:
        stderr_path.write_bytes(res.stderr)
        stderr_path_out = str(stderr_path.relative_to(ROOT))
        stderr_text = res.stderr.decode("utf-8", errors="replace")

    # Surface rtk truncation warnings into the manifest so consumers can
    # audit them. Per Codex adversarial review 2026-05-08-#2 [high]:
    # rtk silently truncates input at 10 MiB and emits a warning ONLY in
    # stderr; previously the manifest carried only stderr_path so callers
    # had to read the file to discover the warning. The argocd 12.8 MB log
    # tripped this on Batch 5 and the §3f finding was at risk of resting
    # on a silently-truncated artifact (it didn't, by chance, but the
    # gap was real). Now the manifest declares truncation in metadata.
    truncation_warning = None
    truncated = False
    if "stdout exceeds" in stderr_text and "filter input truncated" in stderr_text:
        truncated = True
        # Capture the first matching line for the manifest record.
        for line in stderr_text.splitlines():
            if "filter input truncated" in line:
                truncation_warning = line.strip()
                break

    # Count output lines from the captured stdout bytes (after utf-8 decode).
    context_text = res.stdout.decode("utf-8", errors="replace")
    output_line_count = context_text.count("\n")
    output_byte_size = len(res.stdout)
    input_byte_size = raw_path.stat().st_size
    input_line_count = (raw_path.read_bytes().count(b"\n"))

    reduction_ratio = (
        0.0 if input_byte_size == 0
        else round(1 - output_byte_size / input_byte_size, 6)
    )
    reduction_ratio = max(0.0, min(1.0, reduction_ratio))

    metadata: dict = {}
    if truncated:
        metadata["rtk_input_truncated"] = True
        metadata["rtk_truncation_warning"] = truncation_warning
        metadata["rtk_truncation_caveat"] = (
            "rtk's filter input was truncated upstream at 10 MiB. The "
            "context file may not reflect the entire raw log; consumers "
            "should treat downstream sv1.1 / signal-recall scores as "
            "lower-bound estimates and not promote findings without "
            "verifying the relevant failure markers are present in the "
            "context file."
        )

    row = {
        "case_id": case_id,
        "method": method,
        "mode": "context_provider",
        "raw_log_path": str(raw_path.relative_to(ROOT)),
        "context_path": str(ctx_path.relative_to(ROOT)),
        "input_line_count": input_line_count,
        "output_line_count": output_line_count,
        "input_byte_size": input_byte_size,
        "output_byte_size": output_byte_size,
        "reduction_ratio": reduction_ratio,
        "included_line_ranges": [],
        "line_mapping_available": False,
        "external_tool": {
            "name": "rtk",
            "version": rtk_version,
            "binary_path": str(rtk_path),
            "command": argv,
            "exit_code": res.returncode,
            "runtime_ms": round(runtime_ms, 3),
            "stderr_path": stderr_path_out,
        },
        "metadata": metadata,
    }
    validate_row(row)
    return row


def run(
    *,
    method: str,
    split: str,
    results_dir: Path,
    rtk_bin: str | None,
    timeout_seconds: float,
    allow_missing: bool,
    allow_nonzero: bool,
    case_id_filter: str | None,
) -> int:
    if method not in METHODS:
        print(f"ERROR: unknown method {method!r}. "
              f"Choices: {', '.join(sorted(METHODS))}", file=sys.stderr)
        return 1

    resolved = resolve_rtk(rtk_bin)
    if resolved is None:
        msg = ("rtk binary not found. Install it "
               "(`brew install rtk` on macOS, or see https://github.com/rtk-ai/rtk) "
               "and ensure it is on PATH, or pass --rtk-bin.")
        if allow_missing:
            print(f"WARNING: {msg} Skipping {method}.", file=sys.stderr)
            return 0
        print(f"ERROR: {msg}", file=sys.stderr)
        return 1
    rtk_path, rtk_version = resolved
    print(f"RTK: {rtk_path} ({rtk_version})")

    cases_dir = ROOT / "cases" / split
    if not cases_dir.is_dir():
        print(f"ERROR: split dir not found: {cases_dir}", file=sys.stderr)
        return 1

    method_results_dir = results_dir / split / method
    method_results_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = results_dir / split / f"{method}.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    case_dirs = sorted(
        p for p in cases_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if case_id_filter:
        case_dirs = [p for p in case_dirs if p.name == case_id_filter]
        if not case_dirs:
            print(f"ERROR: case_id {case_id_filter!r} not found under {cases_dir}",
                  file=sys.stderr)
            return 1

    rows: list[dict] = []
    for case_dir in case_dirs:
        if not (case_dir / "raw.log").exists():
            print(f"  skip {case_dir.name}: no raw.log", file=sys.stderr)
            continue
        try:
            row = run_one(
                method=method,
                case_dir=case_dir,
                method_results_dir=method_results_dir,
                rtk_path=rtk_path,
                rtk_version=rtk_version,
                timeout_seconds=timeout_seconds,
                allow_nonzero=allow_nonzero,
            )
        except Exception as e:
            print(f"  FAIL {case_dir.name}: {e}", file=sys.stderr)
            return 1
        rows.append(row)
        print(f"  {case_dir.name}: "
              f"{row['input_byte_size']:>7d} -> {row['output_byte_size']:>6d} bytes "
              f"(reduction {row['reduction_ratio']:.2%}) "
              f"exit={row['external_tool']['exit_code']} "
              f"runtime={row['external_tool']['runtime_ms']:.1f}ms")

    # When we ran a single-case debug, do not clobber the full manifest —
    # it's for analysis, not for overwriting the canonical results.
    if case_id_filter:
        debug_path = manifest_path.with_suffix(f".debug.{case_id_filter}.jsonl")
        with debug_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote debug manifest {debug_path.relative_to(ROOT)} "
              f"(skipped overwriting {manifest_path.relative_to(ROOT)})")
        return 0

    with manifest_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {manifest_path.relative_to(ROOT)}")
    if not _HAS_JSONSCHEMA:
        print("note: jsonschema not installed — used structural checks only "
              "(pip install jsonschema for full schema validation)",
              file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run an RTK context-provider baseline.")
    ap.add_argument("--method", required=True, choices=sorted(METHODS.keys()))
    ap.add_argument("--split", default="dev")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--rtk-bin", default=None,
                    help="Override the rtk binary (default: whichever is on PATH).")
    ap.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_S,
                    help=f"Per-case timeout (default: {DEFAULT_TIMEOUT_S}s).")
    ap.add_argument("--allow-missing", action="store_true",
                    help="Skip (exit 0) instead of failing when rtk isn't installed.")
    ap.add_argument("--allow-nonzero", action="store_true",
                    help="Don't fail when rtk returns a non-zero exit code.")
    ap.add_argument("--case-id", default=None,
                    help="Debug a single case; writes to a .debug.<case_id>.jsonl.")
    args = ap.parse_args(argv)

    return run(
        method=args.method,
        split=args.split,
        results_dir=args.results_dir,
        rtk_bin=args.rtk_bin,
        timeout_seconds=args.timeout_seconds,
        allow_missing=args.allow_missing,
        allow_nonzero=args.allow_nonzero,
        case_id_filter=args.case_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
