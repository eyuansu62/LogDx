"""
Render a markdown report for a diagnoser's evaluation.

Usage:
    python tools/render_diagnosis_report.py --split dev --diagnoser debugger-v1-mock

Input:
    results/<split>/eval_diagnosis_<diagnoser>.json

Output:
    reports/<split>_diagnosis_eval_<diagnoser>.md

Kept deliberately separate from render_report.py (which handles signal
recall reports) so the two audiences — "did the context preserve the
signals?" vs "could a diagnoser act on the context?" — don't get mixed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pct(x: float | None) -> str:
    if x is None:
        return "N/A"
    return f"{x * 100:.1f}%"


def num(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "N/A"
    return f"{x:.{digits}f}"


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def load_eval(split: str, diagnoser: str, results_dir: Path) -> dict:
    path = results_dir / split / f"eval_diagnosis_{diagnoser}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `tools/evaluate_diagnosis.py "
            f"--split {split} --diagnoser {diagnoser}` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest_prompt_sha(split: str, diagnoser: str, method: str,
                             results_dir: Path) -> str:
    path = results_dir / split / "diagnoses" / diagnoser / f"{method}.jsonl"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        return (row.get("metadata") or {}).get("prompt_sha256", "")
    return ""


def render(split: str, diagnoser: str, results_dir: Path,
           reports_dir: Path) -> Path:
    ev = load_eval(split, diagnoser, results_dir)
    methods = ev["methods"]
    # Pick a stable, if-present ordering similar to signal-recall reports.
    preferred = [
        "raw", "tail", "grep",
        "rtk-read", "rtk-log", "rtk-err-cat",
        "llm-summary-v1", "llm-summary-v1-mock",
    ]
    seen = [m["context_method"] for m in methods]
    order = [m for m in preferred if m in seen] + [m for m in seen if m not in preferred]

    prompt_sha = ""
    if order:
        prompt_sha = load_manifest_prompt_sha(
            split, diagnoser, order[0], results_dir,
        )

    lines: list[str] = []
    lines.append(f"# CILogBench diagnosis report — `{split}` / `{diagnoser}`")
    lines.append("")
    if prompt_sha:
        lines.append(f"Prompt SHA256 (first 12): `{prompt_sha[:12]}…`")
    lines.append(f"Cases in split: **{ev['case_count']}**")
    lines.append(f"Methods evaluated: **{len(methods)}** "
                 f"(`{'`, `'.join(order)}`)")
    lines.append("")
    lines.append(
        "This report scores whether a **fixed diagnoser** can identify "
        "the CI failure root cause given each context method's output. "
        "It does NOT evaluate the context methods on their own; that lives "
        "in the signal-recall report."
    )
    lines.append("")

    # Main metric table.
    lines.append("## Main metrics (macro-averaged per context method)")
    lines.append("")
    lines.append(
        "| Context Method | Success | Category Acc | Critical Mention "
        "| Must Mention | File Recall | Test Recall | Forbidden | Conf Err "
        "| Context Tok | Diagnosis Tok | score_v1 (exp) |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    method_by_name = {m["context_method"]: m for m in methods}
    for name in order:
        b = method_by_name[name]
        lines.append(
            f"| {name} "
            f"| {pct(b['diagnosis_success_rate'])} "
            f"| {pct(b['macro_category_accuracy'])} "
            f"| {pct(b['macro_critical_signal_mention_recall'])} "
            f"| {pct(b['macro_must_mention_coverage'])} "
            f"| {pct(b['macro_relevant_file_recall'])} "
            f"| {pct(b['macro_relevant_test_recall'])} "
            f"| {pct(b['macro_forbidden_claim_violations'])} "
            f"| {pct(b['confident_error_rate'])} "
            f"| {humanize_tokens(b['macro_context_tokens'])} "
            f"| {humanize_tokens(b['macro_diagnosis_tokens'])} "
            f"| {num(b['diagnosis_score_v1'], 3)} |"
        )
    lines.append("")
    lines.append("Columns:")
    lines.append("")
    lines.append("- **Success**: fraction of cases where a non-empty "
                 "diagnosis was produced (no provider error).")
    lines.append("- **Category Acc**: exact match between "
                 "`diagnosis.root_cause_category` and "
                 "`ground_truth.root_cause.category`. `unknown` never "
                 "counts as correct unless ground truth is also `unknown`.")
    lines.append("- **Critical Mention**: fraction of ground-truth "
                 "`required_signals` with `importance=critical` whose "
                 "value/alias/file appears in the diagnosis text.")
    lines.append("- **Must Mention**: fraction of "
                 "`expected_diagnosis.must_mention` substrings present.")
    lines.append("- **Forbidden**: fraction of cases where at least one "
                 "`expected_diagnosis.must_not_claim` substring leaked into "
                 "the diagnosis.")
    lines.append("- **Conf Err**: cases where `confidence >= 0.70` but "
                 "category was wrong or a forbidden claim appeared.")
    lines.append("- **score_v1**: experimental composite; see "
                 "`docs/evaluation/diagnosis_eval_v1.md`.")
    lines.append("")

    # Per-case breakdown.
    case_ids: list[str] = []
    for m in methods:
        for c in m["cases"]:
            if c["case_id"] not in case_ids:
                case_ids.append(c["case_id"])

    for title, key, fmt in [
        ("Per-case category accuracy", "category_accuracy", pct),
        ("Per-case critical signal mention recall",
            "critical_signal_mention_recall", pct),
        ("Per-case forbidden-claim violations",
            "forbidden_claim_violations",
            lambda v: "0" if not v else f"{len(v)}"),
        ("Per-case abstention", "abstained",
            lambda v: "abst." if v else "—"),
        ("Per-case confident error", "confident_error",
            lambda v: "ERR" if v else "—"),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        header = "| Case | " + " | ".join(order) + " |"
        sep = "|---|" + "|".join("---:" for _ in order) + "|"
        lines.append(header); lines.append(sep)
        for cid in case_ids:
            row = [f"`{cid}`"]
            for name in order:
                case = next((c for c in method_by_name[name]["cases"]
                             if c["case_id"] == cid), None)
                row.append(fmt(case.get(key)) if case else "—")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # Per-case failure analysis: which signals were missed across methods.
    lines.append("## Per-case failure analysis")
    lines.append("")
    for cid in case_ids:
        lines.append(f"### `{cid}`")
        lines.append("")
        for name in order:
            case = next((c for c in method_by_name[name]["cases"]
                         if c["case_id"] == cid), None)
            if case is None:
                continue
            miss = case.get("missed_signals") or []
            forbidden = case.get("forbidden_claim_violations") or []
            flags: list[str] = []
            if case["abstained"]: flags.append("abstained")
            if case["confident_error"]: flags.append("CONFIDENT_ERROR")
            if forbidden:
                flags.append(f"forbidden×{len(forbidden)}")
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            lines.append(
                f"- **{name}** — "
                f"pred `{case['root_cause_category']}` "
                f"@ {case['confidence']:.2f}{flag_text}"
            )
            if miss:
                for s in miss[:5]:
                    val = s.get("value") or s.get("file") or ""
                    if len(val) > 80:
                        val = val[:80] + "…"
                    lines.append(f"  - missed [{s.get('importance')}] "
                                 f"{s.get('type')}: `{val}`")
                if len(miss) > 5:
                    lines.append(f"  - … and {len(miss)-5} more")
            if forbidden:
                for f in forbidden:
                    lines.append(f"  - forbidden claim present: `{f}`")
        lines.append("")

    lines.append("## Interpretation guardrails")
    lines.append("")
    lines.append(
        "- Mock diagnoser results validate the pipeline, not real LLM quality. "
        "If `diagnoser` is `debugger-v1-mock`, the numbers are shaped by "
        "simple pattern rules; they should not be read as an endorsement "
        "of any context method."
    )
    lines.append(
        "- Deterministic diagnosis scoring is a proxy, not a full semantic "
        "judge. A method can lose this proxy while producing a diagnosis a "
        "human would accept, and vice versa."
    )
    lines.append(
        "- Raw context is not guaranteed to win with a weak diagnoser: "
        "the diagnoser may drown in irrelevant lines."
    )
    lines.append(
        "- High signal recall does not necessarily imply high diagnosis "
        "accuracy. The context method may preserve evidence in a form the "
        "diagnoser ignores."
    )
    lines.append(
        "- Low context token count is only useful if diagnosis quality "
        "remains acceptable. A 99% reduction that forces abstention is "
        "not a win."
    )
    lines.append(
        "- `score_v1` is experimental. The individual metrics are what "
        "this report is about."
    )
    lines.append("")

    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"{split}_diagnosis_eval_{diagnoser}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--diagnoser", required=True)
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)
    try:
        render(args.split, args.diagnoser, args.results_dir, args.reports_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
