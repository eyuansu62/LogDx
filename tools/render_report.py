"""
Render the cross-method signal-recall markdown report.

Usage:
    python tools/render_report.py --split dev --methods raw tail grep \
        rtk-read rtk-log rtk-err-cat

Inputs:
    results/<split>/eval_<method>.json (one per method)

Output:
    reports/<split>_signal_recall.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_eval(split: str, method: str, results_dir: Path) -> dict:
    path = results_dir / split / f"eval_{method}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run "
            f"`tools/evaluate_signal_recall.py --method {method} --split {split}` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float | None) -> str:
    if x is None:
        return "N/A"
    return f"{x * 100:.1f}%"


def mapping_label(ev: dict) -> str:
    """Summarize whether the method preserves original-line mapping.
    Mixed is possible in principle but unusual in practice."""
    vals = {c.get("line_mapping_available", True) for c in ev["cases"]}
    if vals == {True}:
        return "line"
    if vals == {False}:
        return "text"
    return "mixed"


def load_manifest(split: str, method: str, results_dir: Path) -> list[dict]:
    path = results_dir / split / f"{method}.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def token_stats(rows: list[dict]) -> tuple[int, int]:
    """Return (processing_tokens, final_context_tokens) averaged across cases.

    For LLM methods with metadata.usage, processing = input+output across all
    LLM calls. For non-LLM baselines, processing is 0 (no summarization work)
    and final_context is estimated from output byte size (chars/4 ≈ tokens).
    """
    if not rows:
        return 0, 0
    processing_total = 0
    final_total = 0
    for r in rows:
        meta = r.get("metadata") or {}
        usage = meta.get("usage") or {}
        proc = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        # For non-LLM baselines there is no usage — proc stays 0.
        final = int(meta.get("final_context_tokens_estimate", 0))
        if final == 0:
            # Estimate from output size for non-LLM methods.
            final = max(1, r["output_byte_size"] // 4) if r["output_byte_size"] else 0
        processing_total += proc
        final_total += final
    n = len(rows)
    return processing_total // n, final_total // n


def humanize_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def render(split: str, methods: list[str], results_dir: Path,
           reports_dir: Path) -> Path:
    evals = [load_eval(split, m, results_dir) for m in methods]
    manifests = [load_manifest(split, m, results_dir) for m in methods]

    # Stable case order = first method's case order, plus any later-method
    # case_ids not seen.
    case_ids: list[str] = []
    for ev in evals:
        for c in ev["cases"]:
            if c["case_id"] not in case_ids:
                case_ids.append(c["case_id"])

    lines: list[str] = []
    lines.append(f"# CILogBench signal-recall report — `{split}`")
    lines.append("")
    lines.append(
        "Context-provider baselines scored against per-case ground truth. "
        "`raw` must score 100% on all recall metrics — if it does not, the "
        "evaluator or the annotations are wrong. `Mapping` indicates whether "
        "a method preserves original raw.log line numbers (`line`) or only "
        "transformed text (`text`). Evidence coverage is line-based and "
        "shows N/A for text-mapped methods."
    )
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Method | Signal Recall | Critical Recall | Evidence Coverage | "
        "Reduction | Mapping | Processing Tokens | Final Context Tokens |"
    )
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|")
    for ev, manifest in zip(evals, manifests):
        proc_toks, final_toks = token_stats(manifest)
        lines.append(
            f"| {ev['method']} "
            f"| {pct(ev['macro_signal_recall'])} "
            f"| {pct(ev['macro_critical_signal_recall'])} "
            f"| {pct(ev['macro_evidence_span_coverage'])} "
            f"| {pct(ev['macro_reduction_ratio'])} "
            f"| {mapping_label(ev)} "
            f"| {humanize_tokens(proc_toks)} "
            f"| {humanize_tokens(final_toks)} |"
        )
    lines.append("")
    lines.append(
        "Token columns are per-case averages. _Processing Tokens_ counts "
        "summarization cost (map+reduce input+output tokens) and is 0 for "
        "non-LLM baselines. _Final Context Tokens_ estimates the size of "
        "the context handed to a downstream reader."
    )
    lines.append("")
    lines.append(f"Cases in split: **{evals[0]['case_count']}**.")
    lines.append("")

    # Per-case tables
    def method_header() -> tuple[str, str]:
        h = "| Case | " + " | ".join(m for m in methods) + " |"
        s = "|---|" + "|".join("---:" for _ in methods) + "|"
        return h, s

    for title, key in [
        ("Per-case signal recall", "signal_recall"),
        ("Per-case critical signal recall", "critical_signal_recall"),
        ("Per-case reduction", "reduction_ratio"),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        h, s = method_header()
        lines.append(h); lines.append(s)
        for cid in case_ids:
            row = [f"`{cid}`"]
            for ev in evals:
                hit = next((c for c in ev["cases"] if c["case_id"] == cid), None)
                row.append(pct(hit[key]) if hit else "—")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # Notable misses, grouped by case (cross-method view so you can see which
    # methods collectively failed each case).
    lines.append("## Notable misses")
    lines.append("")
    for cid in case_ids:
        # Per-method miss counts
        lines.append(f"### `{cid}`")
        lines.append("")
        any_miss = False
        for ev in evals:
            hit = next((c for c in ev["cases"] if c["case_id"] == cid), None)
            if not hit:
                continue
            ms = hit.get("missed_signals", [])
            if not ms:
                continue
            any_miss = True
            lines.append(f"- **{ev['method']}** — "
                         f"missed {len(ms)} signal(s):")
            for m in ms:
                parts = [f"type={m.get('type')}",
                         f"importance={m.get('importance')}"]
                if m.get("value"):
                    v = m["value"]
                    if len(v) > 100:
                        v = v[:100] + "…"
                    parts.append(f"value={v!r}")
                if m.get("file"):
                    parts.append(f"file={m['file']}:{m.get('line','?')}")
                lines.append(f"  - {' · '.join(parts)}")
        if not any_miss:
            lines.append("- All methods preserved every required signal.")
        lines.append("")

    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{split}_signal_recall.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--methods", nargs="+",
                    default=["raw", "tail", "grep",
                             "rtk-read", "rtk-log", "rtk-err-cat"])
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)
    try:
        render(args.split, args.methods, args.results_dir, args.reports_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
