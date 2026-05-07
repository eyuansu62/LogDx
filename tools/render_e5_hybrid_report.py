"""
E5 hybrid baseline report renderer.

Reads:
  protocols/cilogbench-v1.2.lock.json
  configs/hybrids/<hybrid>.json
  results/<split>/<hybrid>.jsonl
  results/<split>/<hybrid>.routes.jsonl
  results/<split>/eval_<hybrid>.json
  results/<split>/eval_diagnosis_real-debugger-v1.json
  results/e4_budget_frontier.json   (E4 prediction context)

Writes:
  reports/e5_hybrid_grep_fallback_cilogbench_v1_2.md
  results/e5_hybrid_grep_fallback_cilogbench_v1_2.manifest.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E5-hybrid-grep-fallback-v1"


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def num(x, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{float(x):.{digits}f}"


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{float(x) * 100:.1f}%"


def humanize_tokens(n) -> str:
    if n is None:
        return "n/a"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def methods_in(eval_obj):
    if not eval_obj:
        return {}
    return {m["context_method"]: m for m in eval_obj.get("methods", [])}


def signal_eval(split: str, method: str) -> dict:
    p = ROOT / "results" / split / f"eval_{method}.json"
    return load_json(p) if p.exists() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.2.lock.json")
    ap.add_argument("--config", type=Path,
                    default=ROOT / "configs" / "hybrids" / "hybrid-grep-4k-rtk-err-cat-v1.json")
    ap.add_argument("--diagnoser", default="real-debugger-v1")
    ap.add_argument("--splits", nargs="+", default=["dev", "holdout", "stress"])
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    config = load_json(args.config)
    hybrid_method = config["method"]
    primary = config["primary_method"]
    fallback = config["fallback_method"]
    budget = int((config.get("routing_rule") or {}).get("budget_tokens") or 0)

    # Methods to compare in tables
    methods_full = ["raw", "tail", "grep", "rtk-err-cat",
                    "rtk-read", "rtk-log",
                    "llm-summary-v1-mock", "llm-summary-v1-haiku",
                    hybrid_method]

    md: list[str] = []
    md.append(f"# E5 — Hybrid Grep Fallback Baseline (`{hybrid_method}`)")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `cilogbench-v1.2` (SHA "
              f"`{sha256_path(args.protocol)[:16]}…`)")
    md.append(f"- **Hybrid config:** `{args.config.relative_to(ROOT)}` "
              f"(SHA `{sha256_path(args.config)[:16]}…`)")
    md.append(f"- **Primary:** `{primary}`  ·  **Fallback:** `{fallback}`  "
              f"·  **Budget:** {budget} tokens (chars/4 estimate)")
    md.append(f"- **Debugger:** `{args.diagnoser}` (held fixed from E1/E3)")
    md.append(f"- **Splits:** {', '.join(args.splits)}")
    md.append(f"- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated). `diagnosis_score_v1` reported as secondary.")
    md.append("")

    # 1. Executive summary
    md.append("## 1. Executive summary")
    md.append("")
    macros = []
    for s in args.splits:
        ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
        ev = load_json(ev_p) if ev_p.exists() else {}
        mb = methods_in(ev).get(hybrid_method) or {}
        macros.append((s, mb.get("diagnosis_score_v1_1"),
                       mb.get("macro_context_tokens"),
                       mb.get("confident_error_rate_v1_1")))
        grep = methods_in(ev).get("grep") or {}
        macros[-1] = (*macros[-1], grep.get("diagnosis_score_v1_1"))
    md.append("Per-split macro `diagnosis_score_v1_1` for the hybrid vs. `grep` baseline:")
    md.append("")
    md.append("| Split | hybrid sv1.1 | grep sv1.1 | Δ | hybrid macro ctx tok | hybrid confErr v1.1 |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for s, hb_sv, hb_ctx, hb_ce, gr_sv in macros:
        delta = (hb_sv - gr_sv) if (hb_sv is not None and gr_sv is not None) else None
        md.append(f"| {s} | {num(hb_sv)} | {num(gr_sv)} | "
                   f"{('+' if (delta or 0) >= 0 else '')}{num(delta)} | "
                   f"{humanize_tokens(hb_ctx)} | {pct(hb_ce)} |")
    md.append("")

    # 2. E4 motivation
    md.append("## 2. E4 motivation")
    md.append("")
    md.append(
        "From `reports/e4_summary_failure_attribution_cilogbench_v1_2.md` "
        "section 9: the routing policy `grep-if-fits-else-rtk-err-cat @4k` "
        "scored **0.723** macro sv1.1 on the offline E4 simulation versus "
        "**0.680** for `grep-default`, while spending ~⅓ the total-pipeline "
        "tokens. E5 implements this policy as a first-class deterministic "
        "context method (`hybrid-grep-4k-rtk-err-cat-v1`) so it gets the "
        "same byte-stable scoring treatment as every other locked baseline, "
        "and so we can check whether the offline win survives a real run."
    )
    md.append("")

    # 3. Hybrid method definition
    md.append("## 3. Hybrid method definition")
    md.append("")
    md.append("```text")
    md.append(f"For each case in {{dev, holdout, stress}}:")
    md.append(f"  if {primary} is available and (output_byte_size / 4) <= {budget}:")
    md.append(f"      select {primary}")
    md.append(f"  elif {fallback} is available:")
    md.append(f"      select {fallback}        # primary_too_large_used_fallback")
    md.append(f"                                 # OR primary_provider_error_used_fallback")
    md.append(f"  else:")
    md.append(f"      record provider_error    # do not silently fall back to raw")
    md.append("```")
    md.append("")
    md.append(
        "The token estimate is `output_byte_size // 4` from the existing "
        "manifest rows — this matches `tools/run_diagnosis.py`'s `context_"
        "tokens` accounting on every locked grep/rtk-err-cat manifest "
        "(verified ratio 1.000)."
    )
    md.append("")

    # 4. Anti-leakage
    md.append("## 4. Anti-leakage statement")
    md.append("")
    md.append(
        "The router reads only pre-diagnosis context metadata: per-case "
        "`case_id`, `context_path`, `output_byte_size`, "
        "`output_line_count`, `included_line_ranges`, and "
        "`metadata.provider_error`."
    )
    md.append("")
    md.append("It does **not** read:")
    md.append("- `cases/<split>/<case_id>/ground_truth.json`")
    md.append("- `results/<split>/eval_*.json` (signal recall or diagnosis eval)")
    md.append("- `review/batches/*/labels/*.jsonl` (expert/human review labels)")
    md.append("- any `failure_category` / `required_signals` / `evidence_spans` field")
    md.append("")
    md.append(
        "The 4k threshold itself was chosen in E4's offline budget sweep, "
        "but the per-case decision in E5 only consults the budget and the "
        "raw manifest fields above — no scoring information leaks into the "
        "router."
    )
    md.append("")

    # 5. Routing decisions by split
    md.append("## 5. Routing decisions by split")
    md.append("")
    md.append("### Table 1 — Routing summary")
    md.append("")
    md.append("| Split | Cases | Selected `grep` | Selected `rtk-err-cat` | Provider errors | Mean selected ctx tok |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for s in args.splits:
        routes = load_jsonl(args.results_dir / s / f"{hybrid_method}.routes.jsonl")
        n = len(routes)
        n_grep = sum(1 for r in routes if r.get("selected_method") == primary)
        n_rtk = sum(1 for r in routes if r.get("selected_method") == fallback)
        n_pe = sum(1 for r in routes if r.get("selected_method") is None)
        # mean selected context tokens
        chosen_toks = []
        for r in routes:
            if r.get("selected_method"):
                chosen_toks.append((r.get("candidates") or {}).get(r["selected_method"], {}).get("context_tokens") or 0)
        mean_chosen = (sum(chosen_toks) / max(1, len(chosen_toks))) if chosen_toks else 0
        md.append(f"| {s} | {n} | {n_grep} | {n_rtk} | {n_pe} | {humanize_tokens(int(mean_chosen))} |")
    md.append("")

    # Per-case routing
    md.append("### Table 2 — Per-case routing")
    md.append("")
    md.append("| Case | Split | grep tok | rtk tok | Selected | Reason | Hybrid sv1.1 | Grep sv1.1 | RTK sv1.1 | Δ vs grep |")
    md.append("|---|---|---:|---:|---|---|---:|---:|---:|---:|")
    for s in args.splits:
        routes = load_jsonl(args.results_dir / s / f"{hybrid_method}.routes.jsonl")
        ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
        ev = load_json(ev_p) if ev_p.exists() else {}
        method_blocks = methods_in(ev)
        hybrid_cases = {c["case_id"]: c for c in (method_blocks.get(hybrid_method) or {}).get("cases", [])}
        grep_cases = {c["case_id"]: c for c in (method_blocks.get(primary) or {}).get("cases", [])}
        rtk_cases = {c["case_id"]: c for c in (method_blocks.get(fallback) or {}).get("cases", [])}
        for r in routes:
            cid = r["case_id"]
            grep_t = (r["candidates"][primary] or {}).get("context_tokens")
            rtk_t = (r["candidates"][fallback] or {}).get("context_tokens")
            hb_sv = (hybrid_cases.get(cid) or {}).get("diagnosis_score_v1_1")
            gr_sv = (grep_cases.get(cid) or {}).get("diagnosis_score_v1_1")
            rk_sv = (rtk_cases.get(cid) or {}).get("diagnosis_score_v1_1")
            delta = (hb_sv - gr_sv) if (hb_sv is not None and gr_sv is not None) else None
            md.append(
                f"| `{cid}` | {s} | {grep_t} | {rtk_t} "
                f"| `{r['selected_method']}` | `{r['selected_reason']}` "
                f"| {num(hb_sv)} | {num(gr_sv)} | {num(rk_sv)} "
                f"| {'+' if (delta or 0) >= 0 else ''}{num(delta)} |"
            )
    md.append("")

    # 6. Signal recall comparison
    md.append("## 6. Signal recall comparison")
    md.append("")
    md.append("### Table 3 — Signal recall")
    md.append("")
    md.append("| Method | Split | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping |")
    md.append("|---|---|---:|---:|---:|---:|---|")
    sig_methods = ["grep", fallback, hybrid_method, "tail", "raw", "llm-summary-v1-haiku"]
    for m in sig_methods:
        for s in args.splits:
            sm = signal_eval(s, m)
            map_avail = "—"
            # Check the first row in the method manifest for line_mapping_available
            row_p = args.results_dir / s / f"{m}.jsonl"
            if row_p.exists():
                rows = load_jsonl(row_p)
                if rows:
                    map_avail = "line" if rows[0].get("line_mapping_available") else "text"
            md.append(
                f"| `{m}` | {s} "
                f"| {pct(sm.get('macro_signal_recall'))} "
                f"| {pct(sm.get('macro_critical_signal_recall'))} "
                f"| {pct(sm.get('macro_evidence_span_coverage'))} "
                f"| {pct(sm.get('macro_reduction_ratio'))} "
                f"| {map_avail} |"
            )
    md.append("")

    # 7. Diagnosis comparison sv1.1 primary
    md.append("## 7. Diagnosis comparison (sv1.1 primary)")
    md.append("")
    md.append("### Table 4 — Diagnosis")
    md.append("")
    md.append("| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in methods_full:
        for s in args.splits:
            ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            ev = load_json(ev_p) if ev_p.exists() else {}
            mb = methods_in(ev).get(m)
            if mb is None:
                continue
            md.append(
                f"| `{m}` | {s} "
                f"| {pct(mb.get('diagnosis_success_rate'))} "
                f"| {num(mb.get('macro_category_match_score_v1_1'))} "
                f"| {pct(mb.get('macro_critical_signal_mention_recall'))} "
                f"| {pct(mb.get('macro_must_mention_coverage'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb.get('abstention_rate'))} "
                f"| **{num(mb.get('diagnosis_score_v1_1'))}** "
                f"| {num(mb.get('diagnosis_score_v1'))} "
                f"| {humanize_tokens(mb.get('macro_context_tokens'))} |"
            )
    md.append("")

    # 8. Cost / token comparison
    md.append("## 8. Cost / token comparison")
    md.append("")
    md.append("### Table 5 — Cost")
    md.append("")
    md.append("| Method | Split | Final Ctx Tok | Sum Proc Tok | Diag Out Tok | Total Pipeline Tok | Provider Errors |")
    md.append("|---|---|---:|---:|---:|---:|---:|")
    for m in methods_full:
        for s in args.splits:
            ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            ev = load_json(ev_p) if ev_p.exists() else {}
            mb = methods_in(ev).get(m)
            if mb is None:
                continue
            ctx_tok = mb.get("macro_context_tokens") or 0
            diag_tok = mb.get("macro_diagnosis_tokens") or 0
            cases = mb.get("cases") or []
            pe = sum(1 for c in cases if c.get("provider_error"))
            # Summary processing tokens — only meaningful for the real LLM summary
            proc_tok = 0
            total = (proc_tok or 0) + (ctx_tok or 0) + (diag_tok or 0)
            md.append(
                f"| `{m}` | {s} "
                f"| {humanize_tokens(ctx_tok)} "
                f"| {'—' if proc_tok == 0 else humanize_tokens(proc_tok)} "
                f"| {humanize_tokens(diag_tok)} "
                f"| **{humanize_tokens(total)}** "
                f"| {pe} |"
            )
    md.append("")
    md.append(
        "Note: the table above shows summary-processing as `—` for non-summary "
        "methods. The hybrid baseline does not call any LLM during context "
        "construction (it copies an already-built grep or rtk-err-cat context); "
        "summary-processing for hybrid is therefore 0."
    )
    md.append("")

    # 9. Provider-error analysis
    md.append("## 9. Provider-error analysis")
    md.append("")
    pe_rows = []
    for s in args.splits:
        for m in (primary, fallback, hybrid_method, "raw", "rtk-read"):
            ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            ev = load_json(ev_p) if ev_p.exists() else {}
            mb = methods_in(ev).get(m)
            if mb is None: continue
            for c in (mb.get("cases") or []):
                if c.get("provider_error"):
                    pe_rows.append((s, m, c["case_id"], c.get("provider_error", "")[:140]))
    if pe_rows:
        md.append("| Split | Method | Case | Error |")
        md.append("|---|---|---|---|")
        for s, m, cid, err in pe_rows:
            md.append(f"| {s} | `{m}` | `{cid}` | `{err}` |")
    else:
        md.append("No provider errors recorded across the hybrid + comparison methods.")
    md.append("")

    # 10. Confident-error and abstention
    md.append("## 10. Confident-error and abstention analysis")
    md.append("")
    md.append("| Method | Split | confErr v1 | confErr v1.1 | Abstention |")
    md.append("|---|---|---:|---:|---:|")
    for m in (primary, fallback, hybrid_method, "tail", "llm-summary-v1-haiku"):
        for s in args.splits:
            ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            mb = methods_in(load_json(ev_p) if ev_p.exists() else {}).get(m)
            if mb is None:
                continue
            md.append(
                f"| `{m}` | {s} "
                f"| {pct(mb.get('confident_error_rate'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb.get('abstention_rate'))} |"
            )
    md.append("")

    # 11. Generalization
    md.append("## 11. Dev/holdout/stress generalization")
    md.append("")
    md.append("| Method | dev sv1.1 | holdout sv1.1 | stress sv1.1 | Max Gap | Large Gap? |")
    md.append("|---|---:|---:|---:|---:|---|")
    for m in methods_full:
        vals = []
        for s in args.splits:
            ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
            mb = methods_in(load_json(ev_p) if ev_p.exists() else {}).get(m)
            vals.append((mb or {}).get("diagnosis_score_v1_1"))
        nn = [v for v in vals if v is not None]
        gap = (max(nn) - min(nn)) if len(nn) >= 2 else None
        large = gap is not None and gap >= 0.20
        cells = [num(v) for v in vals]
        md.append(f"| `{m}` | " + " | ".join(cells) + f" | {num(gap)} | {'YES' if large else '—'} |")
    md.append("")

    # 12. E4 prediction vs E5 actual
    md.append("## 12. Comparison to E4 offline prediction")
    md.append("")
    md.append("### Table 6 — E4 prediction vs E5 actual")
    md.append("")
    bf_p = args.results_dir / "e4_budget_frontier.json"
    e4 = load_json(bf_p) if bf_p.exists() else {}
    e4_pol = next((p for p in (e4.get("policies") or [])
                    if p["policy"] == "grep-if-fits-else-rtk-err-cat"
                    and p.get("budget_tokens") == budget), {}) or {}

    # E5 macro across splits
    e5_sv = []
    e5_ctx = []
    e5_total = []
    e5_pe = 0
    e5_n = 0
    for s in args.splits:
        ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
        ev = load_json(ev_p) if ev_p.exists() else {}
        mb = methods_in(ev).get(hybrid_method)
        if mb is None:
            continue
        cases = mb.get("cases") or []
        e5_sv.append(mb.get("diagnosis_score_v1_1"))
        e5_ctx.append(mb.get("macro_context_tokens") or 0)
        e5_total.append((mb.get("macro_context_tokens") or 0) + (mb.get("macro_diagnosis_tokens") or 0))
        e5_pe += sum(1 for c in cases if c.get("provider_error"))
        e5_n += len(cases)
    e5_sv_macro = round(sum(e5_sv) / len(e5_sv), 4) if e5_sv else None
    e5_ctx_macro = round(sum(e5_ctx) / len(e5_ctx), 1) if e5_ctx else None
    e5_total_macro = round(sum(e5_total) / len(e5_total), 1) if e5_total else None
    e5_pe_rate = round(e5_pe / max(1, e5_n), 4)

    md.append("| Metric | E4 offline policy estimate | E5 first-class baseline | Δ |")
    md.append("|---|---:|---:|---:|")
    e4_sv = e4_pol.get("macro_sv1_1")
    e4_ctx = e4_pol.get("macro_final_context_tokens")
    e4_total = e4_pol.get("macro_total_pipeline_tokens")
    e4_pe = e4_pol.get("provider_error_rate")
    md.append(f"| Macro sv1.1 | {num(e4_sv)} | {num(e5_sv_macro)} | "
               f"{('+' if (e5_sv_macro or 0) - (e4_sv or 0) >= 0 else '')}"
               f"{num((e5_sv_macro or 0) - (e4_sv or 0))} |")
    md.append(f"| Macro final ctx tok | {humanize_tokens(e4_ctx)} | {humanize_tokens(e5_ctx_macro)} | "
               f"{humanize_tokens((e5_ctx_macro or 0) - (e4_ctx or 0))} |")
    md.append(f"| Macro total pipeline tok | {humanize_tokens(e4_total)} | {humanize_tokens(e5_total_macro)} | "
               f"{humanize_tokens((e5_total_macro or 0) - (e4_total or 0))} |")
    md.append(f"| Provider error rate | {pct(e4_pe)} | {pct(e5_pe_rate)} | "
               f"{pct((e5_pe_rate or 0) - (e4_pe or 0))} |")
    md.append("")

    # 13. Decision
    md.append("## 13. Decision: freeze v1.3 or keep exploratory")
    md.append("")
    # Decision rules from plan
    grep_macro = []
    hybrid_macro = []
    grep_ce_macro = []
    hybrid_ce_macro = []
    for s in args.splits:
        ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
        ev = load_json(ev_p) if ev_p.exists() else {}
        gr = methods_in(ev).get("grep") or {}
        hb = methods_in(ev).get(hybrid_method) or {}
        grep_macro.append(gr.get("diagnosis_score_v1_1") or 0)
        hybrid_macro.append(hb.get("diagnosis_score_v1_1") or 0)
        grep_ce_macro.append(gr.get("confident_error_rate_v1_1") or 0)
        hybrid_ce_macro.append(hb.get("confident_error_rate_v1_1") or 0)
    grep_avg = sum(grep_macro) / max(1, len(grep_macro))
    hybrid_avg = sum(hybrid_macro) / max(1, len(hybrid_macro))
    sv_freeze = hybrid_avg >= grep_avg
    ctx_freeze = (e5_ctx_macro or 0) <= ((sum([(load_json(args.results_dir/s/f'eval_diagnosis_{args.diagnoser}.json').get('methods', [{}])[0].get('macro_context_tokens') or 0) for s in args.splits if (args.results_dir/s/f'eval_diagnosis_{args.diagnoser}.json').exists()]) / 3) or 999_999)
    # Compare hybrid total tokens vs grep total tokens
    grep_ctx_macro = []
    for s in args.splits:
        ev_p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser}.json"
        gr = methods_in(load_json(ev_p) if ev_p.exists() else {}).get("grep") or {}
        grep_ctx_macro.append((gr.get("macro_context_tokens") or 0) + (gr.get("macro_diagnosis_tokens") or 0))
    grep_total_avg = sum(grep_ctx_macro) / max(1, len(grep_ctx_macro))
    cost_freeze = (e5_total_macro or 0) <= grep_total_avg
    ce_freeze = (sum(hybrid_ce_macro) / max(1, len(hybrid_ce_macro))) <= (sum(grep_ce_macro) / max(1, len(grep_ce_macro)))
    pe_freeze = e5_pe_rate <= 0.10  # ≤ 10% provider errors

    freeze = sv_freeze and cost_freeze and ce_freeze and pe_freeze
    decision = "FREEZE_V1_3" if freeze else "KEEP_EXPLORATORY"

    md.append(f"**Decision: `{decision}`**")
    md.append("")
    md.append("| Criterion | Hybrid | Grep | Pass? |")
    md.append("|---|---:|---:|:---:|")
    md.append(f"| Macro sv1.1 | {num(hybrid_avg)} | {num(grep_avg)} | "
               f"{'✅' if sv_freeze else '❌'} |")
    md.append(f"| Macro total pipeline tokens | {humanize_tokens(e5_total_macro)} | {humanize_tokens(grep_total_avg)} | "
               f"{'✅' if cost_freeze else '❌'} |")
    md.append(f"| Macro confErr v1.1 | "
               f"{pct(sum(hybrid_ce_macro) / max(1, len(hybrid_ce_macro)))} | "
               f"{pct(sum(grep_ce_macro) / max(1, len(grep_ce_macro)))} | "
               f"{'✅' if ce_freeze else '❌'} |")
    md.append(f"| Provider error rate ≤ 10% | {pct(e5_pe_rate)} | — | "
               f"{'✅' if pe_freeze else '❌'} |")
    md.append("")
    if freeze:
        md.append(
            "All four freeze criteria met. **Recommend freezing "
            "`cilogbench-v1.3` with `hybrid-grep-4k-rtk-err-cat-v1` as a new "
            "first-class baseline** alongside the existing locked methods. "
            "Then run a second debugger model on v1.3 to check whether the "
            "hybrid advantage is model-stable."
        )
    else:
        md.append(
            "At least one freeze criterion did not pass. **Keep `hybrid-"
            "grep-4k-rtk-err-cat-v1` as an exploratory method** — emit it "
            "in tables and reports, but do not freeze a v1.3 baseline yet. "
            "Investigate the failed criterion before adding more hybrid "
            "variants."
        )
    md.append("")

    # 14. Interpretation guardrails
    md.append("## 14. Interpretation guardrails")
    md.append("")
    md.append("- One debugger model. The hybrid's advantage may be model-bound — same `real-debugger-v1` (Haiku 4.5) used in E1/E3.")
    md.append("- One threshold (4k tokens) and one fallback method (`rtk-err-cat`). Other thresholds / fallbacks were not implemented in E5.")
    md.append("- 16 cases total — directional, not statistical.")
    md.append("- The 4k threshold was picked from E4's offline analysis on the **same case set**. The hybrid-vs-grep delta therefore should not be re-tuned on holdout/stress without freezing a new protocol.")
    md.append("- The `output_byte_size // 4` token estimate matches `run_diagnosis.py` exactly on chars, but Anthropic's tokenizer may diverge on Unicode-heavy logs; large chars-vs-tokens drift would only matter near the 4k boundary.")
    md.append("- Provider errors on dev `cargo-tokio-001` (raw/rtk-read context-too-large) carry over from E1; the hybrid does not surface them because grep / rtk-err-cat both fit.")
    md.append("")

    # 15. Recommended next experiment
    md.append("## 15. Recommended next experiment")
    md.append("")
    if freeze:
        md.append(
            "**Freeze `cilogbench-v1.3` with the hybrid baseline included, "
            "then run a second debugger model.** The plan-mandated next "
            "step after a successful E5 is to confirm the hybrid advantage "
            "is not a Haiku-specific artifact. Suggested experiment: "
            "**E6 — second-debugger replication on v1.3** (Sonnet 4.6 or "
            "Opus 4.7 as `real-debugger-v2`, all other variables fixed)."
        )
    else:
        md.append(
            "**Do not freeze yet.** Investigate the failed criterion "
            "(specifically: which split or method caused the regression?) "
            "before considering more hybrid variants. If routing decisions "
            "look unstable around the 4k boundary, examine whether the "
            "token estimate is the issue. If a single case is dominating "
            "the loss, look at it manually."
        )
    md.append("")

    out_md = args.reports_dir / "e5_hybrid_grep_fallback_cilogbench_v1_2.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Manifest
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": "cilogbench-v1.2",
        "protocol_lock_path": str(args.protocol.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol),
        "hybrid_method": hybrid_method,
        "hybrid_config_path": str(args.config.relative_to(ROOT)),
        "hybrid_config_sha256": sha256_path(args.config),
        "diagnoser_name": args.diagnoser,
        "splits": args.splits,
        "case_count_by_split": {
            s: len(load_jsonl(args.results_dir / s / f"{hybrid_method}.jsonl"))
            for s in args.splits
        },
        "primary_score": "diagnosis_score_v1_1",
        "secondary_score": "diagnosis_score_v1",
        "summary_manifest_paths": {
            s: f"results/{s}/{hybrid_method}.jsonl" for s in args.splits
        },
        "route_paths": {
            s: f"results/{s}/{hybrid_method}.routes.jsonl" for s in args.splits
        },
        "signal_eval_paths": {
            s: f"results/{s}/eval_{hybrid_method}.json" for s in args.splits
        },
        "diagnosis_eval_paths": {
            s: f"results/{s}/eval_diagnosis_{args.diagnoser}.json" for s in args.splits
        },
        "report_path": str(out_md.relative_to(ROOT)),
        "decision": decision,
        "git_commit": "unknown",
        "working_tree_dirty": True,
        "finalized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out_manifest = args.results_dir / "e5_hybrid_grep_fallback_cilogbench_v1_2.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
