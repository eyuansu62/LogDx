"""
Run a context-provider baseline over a case split.

Usage:
    python tools/run_baseline.py --method raw --split dev
    python tools/run_baseline.py --method tail --split dev --tail-lines 500
    python tools/run_baseline.py --method grep --split dev --before 3 --after 8

Outputs:
    results/<split>/<method>/<case_id>.txt   — the context each method would hand to an agent
    results/<split>/<method>.jsonl           — one manifest row per case

Only three methods are implemented, by design: raw, tail, grep. See
`cilogbench_milestone2_plan.md` for the scope. Every non-raw method must track
`included_line_ranges` (1-indexed, inclusive) so the signal-recall evaluator
can score against ground-truth evidence lines without re-parsing the output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "method_output.schema.json"

DEFAULT_TAIL_LINES = 200
DEFAULT_GREP_BEFORE = 3
DEFAULT_GREP_AFTER = 8
DEFAULT_GREP_REGEX = (
    r"error|failed|failure|traceback|exception|assert|panic|exit code|##\[error\]"
)


try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_case_lines(raw_path: Path) -> list[str]:
    """Return lines without their trailing newline, preserving line order."""
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    # splitlines() loses the final newline but preserves content — since we
    # track output as re-joined lines, this is fine.
    return text.splitlines()


def merge_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    """Merge overlapping or adjacent 1-indexed inclusive [start,end] ranges."""
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: list[list[int]] = [[ranges[0][0], ranges[0][1]]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def ranges_to_lines(ranges: list[list[int]]) -> list[int]:
    """Flatten merged ranges back into a sorted unique list of line numbers."""
    out: list[int] = []
    for s, e in ranges:
        out.extend(range(s, e + 1))
    return out


# ---------------------------------------------------------------------------
# Baseline implementations
# ---------------------------------------------------------------------------


@dataclass
class BaselineResult:
    output_text: str
    included_line_ranges: list[list[int]]
    metadata: dict = field(default_factory=dict)


def baseline_raw(lines: list[str], **_: object) -> BaselineResult:
    n = len(lines)
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return BaselineResult(
        output_text=text,
        included_line_ranges=[[1, n]] if n else [],
        metadata={},
    )


def baseline_tail(lines: list[str], *, tail_lines: int, **_: object) -> BaselineResult:
    n = len(lines)
    take = min(tail_lines, n)
    start = max(1, n - take + 1)
    text = "\n".join(lines[start - 1:])
    if text and not text.endswith("\n"):
        text += "\n"
    return BaselineResult(
        output_text=text,
        included_line_ranges=[[start, n]] if n else [],
        metadata={"tail_lines": tail_lines},
    )


def baseline_grep(
    lines: list[str],
    *,
    regex: str,
    before: int,
    after: int,
    **_: object,
) -> BaselineResult:
    pat = re.compile(regex, re.IGNORECASE)
    n = len(lines)
    raw_ranges: list[tuple[int, int]] = []
    for i, line in enumerate(lines, start=1):
        if pat.search(line):
            start = max(1, i - before)
            end = min(n, i + after)
            raw_ranges.append((start, end))
    merged = merge_ranges(raw_ranges)
    # Build output in line order from merged ranges
    selected_lines = ranges_to_lines(merged)
    text = "\n".join(lines[i - 1] for i in selected_lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return BaselineResult(
        output_text=text,
        included_line_ranges=merged,
        metadata={"regex": regex, "before": before, "after": after},
    )


BASELINES: dict[str, Callable[..., BaselineResult]] = {
    "raw":  baseline_raw,
    "tail": baseline_tail,
    "grep": baseline_grep,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def build_manifest_row(
    *,
    case_id: str,
    method: str,
    raw_path: Path,
    context_path: Path,
    raw_lines: list[str],
    result: BaselineResult,
) -> dict:
    output_line_count = result.output_text.count("\n")
    output_byte_size = len(result.output_text.encode("utf-8"))
    input_byte_size = raw_path.stat().st_size
    reduction_ratio = (
        0.0 if input_byte_size == 0
        else round(1 - output_byte_size / input_byte_size, 6)
    )
    return {
        "case_id": case_id,
        "method": method,
        "mode": "context_provider",
        "raw_log_path": str(raw_path.relative_to(ROOT)),
        "context_path": str(context_path.relative_to(ROOT)),
        "input_line_count": len(raw_lines),
        "output_line_count": output_line_count,
        "input_byte_size": input_byte_size,
        "output_byte_size": output_byte_size,
        "reduction_ratio": max(0.0, min(1.0, reduction_ratio)),
        "included_line_ranges": result.included_line_ranges,
        "metadata": result.metadata,
    }


def validate_row(row: dict) -> None:
    """Schema-check the row when jsonschema is available; always do structural sanity."""
    if row["mode"] != "context_provider":
        raise ValueError(f"[{row['case_id']}] mode must be context_provider")
    if row["input_line_count"] < row["output_line_count"]:
        raise ValueError(
            f"[{row['case_id']}] output_line_count {row['output_line_count']} "
            f"exceeds input_line_count {row['input_line_count']}"
        )
    if not (0.0 <= row["reduction_ratio"] <= 1.0):
        raise ValueError(
            f"[{row['case_id']}] reduction_ratio out of [0,1]: {row['reduction_ratio']}"
        )
    for i, rng in enumerate(row["included_line_ranges"]):
        if len(rng) != 2 or rng[0] < 1 or rng[1] < rng[0]:
            raise ValueError(
                f"[{row['case_id']}] bad included_line_ranges[{i}]: {rng}"
            )
        if rng[1] > row["input_line_count"]:
            raise ValueError(
                f"[{row['case_id']}] included_line_ranges[{i}] end {rng[1]} "
                f"exceeds input_line_count {row['input_line_count']}"
            )
    if _HAS_JSONSCHEMA and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)  # type: ignore[arg-type]


def run(
    *,
    method: str,
    split: str,
    results_dir: Path,
    tail_lines: int,
    before: int,
    after: int,
    regex: str,
) -> int:
    cases_dir = ROOT / "cases" / split
    if not cases_dir.is_dir():
        print(f"ERROR: split dir not found: {cases_dir}", file=sys.stderr)
        return 1
    method_fn = BASELINES[method]

    method_results_dir = results_dir / split / method
    method_results_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = results_dir / split / f"{method}.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    case_dirs = sorted(
        p for p in cases_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    if not case_dirs:
        print(f"WARNING: no cases under {cases_dir}", file=sys.stderr)

    rows: list[dict] = []
    for case_dir in case_dirs:
        case_id = case_dir.name
        raw_path = case_dir / "raw.log"
        if not raw_path.exists():
            print(f"  skip {case_id}: no raw.log", file=sys.stderr)
            continue

        raw_lines = read_case_lines(raw_path)
        result = method_fn(
            raw_lines,
            tail_lines=tail_lines,
            regex=regex,
            before=before,
            after=after,
        )

        ctx_path = method_results_dir / f"{case_id}.txt"
        ctx_path.write_text(result.output_text, encoding="utf-8")

        row = build_manifest_row(
            case_id=case_id,
            method=method,
            raw_path=raw_path,
            context_path=ctx_path,
            raw_lines=raw_lines,
            result=result,
        )
        try:
            validate_row(row)
        except Exception as e:
            print(f"  FAIL validation for {case_id}: {e}", file=sys.stderr)
            return 1
        rows.append(row)

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
    ap = argparse.ArgumentParser(description="Run a context-provider baseline.")
    ap.add_argument("--method", required=True, choices=sorted(BASELINES.keys()))
    ap.add_argument("--split", default="dev",
                    help="Split directory name under cases/ (default: dev).")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results",
                    help="Output root (default: results).")
    ap.add_argument("--tail-lines", type=int, default=DEFAULT_TAIL_LINES,
                    help=f"Lines to keep for tail baseline (default: {DEFAULT_TAIL_LINES}).")
    ap.add_argument("--before", type=int, default=DEFAULT_GREP_BEFORE,
                    help=f"Grep context lines before each match (default: {DEFAULT_GREP_BEFORE}).")
    ap.add_argument("--after", type=int, default=DEFAULT_GREP_AFTER,
                    help=f"Grep context lines after each match (default: {DEFAULT_GREP_AFTER}).")
    ap.add_argument("--regex", default=DEFAULT_GREP_REGEX,
                    help="Grep regex (default matches common failure keywords).")
    args = ap.parse_args(argv)

    return run(
        method=args.method,
        split=args.split,
        results_dir=args.results_dir,
        tail_lines=args.tail_lines,
        before=args.before,
        after=args.after,
        regex=args.regex,
    )


if __name__ == "__main__":
    raise SystemExit(main())
