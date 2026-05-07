"""
CILogBench case validator.

Usage:
    python tools/validate_cases.py cases/dev
    python tools/validate_cases.py cases/dev cases/holdout

Checks performed per case directory:
    - raw.log, case.json, ground_truth.json all exist
    - case.json.case_id matches the containing directory name
    - case.json.raw_log_path points to an existing file (relative to case dir)
    - case.json.line_count matches `wc -l`-style line count of raw.log
    - case.json.byte_size matches the byte size of raw.log
    - case.json enum fields (source / framework / failure_category) are in the allowed set
    - ground_truth.root_cause.summary is non-empty
    - ground_truth.required_signals is non-empty; every evidence_lines range is valid
      for raw.log, uses start <= end, and is 1-indexed (>= 1)
    - ground_truth.evidence_spans is non-empty; same line-range rules
    - expected_diagnosis.must_mention and must_not_claim are non-empty arrays
    - raw.log contains no obvious unmasked secret patterns (ghp_, github_pat_, sk-,
      AKIA, BEGIN PRIVATE KEY, Authorization:\\s[^*], Bearer\\s[^*], password=, token=
      with non-masked value)

Exits 0 on success, 1 on any failure. On failure prints case_id, field, reason.

The validator prefers `jsonschema` if installed (for stricter enum / required checks)
but falls back to manual checks otherwise, so the first pass has zero external
dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"

try:
    import jsonschema  # type: ignore

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# Allowed enum values (kept in sync with schemas/*.schema.json).
ALLOWED_SOURCE = {"github_actions", "local_fixture", "unknown"}
ALLOWED_FRAMEWORK = {
    "pytest", "jest", "cargo", "npm", "pnpm", "yarn",
    "docker", "ruff", "eslint", "tsc", "generic", "unknown",
}
ALLOWED_FAILURE_CATEGORY = {
    "test_assertion", "snapshot_diff", "compile_error", "type_error",
    "lint_error", "dependency_install", "docker_build",
    "github_actions_config", "permission_or_secret",
    "timeout_or_oom", "network_or_flaky", "generic_error", "unknown",
}
ALLOWED_SIGNAL_TYPE = {
    "failed_test", "stack_location", "assertion", "exception",
    "panic", "compile_error", "exit_code", "command",
    "package", "version", "diff", "annotation",
    "step_name", "job_name", "workflow_name",
}
ALLOWED_IMPORTANCE = {"critical", "important", "optional"}


# Secret patterns to flag. Each pattern is paired with an optional "masked" check:
# if the match's trailing value is clearly already masked (e.g., `***`), we accept
# it — GitHub Actions auto-masks tokens and those appearances are expected.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ghp_ token",         re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("github_pat_ token",  re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("OpenAI sk- key",     re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{30,}")),
    ("AWS AKIA key",       re.compile(r"AKIA[A-Z0-9]{16}")),
    ("private key header", re.compile(r"BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY")),
    ("Authorization header with non-masked value",
         re.compile(r"Authorization:\s+(?!\*\*\*)[A-Za-z0-9][A-Za-z0-9._/+=-]{20,}")),
    ("Bearer token with non-masked value",
         re.compile(r"Bearer\s+(?!\*\*\*)[A-Za-z0-9][A-Za-z0-9._/+=-]{20,}")),
    ("password= with non-masked value",
         re.compile(r"password=(?!\*\*\*)[^\s\"'&]{8,}")),
    ("token= with non-masked value",
         re.compile(r"token=(?!\*\*\*)[A-Za-z0-9][A-Za-z0-9._/+=-]{20,}")),
]


class ValidationErrors:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str, str]] = []  # (case_id, field, reason)

    def add(self, case_id: str, field: str, reason: str) -> None:
        self.errors.append((case_id, field, reason))

    def __bool__(self) -> bool:
        return bool(self.errors)

    def report(self) -> None:
        for case_id, field, reason in self.errors:
            print(f"  FAIL [{case_id}] {field}: {reason}", file=sys.stderr)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _wc_l(path: Path) -> int:
    """Mimic `wc -l` — count newline characters."""
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            count += chunk.count(b"\n")
    return count


def _load_schema(name: str) -> dict | None:
    p = SCHEMA_DIR / f"{name}.schema.json"
    if not p.exists():
        return None
    return _load_json(p)


def _check_schema(obj: Any, schema_name: str, case_id: str, field: str,
                  errors: ValidationErrors) -> None:
    """If jsonschema is available, run a full schema check."""
    if not _HAS_JSONSCHEMA:
        return
    schema = _load_schema(schema_name)
    if schema is None:
        return
    try:
        jsonschema.validate(obj, schema)  # type: ignore[arg-type]
    except jsonschema.ValidationError as e:  # type: ignore[attr-defined]
        path = ".".join(str(x) for x in e.path) or "(root)"
        errors.add(case_id, f"{field}:{path}", e.message)


def _check_line_range(case_id: str, field: str, rng: Any, max_line: int,
                       errors: ValidationErrors) -> None:
    if (not isinstance(rng, list)) or len(rng) != 2:
        errors.add(case_id, field, f"expected [start,end] pair, got {rng!r}")
        return
    start, end = rng
    if not (isinstance(start, int) and isinstance(end, int)):
        errors.add(case_id, field, f"line numbers must be integers, got {rng!r}")
        return
    if start < 1:
        errors.add(case_id, field,
                    f"start_line {start} must be >= 1 (1-indexed, not 0-indexed)")
    if end < start:
        errors.add(case_id, field, f"end_line {end} < start_line {start}")
    if end > max_line:
        errors.add(case_id, field,
                    f"end_line {end} exceeds log line_count {max_line}")


def _scan_secrets(case_id: str, raw_path: Path, errors: ValidationErrors) -> None:
    try:
        text = raw_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        errors.add(case_id, "raw.log", f"could not read: {e}")
        return
    for label, pat in SECRET_PATTERNS:
        m = pat.search(text)
        if m:
            # Grab enough context for a human to triage quickly.
            pre = text.rfind("\n", 0, m.start()) + 1
            post = text.find("\n", m.end())
            snippet = text[pre:post if post >= 0 else m.end() + 40]
            errors.add(case_id, "raw.log:secret",
                        f"{label} matched: {snippet.strip()[:160]!r}")


def validate_case(case_dir: Path, errors: ValidationErrors) -> None:
    case_id = case_dir.name

    raw_path = case_dir / "raw.log"
    case_path = case_dir / "case.json"
    gt_path = case_dir / "ground_truth.json"

    for required in (raw_path, case_path, gt_path):
        if not required.exists():
            errors.add(case_id, required.name, "missing file")
            return

    try:
        case = _load_json(case_path)
    except json.JSONDecodeError as e:
        errors.add(case_id, "case.json", f"invalid JSON: {e}")
        return
    try:
        gt = _load_json(gt_path)
    except json.JSONDecodeError as e:
        errors.add(case_id, "ground_truth.json", f"invalid JSON: {e}")
        return

    _check_schema(case, "case", case_id, "case.json", errors)
    _check_schema(gt, "ground_truth", case_id, "ground_truth.json", errors)

    if case.get("case_id") != case_id:
        errors.add(case_id, "case.json:case_id",
                    f"case_id {case.get('case_id')!r} != directory name {case_id!r}")

    rel = case.get("raw_log_path", "raw.log")
    raw_target = (case_dir / rel).resolve()
    if not raw_target.exists():
        errors.add(case_id, "case.json:raw_log_path",
                    f"{rel!r} does not resolve to an existing file")
        return

    # Size + line count checks
    actual_bytes = raw_path.stat().st_size
    actual_lines = _wc_l(raw_path)
    if case.get("byte_size") != actual_bytes:
        errors.add(case_id, "case.json:byte_size",
                    f"declared {case.get('byte_size')!r} != actual {actual_bytes}")
    if case.get("line_count") != actual_lines:
        errors.add(case_id, "case.json:line_count",
                    f"declared {case.get('line_count')!r} != actual {actual_lines}")

    # Enum checks (manual — jsonschema does these too when available)
    if case.get("source") not in ALLOWED_SOURCE:
        errors.add(case_id, "case.json:source",
                    f"{case.get('source')!r} not in {sorted(ALLOWED_SOURCE)}")
    if case.get("framework") not in ALLOWED_FRAMEWORK:
        errors.add(case_id, "case.json:framework",
                    f"{case.get('framework')!r} not in {sorted(ALLOWED_FRAMEWORK)}")
    if case.get("failure_category") not in ALLOWED_FAILURE_CATEGORY:
        errors.add(case_id, "case.json:failure_category",
                    f"{case.get('failure_category')!r} not in {sorted(ALLOWED_FAILURE_CATEGORY)}")

    # Ground-truth checks
    root_cause = gt.get("root_cause") or {}
    summary = root_cause.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        errors.add(case_id, "ground_truth.json:root_cause.summary",
                    "must be a non-empty string")
    if root_cause.get("category") not in ALLOWED_FAILURE_CATEGORY:
        errors.add(case_id, "ground_truth.json:root_cause.category",
                    f"{root_cause.get('category')!r} not in "
                    f"{sorted(ALLOWED_FAILURE_CATEGORY)}")

    signals = gt.get("required_signals")
    if not isinstance(signals, list) or not signals:
        errors.add(case_id, "ground_truth.json:required_signals",
                    "must be a non-empty array")
    else:
        for i, sig in enumerate(signals):
            if not isinstance(sig, dict):
                errors.add(case_id, f"ground_truth.json:required_signals[{i}]",
                            "must be an object")
                continue
            if sig.get("type") not in ALLOWED_SIGNAL_TYPE:
                errors.add(case_id, f"ground_truth.json:required_signals[{i}].type",
                            f"{sig.get('type')!r} not in {sorted(ALLOWED_SIGNAL_TYPE)}")
            if sig.get("importance") not in ALLOWED_IMPORTANCE:
                errors.add(case_id,
                            f"ground_truth.json:required_signals[{i}].importance",
                            f"{sig.get('importance')!r} not in "
                            f"{sorted(ALLOWED_IMPORTANCE)}")
            ev = sig.get("evidence_lines")
            if not isinstance(ev, list) or not ev:
                errors.add(case_id,
                            f"ground_truth.json:required_signals[{i}].evidence_lines",
                            "must be a non-empty array of [start,end] pairs")
            else:
                for j, rng in enumerate(ev):
                    _check_line_range(
                        case_id,
                        f"ground_truth.json:required_signals[{i}].evidence_lines[{j}]",
                        rng, actual_lines, errors,
                    )

    spans = gt.get("evidence_spans")
    if not isinstance(spans, list) or not spans:
        errors.add(case_id, "ground_truth.json:evidence_spans",
                    "must be a non-empty array")
    else:
        for i, span in enumerate(spans):
            if not isinstance(span, dict):
                errors.add(case_id, f"ground_truth.json:evidence_spans[{i}]",
                            "must be an object")
                continue
            s = span.get("start_line"); e = span.get("end_line")
            _check_line_range(
                case_id, f"ground_truth.json:evidence_spans[{i}]",
                [s, e], actual_lines, errors,
            )
            if not (isinstance(span.get("reason"), str) and span["reason"].strip()):
                errors.add(case_id,
                            f"ground_truth.json:evidence_spans[{i}].reason",
                            "must be a non-empty string")

    diag = gt.get("expected_diagnosis") or {}
    for field in ("must_mention", "must_not_claim"):
        arr = diag.get(field)
        if not isinstance(arr, list) or not arr:
            errors.add(case_id, f"ground_truth.json:expected_diagnosis.{field}",
                        "must be a non-empty array")

    # Secret scan (raw.log only; case/ground_truth shouldn't contain secrets either,
    # but those are small and handwritten).
    _scan_secrets(case_id, raw_path, errors)


def validate_split(split_dir: Path, errors: ValidationErrors) -> int:
    if not split_dir.exists():
        errors.add(split_dir.as_posix(), "(split)", "directory does not exist")
        return 0
    case_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())
    # Skip hidden (e.g., .gitkeep isn't a dir, but holdout may have just .gitkeep)
    case_dirs = [p for p in case_dirs if not p.name.startswith(".")]
    for case_dir in case_dirs:
        validate_case(case_dir, errors)
    return len(case_dirs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate CILogBench cases.")
    ap.add_argument("split_dirs", nargs="+", type=Path,
                    help="One or more split directories (e.g. cases/dev).")
    args = ap.parse_args(argv)

    all_errors = ValidationErrors()
    totals: list[tuple[Path, int]] = []
    for split in args.split_dirs:
        split_errors = ValidationErrors()
        n = validate_split(split, split_errors)
        totals.append((split, n))
        all_errors.errors.extend(split_errors.errors)

    if not _HAS_JSONSCHEMA:
        print("note: jsonschema not installed — using fallback checks "
              "(pip install jsonschema for full schema validation)", file=sys.stderr)

    for split, n in totals:
        failures = sum(1 for e in all_errors.errors
                       if Path(e[0]).as_posix() != split.as_posix()
                       and (split / e[0]).exists())
        passed = n - failures
        print(f"Validated {n} cases in {split}")
        print(f"- {passed} passed")
        print(f"- {failures} failed")

    if all_errors:
        print("\nFailures:", file=sys.stderr)
        all_errors.report()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
