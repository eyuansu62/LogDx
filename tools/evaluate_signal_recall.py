"""
Score a context-provider baseline against per-case ground truth.

Usage:
    python tools/evaluate_signal_recall.py --method raw       --split dev
    python tools/evaluate_signal_recall.py --method tail      --split dev
    python tools/evaluate_signal_recall.py --method grep      --split dev
    python tools/evaluate_signal_recall.py --method rtk-log   --split dev

Inputs:
    cases/<split>/<case_id>/ground_truth.json
    results/<split>/<method>.jsonl

Output:
    results/<split>/eval_<method>.json

A required signal counts as preserved if one of these holds (in order):

    A. line-based (preferred, deterministic)
         - manifest row has line_mapping_available != false AND
         - every line in the signal's evidence_lines ranges is inside
           the method's included_line_ranges.

    B. text-based (normalized substring match)
         - the signal's value (or one of its aliases) appears in the
           normalized context text. Normalization: strip ANSI escapes,
           normalize CRLF→LF, trim surrounding whitespace.
         - For methods where line_mapping_available=false (e.g. RTK),
           this is the primary path.
         - For raw/tail/grep, this is a fallback when evidence_lines
           are unavailable.

Evidence-span coverage is computed only when line_mapping_available is
true. For unmapped methods the metric is null and the per-case row sets
`evidence_span_coverage_available=false`; macro averages omit null values.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent

# Strip ANSI CSI and OSC sequences (covers colors, cursor moves, hyperlinks).
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_ground_truth(split: str, case_id: str) -> dict:
    path = ROOT / "cases" / split / case_id / "ground_truth.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(results_dir: Path, split: str, method: str) -> list[dict]:
    path = results_dir / split / f"{method}.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"manifest not found: {path}. "
            f"Run `tools/run_baseline.py --method {method} --split {split}` "
            f"(or `tools/run_rtk_baseline.py` for RTK methods) first."
        )
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def normalize_text(s: str) -> str:
    """ANSI-strip + CRLF→LF. We deliberately keep case and internal whitespace
    unchanged so substring matches remain strict."""
    s = ANSI_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


class LineSet:
    """Fast membership test over merged 1-indexed inclusive ranges."""

    def __init__(self, ranges: list[list[int]]):
        self.ranges = sorted((s, e) for s, e in ranges)
        self._starts = [s for s, _ in self.ranges]

    def __contains__(self, line_no: int) -> bool:
        i = bisect.bisect_right(self._starts, line_no) - 1
        if i < 0:
            return False
        s, e = self.ranges[i]
        return s <= line_no <= e

    def covers_range(self, start: int, end: int) -> bool:
        return all(n in self for n in range(start, end + 1))

    def count_covered(self, start: int, end: int) -> int:
        return sum(1 for n in range(start, end + 1) if n in self)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _text_preserved(sig: dict, ctx: str) -> str | None:
    """Return which match fired: 'text' (primary value), 'alias', 'file' (for
    stack_location signals that carry file+line instead of value), or None."""
    probe = (sig.get("value") or "").strip()
    if probe and probe in ctx:
        return "text"
    aliases = sig.get("aliases") or []
    for alt in aliases:
        alt_s = (alt or "").strip()
        if alt_s and alt_s in ctx:
            return "alias"
    # stack_location signals typically set `file` (+optional `line`) rather
    # than `value`. Fall back to the filepath — a strict substring match on
    # the filepath is a reasonable definition of "the location survived the
    # transformation". We intentionally do not require the line number, since
    # many compressors (including RTK) elide line numbers while keeping the
    # file reference in a summary row.
    file_probe = (sig.get("file") or "").strip()
    if file_probe and file_probe in ctx:
        return "file"
    return None


def score_case(*, manifest_row: dict, ground_truth: dict,
               context_text: str) -> dict:
    line_mapping = manifest_row.get("line_mapping_available", True)
    line_set = LineSet(manifest_row.get("included_line_ranges", []))
    normalized_ctx = normalize_text(context_text)

    signals = ground_truth.get("required_signals", [])
    critical_signals = [s for s in signals if s.get("importance") == "critical"]

    preserved_total = 0
    preserved_critical = 0
    missed_signals: list[dict] = []
    per_signal: list[dict] = []

    for sig in signals:
        ev_ranges = sig.get("evidence_lines") or []

        line_hit = (
            line_mapping
            and bool(ev_ranges)
            and all(line_set.covers_range(s, e) for s, e in ev_ranges)
        )
        preserved_via: str | None = None
        if line_hit:
            preserved_via = "evidence_lines"
        else:
            match = _text_preserved(sig, normalized_ctx)
            if match == "text":
                preserved_via = "text_fallback"
            elif match == "alias":
                preserved_via = "alias"
            elif match == "file":
                # stack_location signals without an explicit `value` fall back
                # to the filepath.
                preserved_via = "file_fallback"

        ok = preserved_via is not None
        if ok:
            preserved_total += 1
            if sig.get("importance") == "critical":
                preserved_critical += 1
        else:
            missed = {
                "type": sig.get("type"),
                "importance": sig.get("importance"),
            }
            if "value" in sig:   missed["value"] = sig["value"]
            if "aliases" in sig: missed["aliases"] = sig["aliases"]
            if "file" in sig:    missed["file"] = sig["file"]
            if "line" in sig:    missed["line"] = sig["line"]
            missed["evidence_lines"] = ev_ranges
            missed_signals.append(missed)

        per_signal.append({
            "type": sig.get("type"),
            "importance": sig.get("importance"),
            "preserved": ok,
            "preserved_via": preserved_via,
        })

    signal_recall = (preserved_total / len(signals)) if signals else 1.0
    critical_recall = (
        (preserved_critical / len(critical_signals))
        if critical_signals else 1.0
    )

    spans = ground_truth.get("evidence_spans", [])
    total_span_lines = sum(sp["end_line"] - sp["start_line"] + 1 for sp in spans)

    if line_mapping and total_span_lines:
        covered_span_lines = sum(
            line_set.count_covered(sp["start_line"], sp["end_line"])
            for sp in spans
        )
        span_coverage: float | None = covered_span_lines / total_span_lines
        span_coverage_available = True
    elif line_mapping and not total_span_lines:
        covered_span_lines = 0
        span_coverage = 1.0
        span_coverage_available = True
    else:
        covered_span_lines = None  # type: ignore[assignment]
        span_coverage = None
        span_coverage_available = False

    return {
        "case_id": manifest_row["case_id"],
        "signal_recall": round(signal_recall, 4),
        "critical_signal_recall": round(critical_recall, 4),
        "evidence_span_coverage": (
            round(span_coverage, 4) if span_coverage is not None else None
        ),
        "evidence_span_coverage_available": span_coverage_available,
        "reduction_ratio": manifest_row.get("reduction_ratio", 0.0),
        "line_mapping_available": line_mapping,
        "signals_total": len(signals),
        "signals_preserved": preserved_total,
        "critical_total": len(critical_signals),
        "critical_preserved": preserved_critical,
        "evidence_lines_total": total_span_lines,
        "evidence_lines_covered": covered_span_lines,
        "missed_signals": missed_signals,
        "per_signal": per_signal,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _macro(values: Iterable[float | None]) -> float | None:
    pool = [v for v in values if v is not None]
    if not pool:
        return None
    return round(sum(pool) / len(pool), 4)


def evaluate(*, method: str, split: str, results_dir: Path) -> int:
    try:
        manifest_rows = load_manifest(results_dir, split, method)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    per_case: list[dict] = []
    for row in manifest_rows:
        gt = load_ground_truth(split, row["case_id"])
        context_path = ROOT / row["context_path"]
        context_text = (
            context_path.read_text(encoding="utf-8", errors="replace")
            if context_path.exists() else ""
        )
        per_case.append(score_case(
            manifest_row=row, ground_truth=gt, context_text=context_text,
        ))

    out = {
        "split": split,
        "method": method,
        "case_count": len(per_case),
        "macro_signal_recall":          _macro(c["signal_recall"] for c in per_case),
        "macro_critical_signal_recall": _macro(c["critical_signal_recall"] for c in per_case),
        "macro_evidence_span_coverage": _macro(c["evidence_span_coverage"] for c in per_case),
        "macro_reduction_ratio":        _macro(c["reduction_ratio"] for c in per_case),
        "cases": per_case,
    }

    out_path = results_dir / split / f"eval_{method}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    def fmt(x: float | None) -> str:
        return "N/A" if x is None else f"{x:.4f}"
    print(f"  macro_signal_recall          = {fmt(out['macro_signal_recall'])}")
    print(f"  macro_critical_signal_recall = {fmt(out['macro_critical_signal_recall'])}")
    print(f"  macro_evidence_span_coverage = {fmt(out['macro_evidence_span_coverage'])}")
    print(f"  macro_reduction_ratio        = {fmt(out['macro_reduction_ratio'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Score a baseline's context outputs against ground truth."
    )
    ap.add_argument("--method", required=True,
                    help="Method name matching the .jsonl manifest "
                         "(raw/tail/grep/rtk-read/rtk-log/rtk-err-cat/...).")
    ap.add_argument("--split", default="dev",
                    help="Split directory name under cases/ and results/ (default: dev).")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results",
                    help="Output root (default: results).")
    args = ap.parse_args(argv)
    return evaluate(method=args.method, split=args.split,
                     results_dir=args.results_dir)


if __name__ == "__main__":
    raise SystemExit(main())
