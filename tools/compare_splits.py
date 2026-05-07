"""
Render a dev-vs-holdout comparison for a locked protocol + diagnoser.

Reads the signal-recall and diagnosis evaluations for both splits and
writes:
    results/dev_vs_holdout_<protocol_id>.json
    reports/dev_vs_holdout_<protocol_id>.md

Flags methods with a ≥20pp absolute gap between dev and holdout on any
recall metric. The flag is diagnostic, not a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GAP_THRESHOLD = 0.20  # 20 percentage points


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float | None) -> str:
    return "N/A" if x is None else f"{x * 100:.1f}%"


def gap(dev: float | None, hold: float | None) -> float | None:
    if dev is None or hold is None:
        return None
    return round(hold - dev, 4)


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def sig_row(split: str, method: str, results_dir: Path) -> dict:
    ev = load_json(results_dir / split / f"eval_{method}.json") or {}
    return {
        "signal_recall": ev.get("macro_signal_recall"),
        "critical_signal_recall": ev.get("macro_critical_signal_recall"),
        "evidence_coverage": ev.get("macro_evidence_span_coverage"),
        "reduction": ev.get("macro_reduction_ratio"),
    }


def diag_row(diag_eval: dict | None, method: str) -> dict:
    if not diag_eval:
        return {}
    for mb in diag_eval.get("methods", []):
        if mb["context_method"] == method:
            return {
                "category_accuracy":     mb.get("macro_category_accuracy"),
                "critical_mention":      mb.get("macro_critical_signal_mention_recall"),
                "forbidden":             mb.get("macro_forbidden_claim_violations"),
                "confident_error":       mb.get("confident_error_rate"),
                "abstention":            mb.get("abstention_rate"),
                "context_tokens":        mb.get("macro_context_tokens"),
            }
    return {}


def _render_multi(
    protocol_path: Path, protocol_id: str, splits: list[str],
    methods: list[str], diag_by_split: dict[str, dict | None],
    diagnoser: str | None, results_dir: Path, reports_dir: Path,
) -> int:
    """Render a 3+-split comparison report."""
    comparisons: list[dict] = []
    for m in methods:
        per_split: dict[str, dict] = {}
        for s in splits:
            sig = sig_row(s, m, results_dir)
            d = diag_row(diag_by_split.get(s), m) if diagnoser else {}
            per_split[s] = {**sig, **d}
        gap_metrics = ["signal_recall", "critical_signal_recall", "reduction"]
        if diagnoser:
            gap_metrics += ["category_accuracy", "critical_mention", "confident_error"]
        gaps: dict[str, float | None] = {}
        for k in gap_metrics:
            vals = [per_split[s].get(k) for s in splits]
            pairs = [abs(vals[i] - vals[j])
                     for i in range(len(vals)) for j in range(i+1, len(vals))
                     if vals[i] is not None and vals[j] is not None]
            gaps[k] = round(max(pairs), 4) if pairs else None
        large_gaps = [k for k, v in gaps.items() if v is not None and v >= GAP_THRESHOLD]
        comparisons.append({
            "method": m, "splits": per_split,
            "max_gaps": gaps, "large_gaps": large_gaps,
        })

    slug = protocol_id.replace("-", "_").replace(".", "_")
    out_json = results_dir / f"{'_'.join(splits)}_comparison_{slug}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps({
            "protocol_id": protocol_id, "splits": splits,
            "diagnoser": diagnoser,
            "gap_threshold_abs_pp": GAP_THRESHOLD,
            "methods": comparisons,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md: list[str] = []
    md.append(f"# {' vs '.join(splits)} — `{protocol_id}`")
    md.append("")
    if diagnoser:
        md.append(f"Diagnoser: `{diagnoser}`")
        md.append("")
    md.append(
        f"Methods flagged with `*` have a maximum absolute pairwise gap "
        f"≥ {int(GAP_THRESHOLD*100)} pp across the {len(splits)} splits "
        f"on at least one metric."
    )
    md.append("")

    hdr = "| Method | " + " | ".join(f"{s} sig" for s in splits) + " | Max gap |"
    sep = "|---|" + "|".join(["---:"] * (len(splits) + 1)) + "|"

    for title, key in [
        ("Signal recall by split", "signal_recall"),
        ("Critical signal recall by split", "critical_signal_recall"),
        ("Reduction by split", "reduction"),
    ]:
        md.append(f"## {title}")
        md.append("")
        md.append(hdr); md.append(sep)
        for c in comparisons:
            flag = " *" if c["large_gaps"] and key == "signal_recall" else ""
            row = [f"{c['method']}{flag}"]
            for s in splits:
                row.append(pct(c["splits"][s].get(key)))
            row.append(pct(c["max_gaps"].get(key)))
            md.append("| " + " | ".join(row) + " |")
        md.append("")

    if diagnoser:
        for title, key in [
            (f"Diagnosis category accuracy — `{diagnoser}`", "category_accuracy"),
            (f"Critical mention — `{diagnoser}`", "critical_mention"),
            (f"Confident error rate — `{diagnoser}`", "confident_error"),
        ]:
            md.append(f"## {title}")
            md.append("")
            md.append(hdr); md.append(sep)
            for c in comparisons:
                row = [c["method"]]
                for s in splits:
                    row.append(pct(c["splits"][s].get(key)))
                row.append(pct(c["max_gaps"].get(key)))
                md.append("| " + " | ".join(row) + " |")
            md.append("")

    md.append("## Methods with large split gaps")
    md.append("")
    any_flag = False
    for c in comparisons:
        if not c["large_gaps"]:
            continue
        any_flag = True
        md.append(f"- `{c['method']}` — gap on: "
                   + ", ".join(f"`{g}`" for g in c["large_gaps"]))
    if not any_flag:
        md.append("- No method crosses the ≥20pp threshold on any metric.")
    md.append("")

    md.append("## Split composition (from split manifests)")
    md.append("")
    md.append("| Split | Cases | Frameworks | Failure categories |")
    md.append("|---|---:|---|---|")
    for s in splits:
        mfp = ROOT / "cases" / s / "split_manifest.json"
        if mfp.exists():
            m_ = json.loads(mfp.read_text(encoding="utf-8"))
            fw = ", ".join(f"{k}×{v}" for k, v in sorted(m_.get("framework_counts", {}).items()))
            cat = ", ".join(f"{k}×{v}" for k, v in sorted(m_.get("category_counts", {}).items()))
            md.append(f"| {s} | {m_.get('case_count')} | {fw} | {cat} |")
    md.append("")

    md.append("## Interpretation guardrails")
    md.append("")
    md.append(
        f"- This comparison uses only the cases locked in "
        f"`{protocol_path.relative_to(ROOT)}`. The stress split is "
        f"intentionally adversarial; a 20pp gap vs dev is a signal of "
        f"brittleness, not automatic method failure."
    )
    md.append(
        "- Mock diagnosis numbers validate the pipeline only. Real "
        "model numbers live under M10."
    )
    md.append(
        "- Small case counts: a single case flipping can shift a macro "
        "metric by 17-25pp. Prefer critical_signal_recall and max-gap "
        "patterns over single-number rankings."
    )
    md.append(
        "- `category_accuracy` depends on the category distribution of "
        "each split. If the mock diagnoser scores 0% on stress, that is "
        "almost certainly a mock-heuristic gap, not a context-method "
        "problem."
    )

    out_md = reports_dir / f"{'_'.join(splits)}_comparison_{slug}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare dev vs holdout under a locked protocol.")
    ap.add_argument("--protocol", required=True, type=Path)
    ap.add_argument("--splits", default="dev,holdout",
                    help="Comma-separated split list (e.g. dev,holdout,stress). "
                         "Two splits use the legacy dev-vs-holdout renderer; "
                         "three or more use the multi-split renderer.")
    ap.add_argument("--diagnoser", default=None,
                    help="Diagnoser name; when given, diagnosis metrics are "
                         "added to the comparison.")
    ap.add_argument("--methods", default=None,
                    help="Comma-separated method subset. Defaults to every "
                         "method for which every requested split has a signal eval.")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    protocol_path = args.protocol if args.protocol.is_absolute() else (ROOT / args.protocol)
    if not protocol_path.exists():
        print(f"ERROR: lock file not found: {protocol_path}", file=sys.stderr)
        return 1
    lock = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_id = lock.get("protocol_id", "unknown")

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    if len(splits) < 2:
        print(f"ERROR: need at least 2 splits, got {splits}", file=sys.stderr)
        return 1

    # Discover methods present in every split.
    if args.methods:
        methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    else:
        sets: list[set[str]] = []
        for s in splits:
            sets.append({
                p.stem.removeprefix("eval_")
                for p in (args.results_dir / s).glob("eval_*.json")
                if not p.stem.startswith("eval_diagnosis_")
            })
        methods = sorted(set.intersection(*sets)) if sets else []

    diag_by_split: dict[str, dict | None] = {}
    if args.diagnoser:
        for s in splits:
            diag_by_split[s] = load_json(
                args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            )

    if len(splits) >= 3:
        return _render_multi(
            protocol_path, protocol_id, splits, methods,
            diag_by_split, args.diagnoser,
            args.results_dir, args.reports_dir,
        )

    # Legacy dev/holdout path below.
    dev_diag = diag_by_split.get(splits[0]) if args.diagnoser else None
    hold_diag = diag_by_split.get(splits[1]) if args.diagnoser else None

    comparisons: list[dict] = []
    for m in methods:
        dev_s = sig_row(splits[0], m, args.results_dir)
        hold_s = sig_row(splits[1], m, args.results_dir)
        dev_d = diag_row(dev_diag, m)
        hold_d = diag_row(hold_diag, m)
        gaps: dict[str, float | None] = {
            "signal_recall":          gap(dev_s["signal_recall"], hold_s["signal_recall"]),
            "critical_signal_recall": gap(dev_s["critical_signal_recall"], hold_s["critical_signal_recall"]),
            "reduction":              gap(dev_s["reduction"], hold_s["reduction"]),
            "category_accuracy":      gap(dev_d.get("category_accuracy"), hold_d.get("category_accuracy")),
            "critical_mention":       gap(dev_d.get("critical_mention"), hold_d.get("critical_mention")),
            "confident_error":        gap(dev_d.get("confident_error"), hold_d.get("confident_error")),
        }
        large_gaps = [
            k for k, v in gaps.items()
            if v is not None and abs(v) >= GAP_THRESHOLD
        ]
        comparisons.append({
            "method": m,
            "dev": {**dev_s, **dev_d},
            "holdout": {**hold_s, **hold_d},
            "gaps": gaps,
            "large_gaps": large_gaps,
        })

    out_json = args.results_dir / f"dev_vs_holdout_{protocol_id.replace('-', '_')}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps({
            "protocol_id": protocol_id,
            "diagnoser":   args.diagnoser,
            "gap_threshold_abs_pp": GAP_THRESHOLD,
            "methods":     comparisons,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md: list[str] = []
    md.append(f"# Dev vs Holdout — `{protocol_id}`")
    md.append("")
    if args.diagnoser:
        md.append(f"Diagnoser: `{args.diagnoser}`")
        md.append("")
    md.append(
        f"Methods flagged with `*` below have an absolute dev↔holdout gap "
        f"≥ {int(GAP_THRESHOLD*100)} pp on at least one metric. The flag is "
        f"diagnostic, not a failure."
    )
    md.append("")

    md.append("## Signal recall")
    md.append("")
    md.append(
        "| Method | Dev Signal | Holdout Signal | Gap "
        "| Dev Critical | Holdout Critical | Gap "
        "| Dev Reduction | Holdout Reduction |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for c in comparisons:
        flag = " *" if c["large_gaps"] else ""
        md.append(
            f"| {c['method']}{flag} "
            f"| {pct(c['dev']['signal_recall'])} "
            f"| {pct(c['holdout']['signal_recall'])} "
            f"| {pct(c['gaps']['signal_recall'])} "
            f"| {pct(c['dev']['critical_signal_recall'])} "
            f"| {pct(c['holdout']['critical_signal_recall'])} "
            f"| {pct(c['gaps']['critical_signal_recall'])} "
            f"| {pct(c['dev']['reduction'])} "
            f"| {pct(c['holdout']['reduction'])} |"
        )
    md.append("")

    if args.diagnoser:
        md.append(f"## Diagnosis — `{args.diagnoser}`")
        md.append("")
        md.append(
            "_Mock diagnoser results validate the pipeline only; do not "
            "interpret these numbers as real model quality._"
        )
        md.append("")
        md.append(
            "| Method | Dev CatAcc | Holdout CatAcc | Gap "
            "| Dev CritMention | Holdout CritMention | Gap "
            "| Dev ConfErr | Holdout ConfErr |"
        )
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for c in comparisons:
            md.append(
                f"| {c['method']} "
                f"| {pct(c['dev'].get('category_accuracy'))} "
                f"| {pct(c['holdout'].get('category_accuracy'))} "
                f"| {pct(c['gaps']['category_accuracy'])} "
                f"| {pct(c['dev'].get('critical_mention'))} "
                f"| {pct(c['holdout'].get('critical_mention'))} "
                f"| {pct(c['gaps']['critical_mention'])} "
                f"| {pct(c['dev'].get('confident_error'))} "
                f"| {pct(c['holdout'].get('confident_error'))} |"
            )
        md.append("")

    md.append("## Methods with large dev/holdout gaps")
    md.append("")
    any_flagged = False
    for c in comparisons:
        if not c["large_gaps"]:
            continue
        any_flagged = True
        md.append(f"- `{c['method']}` — gap on: "
                  + ", ".join(f"`{g}`" for g in c["large_gaps"]))
    if not any_flagged:
        md.append("- None above the ≥20pp threshold.")
    md.append("")

    md.append("## Interpretation guardrails")
    md.append("")
    md.append(
        "- This comparison uses only the cases locked in "
        f"`{protocol_path.relative_to(ROOT)}`. Splits are small "
        "(5 + 5 = 10 cases), so a 20pp gap on one method may move with "
        "one case going the other way. Treat it as a flag, not a verdict."
    )
    md.append(
        "- Mock diagnosis numbers reflect a deterministic keyword "
        "heuristic; they say nothing about real model quality. Do not "
        "stop at the mock numbers."
    )
    md.append(
        "- Holdout cases were annotated before running any method on "
        "them. If future method tuning is informed by holdout per-case "
        "failures, subsequent runs must be marked `post-holdout-tuned` "
        "or a new protocol version must be created."
    )
    md.append(
        "- `category_accuracy` can jump up or down on holdout simply "
        "because the split has different category distributions; look at "
        "`critical_signal_recall` first for context-quality signal."
    )

    out_md = args.reports_dir / f"dev_vs_holdout_{protocol_id.replace('-', '_')}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
