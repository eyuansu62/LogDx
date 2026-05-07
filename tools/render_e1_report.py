"""
Finalize Experiment 1 (E1) outputs.

Produces:
    results/e1_real_fixed_debugger_cilogbench_v1_1_<diagnoser>.manifest.json
    reports/e1_real_fixed_debugger_cilogbench_v1_1_<diagnoser>.md

The manifest is the M10 manifest plus an `experiment_id` and a static
copy of the analysis-question answers the plan asks for. The report is
the M10 report extended with:

    - Section 13: a real generalization table per metric (the M10
      report only links to compare_splits)
    - Section 15: interpretation guardrails (already in M10 #14)
    - Section 16: next recommended experiment

Usage:
    python tools/render_e1_report.py --diagnoser real-debugger-v1
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E1-real-fixed-debugger-v1"


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def pct(x: float | None) -> str:
    return "N/A" if x is None else f"{x * 100:.1f}%"


def num(x: float | None, digits: int = 3) -> str:
    return "N/A" if x is None else f"{x:.{digits}f}"


def humanize_tokens(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def collect(diagnoser: str, splits: list[str]) -> dict[str, dict | None]:
    return {
        s: load_json(ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json")
            if (ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json").exists()
            else None
        for s in splits
    }


def methods_in(eval_obj: dict | None) -> dict[str, dict]:
    if not eval_obj:
        return {}
    return {m["context_method"]: m for m in eval_obj["methods"]}


def render_generalization_table(metric_label: str, metric_key: str,
                                 splits: list[str],
                                 evals: dict[str, dict | None]) -> list[str]:
    md: list[str] = []
    md.append(f"### {metric_label}")
    md.append("")
    md.append("| Method | " + " | ".join(splits) + " | Max Gap | Large Gap? |")
    md.append("|---|" + "|".join("---:" for _ in splits) + "|---:|---|")
    union: set[str] = set()
    for s in splits:
        union.update(methods_in(evals[s]).keys())
    rows = []
    for m in sorted(union):
        vals = []
        for s in splits:
            mb = methods_in(evals[s]).get(m, {})
            vals.append(mb.get(metric_key))
        non_null = [v for v in vals if v is not None]
        if len(non_null) >= 2:
            gap = round(max(non_null) - min(non_null), 4)
        else:
            gap = None
        large = gap is not None and gap >= 0.20
        rows.append((m, vals, gap, large))
    for m, vals, gap, large in rows:
        cells = [pct(v) for v in vals]
        md.append(f"| {m} | " + " | ".join(cells)
                   + f" | {pct(gap)} | {'YES' if large else '—'} |")
    md.append("")
    return md


def synthesize_analysis_q_and_a(splits: list[str],
                                 evals: dict[str, dict | None]) -> list[str]:
    """Answer each of the 10 analysis questions from the plan in 2-3 lines,
    grounded in the actual numbers from this run."""
    md: list[str] = []
    md.append("## Analysis questions answered")
    md.append("")
    md.append(
        "Each answer is grounded in the per-split metrics computed for "
        "this run. Statements are descriptive, not prescriptive — see "
        "the guardrails section."
    )
    md.append("")

    # Helpers to compare a metric across splits
    def get(metric: str, method: str, split: str) -> float | None:
        mb = methods_in(evals[split]).get(method)
        return None if mb is None else mb.get(metric)

    def cmp_text(method_a: str, method_b: str, metric: str,
                 split: str, label: str) -> str:
        a = get(metric, method_a, split); b = get(metric, method_b, split)
        if a is None or b is None:
            return (f"On {split}, the {metric} comparison between "
                    f"`{method_a}` and `{method_b}` is unavailable.")
        diff = a - b
        verdict = "higher" if diff > 0 else "lower" if diff < 0 else "tied"
        return (f"On {split}, `{method_a}` had {label} {pct(a)} vs "
                f"`{method_b}` {pct(b)} ({verdict} by {pct(abs(diff))}).")

    # 1. Does raw context outperform compressed context?
    md.append("**1. Does raw context outperform compressed context?**")
    md.append("")
    for s in splits:
        raw_sv = get("diagnosis_score_v1", "raw", s) or 0
        ranks = sorted(
            ((m["context_method"], m.get("diagnosis_score_v1") or 0)
             for m in (evals[s] or {}).get("methods", [])),
            key=lambda kv: -kv[1])
        winner = ranks[0][0] if ranks else "?"
        md.append(f"- {s}: raw `score_v1` = {num(raw_sv)}; top method "
                   f"this split is `{winner}`.")
    md.append("")

    # 2. Does raw context ever hurt due to length/noise?
    md.append("**2. Does raw context ever hurt due to length/noise?**")
    md.append("")
    for s in splits:
        succ = get("diagnosis_success_rate", "raw", s)
        abst = get("abstention_rate", "raw", s)
        cerr = get("confident_error_rate", "raw", s)
        md.append(f"- {s}: raw success={pct(succ)}, abstention={pct(abst)}, "
                   f"confident_error={pct(cerr)}.")
    md.append("")

    # 3. Does grep's high signal recall translate into better diagnosis quality?
    md.append("**3. Does grep's signal recall translate into better diagnosis?**")
    md.append("")
    for s in splits:
        # signal_recall lives in eval_<method>.json (signal recall eval)
        sr_p = ROOT / "results" / s / "eval_grep.json"
        sr = load_json(sr_p).get("macro_signal_recall") if sr_p.exists() else None
        cat = get("macro_category_accuracy", "grep", s)
        crit = get("macro_critical_signal_mention_recall", "grep", s)
        md.append(f"- {s}: grep signal_recall={pct(sr)} → "
                   f"category_accuracy={pct(cat)}, critical_mention={pct(crit)}.")
    md.append("")

    # 4. Does rtk-err-cat's lower stress recall reduce diagnosis quality?
    md.append("**4. Does rtk-err-cat's lower holdout/stress signal recall "
               "reduce diagnosis quality?**")
    md.append("")
    for s in splits:
        sr_p = ROOT / "results" / s / "eval_rtk-err-cat.json"
        sr = load_json(sr_p).get("macro_signal_recall") if sr_p.exists() else None
        cat = get("macro_category_accuracy", "rtk-err-cat", s)
        crit = get("macro_critical_signal_mention_recall", "rtk-err-cat", s)
        sv = get("diagnosis_score_v1", "rtk-err-cat", s)
        md.append(f"- {s}: rtk-err-cat signal_recall={pct(sr)} → "
                   f"cat={pct(cat)}, crit_mention={pct(crit)}, "
                   f"score_v1={num(sv)}.")
    md.append("")

    # 5. rtk-log abstention / wrong / unsupported?
    md.append("**5. Does rtk-log cause abstention, wrong answers, or "
               "unsupported evidence?**")
    md.append("")
    for s in splits:
        cat = get("macro_category_accuracy", "rtk-log", s)
        crit = get("macro_critical_signal_mention_recall", "rtk-log", s)
        cerr = get("confident_error_rate", "rtk-log", s)
        abst = get("abstention_rate", "rtk-log", s)
        veq = get("macro_valid_evidence_quote_rate", "rtk-log", s)
        md.append(f"- {s}: cat={pct(cat)} (low → wrong), "
                   f"abstention={pct(abst)}, confident_error={pct(cerr)}, "
                   f"valid_evidence_quote_rate={pct(veq)}.")
    md.append("")

    # 6. Tail-200 short-log bias
    md.append("**6. Does tail-200's strong holdout/stress signal recall "
               "reflect short-log bias?**")
    md.append("")
    for s in splits:
        sr_p = ROOT / "results" / s / "eval_tail.json"
        sr = load_json(sr_p).get("macro_signal_recall") if sr_p.exists() else None
        sv = get("diagnosis_score_v1", "tail", s)
        cat = get("macro_category_accuracy", "tail", s)
        md.append(f"- {s}: tail signal_recall={pct(sr)}, "
                   f"category_accuracy={pct(cat)}, score_v1={num(sv)}.")
    md.append("")

    # 7. Lowest confident-error rate
    md.append("**7. Which method has the lowest confident-error rate?**")
    md.append("")
    for s in splits:
        ranks = sorted(
            ((m["context_method"], m.get("confident_error_rate") or 0)
             for m in (evals[s] or {}).get("methods", [])),
            key=lambda kv: kv[1])
        if ranks:
            md.append(f"- {s}: {', '.join(f'`{m}`={pct(v)}' for m, v in ranks[:3])}")
    md.append("")

    # 8. Highest abstention rate
    md.append("**8. Which method has the highest abstention rate?**")
    md.append("")
    for s in splits:
        ranks = sorted(
            ((m["context_method"], m.get("abstention_rate") or 0)
             for m in (evals[s] or {}).get("methods", [])),
            key=lambda kv: -kv[1])
        if ranks:
            md.append(f"- {s}: {', '.join(f'`{m}`={pct(v)}' for m, v in ranks[:3])}")
    md.append("")

    # 9. Hard cases for all methods
    md.append("**9. Which cases are hard for all methods?**")
    md.append("")
    for s in splits:
        ev = evals[s] or {"methods": []}
        case_to_methods: dict[str, list[dict]] = {}
        for mb in ev.get("methods", []):
            for c in mb.get("cases", []):
                case_to_methods.setdefault(c["case_id"], []).append(c)
        hard = []
        for cid, rows in case_to_methods.items():
            cats = [c.get("category_accuracy") for c in rows
                     if c.get("category_accuracy") is not None]
            if cats and max(cats) == 0.0:
                hard.append(cid)
        md.append(f"- {s}: hard for every method → "
                   + (", ".join(f"`{c}`" for c in sorted(hard)) if hard else "none"))
    md.append("")

    # 10. Most often-absent required signals
    md.append("**10. Which required signals are most often missing?**")
    md.append("")
    from collections import Counter
    for s in splits:
        ev = evals[s] or {"methods": []}
        c = Counter()
        for mb in ev.get("methods", []):
            for case in mb.get("cases", []):
                for ms in (case.get("missed_signals") or []):
                    c[ms.get("type", "?")] += 1
        if c:
            top = ", ".join(f"`{t}`×{n}" for t, n in c.most_common(4))
            md.append(f"- {s}: top miss types → {top}")
    md.append("")
    return md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Finalize E1 manifest + report.")
    ap.add_argument("--diagnoser", required=True)
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.1.lock.json")
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    diagnoser = args.diagnoser
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    if not args.protocol.exists():
        print(f"ERROR: {args.protocol} missing.", file=sys.stderr)
        return 1

    # Reuse the M10 manifest + report; copy/extend them for E1.
    m10_manifest = args.results_dir / f"{load_json(args.protocol).get('protocol_id','unknown')}_real_debugger_{diagnoser}.manifest.json"
    m10_report = args.reports_dir / f"{load_json(args.protocol).get('protocol_id','unknown')}_real_debugger_{diagnoser}.md"
    if not m10_manifest.exists() or not m10_report.exists():
        print(f"ERROR: M10 outputs missing — run "
              f"tools/run_protocol_diagnosis_eval.py first.", file=sys.stderr)
        return 1

    base_manifest = load_json(m10_manifest)
    e1_manifest = dict(base_manifest)
    e1_manifest["experiment_id"] = EXPERIMENT_ID
    e1_manifest["finalized_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    e1_manifest_path = args.results_dir / f"e1_real_fixed_debugger_cilogbench_v1_1_{diagnoser}.manifest.json"
    e1_manifest_path.write_text(
        json.dumps(e1_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    evals = collect(diagnoser, splits)

    # Build extended report.
    body = m10_report.read_text(encoding="utf-8")
    # Replace the M10 title line with the E1 one
    body_lines = body.splitlines()
    if body_lines and body_lines[0].startswith("# CILogBench M10"):
        body_lines[0] = (
            f"# CILogBench {EXPERIMENT_ID} — `{diagnoser}` on `cilogbench-v1.1`"
        )
    md = body_lines

    md.append("")
    md.append("---")
    md.append("")
    md.append("## Generalization tables (per metric)")
    md.append("")
    md.append(
        "Per the E1 plan, these tables make the dev/holdout/stress gap "
        "explicit per metric. `Large Gap?` flags absolute spread "
        "≥ 20 percentage points across the three splits."
    )
    md.append("")
    for label, key in [
        ("Diagnosis Score v1",          "diagnosis_score_v1"),
        ("Category Accuracy",           "macro_category_accuracy"),
        ("Critical Signal Mention",     "macro_critical_signal_mention_recall"),
        ("Confident Error Rate",        "confident_error_rate"),
        ("Abstention Rate",             "abstention_rate"),
    ]:
        md.extend(render_generalization_table(label, key, splits, evals))

    md.extend(synthesize_analysis_q_and_a(splits, evals))

    md.append("---")
    md.append("")
    md.append("## E1 interpretation guardrails (recap)")
    md.append("")
    md.append(
        "- This is one model (Claude Haiku 4.5 via the Claude Code CLI), "
        "one prompt (`debugger_v1`, SHA pinned in `cilogbench-v1.1`), "
        "and 16 cases. Numbers establish a baseline, not a winner."
    )
    md.append(
        "- E1 supports statements like \"under cilogbench-v1.1, this "
        "diagnoser had higher `score_v1` on stress/grep than on "
        "stress/rtk-log\". It does NOT support \"method X is the best "
        "CI debugging strategy\"."
    )
    md.append(
        "- `diagnosis_success_rate` < 1.0 happens when the CLI itself "
        "errors out (e.g. on the largest log). Those rows are "
        "labeled `provider_error` in metadata; they are not silent "
        "abstentions."
    )
    md.append(
        "- The deterministic evaluator can undercount valid "
        "paraphrases. Cross-check with M11 human review before "
        "publishing claims."
    )
    md.append("")

    md.append("## Next recommended experiment")
    md.append("")
    md.append(
        "Per the plan, the recommended next step is **E2: human review "
        "of E1 diagnoses**. Build a blinded batch from the E1 outputs "
        "with `tools/build_human_review_set.py`, score 5 holdout cases × "
        "3-4 context methods, and check whether human "
        "`overall_usefulness` correlates with `diagnosis_score_v1` on "
        "this real-model run before adding more variables (real "
        "summarizer, MCP/agent baselines)."
    )
    md.append("")
    md.append(
        "If correlation is strong, E3 (real LLM summary context with the "
        "same debugger) becomes a clean follow-up that adds exactly one "
        "new variable. If correlation is weak, fix the metric or "
        "ground-truth annotations before adding any new variable."
    )
    md.append("")

    e1_report_path = args.reports_dir / f"e1_real_fixed_debugger_cilogbench_v1_1_{diagnoser}.md"
    e1_report_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    e1_manifest["report_path"] = str(e1_report_path.relative_to(ROOT))
    e1_manifest_path.write_text(
        json.dumps(e1_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"E1 manifest → {e1_manifest_path.relative_to(ROOT)}")
    print(f"E1 report   → {e1_report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
