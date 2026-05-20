"""
Finalize Experiment 3 (E3) outputs.

Produces:
    results/e3_real_llm_summary_cilogbench_v1_2_<summarizer_slug>.manifest.json
    reports/e3_real_llm_summary_cilogbench_v1_2_<summarizer_slug>.md

Reads:
    protocols/legacy/cilogbench-v1.2.lock.json
    configs/summarizers/<summarizer_slug>.json
    configs/diagnosers/real-debugger-v1.json
    prompts/llm_summary_v1_map.md
    prompts/llm_summary_v1_reduce.md
    prompts/debugger_v1.md
    results/<split>/llm-summary-v1-<summarizer_slug>.jsonl
    results/<split>/eval_llm-summary-v1-<summarizer_slug>.json (signal recall)
    results/<split>/eval_diagnosis_real-debugger-v1.json (diagnosis eval, sv1+sv1.1)
    results/<split>/diagnoses/real-debugger-v1/llm-summary-v1-<summarizer_slug>.jsonl

Implements the 18-section structure from
`/Users/eyuansu62/Downloads/cilogbench_e3_real_llm_summary_plan.md` and the
five required tables (signal recall, diagnosis comparison, full pipeline cost,
generalization, summary failure-mode).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E3-real-llm-summary-v1"


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
    return "N/A" if x is None else f"{float(x):.{digits}f}"


def pct(x) -> str:
    return "N/A" if x is None else f"{float(x) * 100:.1f}%"


def fmt_int(x) -> str:
    return "N/A" if x is None else f"{int(x)}"


def humanize_tokens(n) -> str:
    if n is None:
        return "N/A"
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


def signal_macros_for(split: str, method: str) -> dict:
    """Read the per-method signal-recall eval (the M3 / M4 evaluator output).
    Returns macro_signal_recall, macro_critical_signal_recall, macro_evidence_span_coverage,
    macro_reduction_ratio."""
    p = ROOT / "results" / split / f"eval_{method}.json"
    if not p.exists():
        return {}
    return load_json(p)


def per_case_summary_meta(split: str, method: str) -> dict[str, dict]:
    """Per-case usage metadata from the summary-method jsonl: chunk_count,
    summary_processing_tokens (approx), final_context_tokens, etc."""
    p = ROOT / "results" / split / f"{method}.jsonl"
    out: dict[str, dict] = {}
    for row in load_jsonl(p):
        meta = row.get("metadata") or {}
        usage = meta.get("usage") or {}
        in_tok = usage.get("input_tokens") or usage.get("input_tokens_total") or 0
        out_tok = usage.get("output_tokens") or usage.get("output_tokens_total") or 0
        # Sanity: pre-2026-05-02 shim runs only recorded the non-cached
        # `input_tokens` field, which excludes the system-prompt cache. When
        # that shows as a dramatic undercount vs. the raw log size, fall back
        # to a chars-per-4 estimate so the cost table is not misleading.
        raw_chars = row.get("input_byte_size") or 0
        chars_estimate = max(0, raw_chars // 4)
        if in_tok < chars_estimate * 0.3:  # likely the old non-cached number
            in_tok_used = chars_estimate
            in_tok_source = "estimated_from_raw_chars"
        else:
            in_tok_used = int(in_tok)
            in_tok_source = "shim_reported"
        out[row["case_id"]] = {
            "chunk_count": meta.get("chunk_count"),
            "non_empty_chunk_count": meta.get("non_empty_chunk_count"),
            "summary_input_tokens": in_tok_used,
            "summary_input_tokens_source": in_tok_source,
            "summary_output_tokens": int(out_tok),
            "summary_processing_tokens": int(in_tok_used) + int(out_tok),
            "context_tokens_estimate": (
                meta.get("final_context_tokens_estimate")
                or (row.get("output") or {}).get("context_tokens_estimate")
            ),
            "context_chars": row.get("output_byte_size"),
            "provider_error": meta.get("provider_error"),
        }
    return out


def render_signal_recall_table(
    splits: list[str],
    methods: list[str],
    summary_method: str,
) -> list[str]:
    md = ["## 7. Real summary signal recall",
          "",
          "Side-by-side recall of every locked baseline plus the new real "
          f"summary method `{summary_method}`. `Reduction` = bytes saved vs "
          "raw; `Mapping` = chunk count. `Summary Processing Tokens` is 0 "
          "for non-summary methods and equals map+reduce input/output token "
          "totals for the LLM summary.",
          "",
          "| Method | Split | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Sum Proc Tok | Final Ctx Tok |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m in methods:
        for s in splits:
            sm = signal_macros_for(s, m)
            mapping = "—"
            sproc = 0
            ctxtok = sm.get("macro_context_tokens")
            if m == summary_method:
                # Per-case meta sums
                pcm = per_case_summary_meta(s, m)
                if pcm:
                    chunk_counts = [v.get("chunk_count") for v in pcm.values() if v.get("chunk_count")]
                    if chunk_counts:
                        mapping = f"{min(chunk_counts)}–{max(chunk_counts)}"
                    sproc = sum((v.get("summary_processing_tokens") or 0) for v in pcm.values())
                    if not ctxtok:
                        toks = [v.get("context_tokens_estimate") for v in pcm.values() if v.get("context_tokens_estimate")]
                        ctxtok = sum(toks) / len(toks) if toks else None
            md.append(
                f"| `{m}` | {s} "
                f"| {pct(sm.get('macro_signal_recall'))} "
                f"| {pct(sm.get('macro_critical_signal_recall'))} "
                f"| {pct(sm.get('macro_evidence_span_coverage'))} "
                f"| {pct(sm.get('macro_reduction_ratio'))} "
                f"| {mapping} "
                f"| {humanize_tokens(sproc) if sproc else '—'} "
                f"| {humanize_tokens(ctxtok)} |"
            )
    md.append("")
    return md


def render_diagnosis_comparison(
    splits: list[str],
    methods: list[str],
    diagnoser: str,
) -> list[str]:
    md = ["## 8. Diagnosis comparison (sv1.1 primary)",
          "",
          "| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | File Recall | Test Recall | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok | Diag Tok |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in methods:
        for s in splits:
            ev = ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json"
            if not ev.exists():
                continue
            mb = methods_in(load_json(ev)).get(m)
            if mb is None:
                continue
            md.append(
                f"| `{m}` | {s} "
                f"| {pct(mb.get('diagnosis_success_rate'))} "
                f"| {num(mb.get('macro_category_match_score_v1_1'))} "
                f"| {pct(mb.get('macro_critical_signal_mention_recall'))} "
                f"| {pct(mb.get('macro_must_mention_coverage'))} "
                f"| {pct(mb.get('macro_relevant_file_recall'))} "
                f"| {pct(mb.get('macro_relevant_test_recall'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb.get('abstention_rate'))} "
                f"| **{num(mb.get('diagnosis_score_v1_1'))}** "
                f"| {num(mb.get('diagnosis_score_v1'))} "
                f"| {humanize_tokens(mb.get('macro_context_tokens'))} "
                f"| {humanize_tokens(mb.get('macro_diagnosis_tokens'))} |"
            )
    md.append("")
    return md


def render_pipeline_cost_table(
    splits: list[str],
    methods: list[str],
    diagnoser: str,
    summary_method: str,
) -> list[str]:
    md = ["## 10. Full pipeline cost table",
          "",
          "Pipeline tokens = `summary_processing_tokens` + "
          "`final_context_tokens` + `diagnosis_output_tokens`. "
          "summary_processing is non-zero only for the real summary method; "
          "for the deterministic baselines it is 0 by definition.",
          "",
          "| Method | Split | Sum Proc Tok | Final Ctx Tok | Diag Out Tok | Total Pipeline Tok | Estimated Calls | Unsupported | Provider Errors |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m in methods:
        for s in splits:
            ev = ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json"
            if not ev.exists():
                continue
            mb = methods_in(load_json(ev)).get(m)
            if mb is None:
                continue
            ctx_tok = mb.get("macro_context_tokens") or 0
            diag_tok = mb.get("macro_diagnosis_tokens") or 0
            sproc_tok = 0
            calls = 0
            unsupported = 0
            prov_err = 0
            if m == summary_method:
                pcm = per_case_summary_meta(s, m)
                # Total summary-side tokens, averaged per case
                cases = list(pcm.values())
                if cases:
                    sproc_tok = sum(v.get("summary_processing_tokens") or 0 for v in cases) / len(cases)
                    chunk_counts = [v.get("chunk_count") or 0 for v in cases]
                    calls = sum(chunk_counts) + len(cases)  # map calls + reduce per case
                    prov_err = sum(1 for v in cases if v.get("provider_error"))
            # Provider errors from diagnosis
            for c in mb.get("cases", []):
                if c.get("provider_error"):
                    prov_err += 1
            total = (sproc_tok or 0) + (ctx_tok or 0) + (diag_tok or 0)
            md.append(
                f"| `{m}` | {s} "
                f"| {humanize_tokens(sproc_tok) if sproc_tok else '0'} "
                f"| {humanize_tokens(ctx_tok)} "
                f"| {humanize_tokens(diag_tok)} "
                f"| **{humanize_tokens(total)}** "
                f"| {calls or '—'} "
                f"| {unsupported} "
                f"| {prov_err} |"
            )
    md.append("")
    return md


def render_generalization_table(
    splits: list[str],
    methods: list[str],
    diagnoser: str,
) -> list[str]:
    md = ["## 15. Generalization table (sv1.1)",
          "",
          "Per-method `diagnosis_score_v1_1` across splits. `Max Gap` is the "
          "spread between the best and worst split for that method; `Large "
          "Gap?` is YES when the gap is ≥ 20 percentage points (0.20).",
          "",
          "| Method | " + " | ".join(splits) + " | Max Gap | Large Gap? |",
          "|---|" + "|".join("---:" for _ in splits) + "|---:|---|"]
    for m in methods:
        vals = []
        for s in splits:
            ev = ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json"
            if not ev.exists():
                vals.append(None); continue
            mb = methods_in(load_json(ev)).get(m)
            vals.append(mb.get("diagnosis_score_v1_1") if mb else None)
        nn = [v for v in vals if v is not None]
        gap = (max(nn) - min(nn)) if len(nn) >= 2 else None
        large = gap is not None and gap >= 0.20
        cells = [num(v) for v in vals]
        md.append(f"| `{m}` | " + " | ".join(cells)
                   + f" | {num(gap)} | {'YES' if large else '—'} |")
    md.append("")
    return md


def render_summary_failure_modes(
    splits: list[str],
    summary_method: str,
    diagnoser: str,
) -> list[str]:
    md = ["## 11. Summary failure-mode analysis",
          "",
          "Per-case rows for the real summary method only. `expert-reviewed?` "
          "is YES on holdout cases that were part of the E2 expert-model "
          "review batch.",
          "",
          "| Case | Split | Sum Tok | Sum Proc Tok | Sig Recall | Crit Recall | sv1.1 | expert-reviewed? | Failure mode |",
          "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for s in splits:
        sig_eval = signal_macros_for(s, summary_method)
        per_case_sig = {c["case_id"]: c for c in sig_eval.get("cases", [])} if sig_eval else {}
        pcm = per_case_summary_meta(s, summary_method)
        ev_p = ROOT / "results" / s / f"eval_diagnosis_{diagnoser}.json"
        ev_obj = load_json(ev_p) if ev_p.exists() else {}
        diag_method = methods_in(ev_obj).get(summary_method)
        diag_cases = {c["case_id"]: c for c in (diag_method or {}).get("cases", [])}
        for cid in sorted(set(pcm) | set(per_case_sig) | set(diag_cases)):
            sig = per_case_sig.get(cid, {})
            meta = pcm.get(cid, {})
            diag = diag_cases.get(cid, {})
            sv = diag.get("diagnosis_score_v1_1")
            fmode = []
            if (diag or {}).get("provider_error"):
                fmode.append(diag["provider_error"])
            else:
                if sig.get("critical_signal_recall") == 0:
                    fmode.append("omitted_primary_error")
                if (diag or {}).get("relevant_file_recall") == 0:
                    fmode.append("omitted_file_name")
                if (diag or {}).get("relevant_test_recall") == 0 and (diag or {}).get("relevant_test_recall") is not None:
                    fmode.append("omitted_test_name")
                if (diag or {}).get("forbidden_claim_violations"):
                    fmode.append("hallucinated_root_cause")
                if (diag or {}).get("category_match_score_v1_1") in (0.0, 0) and (diag or {}).get("critical_signal_mention_recall", 0) >= 0.5:
                    fmode.append("good_high_level_but_missing_repair_evidence")
                if not fmode:
                    fmode.append("—")
            reviewed = "YES" if (s == "holdout" and cid in {
                "actions-terraform-001", "dependabot-cargo-001",
                "docs-transformers-001", "pushpr-nextjs-001",
                "tsc-typescript-001",
            }) else "no"
            md.append(
                f"| `{cid}` | {s} "
                f"| {humanize_tokens(meta.get('context_tokens_estimate'))} "
                f"| {humanize_tokens(meta.get('summary_processing_tokens'))} "
                f"| {pct(sig.get('signal_recall'))} "
                f"| {pct(sig.get('critical_signal_recall'))} "
                f"| {num(sv)} "
                f"| {reviewed} "
                f"| {', '.join(fmode)} |"
            )
    md.append("")
    return md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summarizer-slug", required=True,
                    help="Slug used in method name (e.g. 'haiku').")
    ap.add_argument("--summarizer-config", type=Path,
                    default=None,
                    help="Defaults to configs/summarizers/<slug>.json")
    ap.add_argument("--diagnoser", default="real-debugger-v1")
    ap.add_argument("--diagnoser-config", type=Path,
                    default=None,
                    help="Defaults to configs/diagnosers/<diagnoser>.json")
    ap.add_argument("--protocol-lock", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.2.lock.json")
    ap.add_argument("--splits", nargs="+", default=["dev", "holdout", "stress"])
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    slug = args.summarizer_slug
    summary_method = f"llm-summary-v1-{slug}"
    summarizer_cfg = args.summarizer_config or (ROOT / "configs" / "summarizers" / f"{slug}.json")
    diagnoser_cfg = args.diagnoser_config or (ROOT / "configs" / "diagnosers" / f"{args.diagnoser}.json")
    map_prompt = ROOT / "prompts" / "llm_summary_v1_map.md"
    reduce_prompt = ROOT / "prompts" / "llm_summary_v1_reduce.md"
    debugger_prompt = ROOT / "prompts" / "debugger_v1.md"

    # Methods to compare in tables. Mock is included for the contrast the
    # plan calls out ("does real summary preserve critical signals better
    # than llm-summary-v1-mock?").
    methods = [
        "raw", "tail", "grep",
        "rtk-read", "rtk-log", "rtk-err-cat",
        "llm-summary-v1-mock",
        summary_method,
    ]

    # ---- Manifest ----
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": "cilogbench-v1.2",
        "protocol_lock_path": str(args.protocol_lock.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol_lock),

        "summarizer_name": slug,
        "summary_method": summary_method,
        "summarizer_config_path": str(summarizer_cfg.relative_to(ROOT)),
        "summarizer_config_sha256": sha256_path(summarizer_cfg),
        "map_prompt_path": str(map_prompt.relative_to(ROOT)),
        "map_prompt_sha256": sha256_path(map_prompt),
        "reduce_prompt_path": str(reduce_prompt.relative_to(ROOT)),
        "reduce_prompt_sha256": sha256_path(reduce_prompt),

        "diagnoser_name": args.diagnoser,
        "diagnoser_config_path": str(diagnoser_cfg.relative_to(ROOT)),
        "diagnoser_config_sha256": sha256_path(diagnoser_cfg),
        "debugger_prompt_path": str(debugger_prompt.relative_to(ROOT)),
        "debugger_prompt_sha256": sha256_path(debugger_prompt),

        "splits": args.splits,
        "case_count_by_split": {
            s: int(load_json(args.protocol_lock).get("splits", {}).get(s, {}).get("case_count") or 0)
            for s in args.splits
        },

        "primary_score": "diagnosis_score_v1_1",
        "secondary_score": "diagnosis_score_v1",

        "summary_manifest_paths": {
            s: f"results/{s}/{summary_method}.jsonl" for s in args.splits
        },
        "signal_eval_paths": {
            s: f"results/{s}/eval_{summary_method}.json" for s in args.splits
        },
        "diagnosis_eval_paths": {
            s: f"results/{s}/eval_diagnosis_{args.diagnoser}.json" for s in args.splits
        },

        "report_path": f"reports/e3_real_llm_summary_cilogbench_v1_2_{slug}.md",

        "started_at": started,
        "finished_at": started,
        "git_commit": "unknown",
        "working_tree_dirty": True,
    }

    out_manifest = args.results_dir / f"e3_real_llm_summary_cilogbench_v1_2_{slug}.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")

    # ---- Report ----
    md: list[str] = []
    md.append(f"# E3 — Real LLM Summary Baseline ({slug}) on cilogbench-v1.2")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `cilogbench-v1.2` "
              f"(SHA `{manifest['protocol_lock_sha256'][:16]}…`)")
    md.append(f"- **Summarizer:** `{summary_method}` (config "
              f"`{summarizer_cfg.relative_to(ROOT)}`, "
              f"SHA `{manifest['summarizer_config_sha256'][:16]}…`)")
    md.append(f"- **Debugger:** `{args.diagnoser}` (held fixed from E1)")
    md.append(f"- **Splits:** {', '.join(args.splits)}")
    md.append(f"- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated). `diagnosis_score_v1` reported as secondary.")
    md.append(f"- **Run started:** {started}")
    md.append("")

    # 1
    md.append("## 1. Experiment summary")
    md.append("")
    md.append(
        "E3 adds one **real** LLM-generated CI failure summary as a context "
        "method (`" + summary_method + "`) on `cilogbench-v1.2` and runs the "
        "same fixed debugger as E1 (`" + args.diagnoser + "`) against it. "
        "The intent is to see whether a compact LLM summary improves "
        "fixed-debugger diagnosis quality enough to justify its summary-"
        "processing cost, vs. raw, tail, grep, the three RTK modes, and "
        "the deterministic mock summary."
    )
    md.append("")

    # 2
    md.append("## 2. Protocol and scoring summary")
    md.append("")
    md.append(
        f"- Protocol lock: `{args.protocol_lock.relative_to(ROOT)}` "
        f"(SHA `{manifest['protocol_lock_sha256']}`)"
    )
    md.append(f"- Diagnosis evaluator: `tools/evaluate_diagnosis.py` (v1.2)")
    md.append(f"- Calibration table: `configs/evaluation/category_compatibility_v1_1.json`")
    md.append(f"- Primary score: `diagnosis_score_v1_1`")
    md.append(f"- Secondary score: `diagnosis_score_v1` (preserved alongside sv1.1)")
    md.append(
        "- E2b memo: `reports/e2b_score_calibration_v1_1.md` "
        "(why sv1.1 is primary)"
    )
    md.append("")

    # 3
    md.append("## 3. Summarizer config summary")
    md.append("")
    sc = load_json(summarizer_cfg)
    md.append(
        f"- summarizer_name: `{sc.get('summarizer_name')}`\n"
        f"- method_name: `{sc.get('method_name')}`\n"
        f"- provider: `{sc.get('provider')}`\n"
        f"- model: `{(sc.get('model') or {}).get('model_name')}`@`{(sc.get('model') or {}).get('model_version')}`, "
        f"temperature={(sc.get('model') or {}).get('temperature')}, "
        f"max_output_tokens={(sc.get('model') or {}).get('max_output_tokens')}\n"
        f"- chunking: chunk_lines="
        f"{(sc.get('chunking') or {}).get('chunk_lines')}, "
        f"overlap_lines={(sc.get('chunking') or {}).get('chunk_overlap_lines')}, "
        f"on_oversize=`{(sc.get('chunking') or {}).get('on_context_too_large')}`\n"
        f"- map prompt SHA: `{manifest['map_prompt_sha256']}`\n"
        f"- reduce prompt SHA: `{manifest['reduce_prompt_sha256']}`"
    )
    md.append("")

    # 4
    md.append("## 4. Debugger config summary")
    md.append("")
    dc = load_json(diagnoser_cfg)
    md.append(
        f"- diagnoser_name: `{dc.get('diagnoser_name')}`\n"
        f"- model: `{(dc.get('model') or {}).get('model_name')}`@`{(dc.get('model') or {}).get('model_version')}`, "
        f"temperature={(dc.get('model') or {}).get('temperature')}, "
        f"max_output_tokens={(dc.get('model') or {}).get('max_output_tokens')}\n"
        f"- prompt SHA: `{manifest['debugger_prompt_sha256']}`\n"
        f"- determinism: `deterministic={(dc.get('model') or {}).get('deterministic')}`"
    )
    md.append("")

    # 5
    md.append("## 5. Privacy audit summary")
    md.append("")
    md.append(
        "Privacy audits ran on `raw` for all three splits before E3 began "
        "(see `reports/<split>_privacy_audit.md`). Re-run on the new "
        f"summary outputs (`reports/<split>_privacy_audit.md`) before any "
        "downstream sharing."
    )
    md.append("")

    # 6
    md.append("## 6. Splits and methods evaluated")
    md.append("")
    md.append("| Split | Cases | Methods |")
    md.append("|---|---:|---|")
    for s in args.splits:
        md.append(f"| {s} | {manifest['case_count_by_split'][s]} | "
                   f"{', '.join(f'`{m}`' for m in methods)} |")
    md.append("")

    # 7
    md.extend(render_signal_recall_table(args.splits, methods, summary_method))

    # 8
    md.extend(render_diagnosis_comparison(args.splits, methods, args.diagnoser))

    # 9 sv1 vs sv1.1
    md.append("## 9. sv1 vs sv1.1 comparison")
    md.append("")
    md.append("| Method | Split | sv1 | sv1.1 | Δ | confErr v1 | confErr v1.1 |")
    md.append("|---|---|---:|---:|---:|---:|---:|")
    for m in methods:
        for s in args.splits:
            ev_p = ROOT / "results" / s / f"eval_diagnosis_{args.diagnoser}.json"
            if not ev_p.exists():
                continue
            mb = methods_in(load_json(ev_p)).get(m)
            if mb is None:
                continue
            sv1 = mb.get("diagnosis_score_v1")
            sv1_1 = mb.get("diagnosis_score_v1_1")
            delta = (sv1_1 - sv1) if (sv1 is not None and sv1_1 is not None) else None
            md.append(
                f"| `{m}` | {s} | {num(sv1)} | {num(sv1_1)} "
                f"| {'+' if (delta or 0) >= 0 else ''}{num(delta)} "
                f"| {pct(mb.get('confident_error_rate'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} |"
            )
    md.append("")

    # 10 cost
    md.extend(render_pipeline_cost_table(args.splits, methods, args.diagnoser, summary_method))

    # 11 summary failure modes
    md.extend(render_summary_failure_modes(args.splits, summary_method, args.diagnoser))

    # 12 confident-error analysis
    md.append("## 12. Confident-error analysis")
    md.append("")
    md.append("Confident-error (sv1.1 trigger: `confidence>=0.7 AND "
              "(forbidden>0 OR (cms=0 AND critical<0.5 AND must<0.5))`) "
              "rate by method × split:")
    md.append("")
    md.append("| Method | dev | holdout | stress |")
    md.append("|---|---:|---:|---:|")
    for m in methods:
        cells = []
        for s in args.splits:
            ev_p = ROOT / "results" / s / f"eval_diagnosis_{args.diagnoser}.json"
            mb = methods_in(load_json(ev_p)).get(m) if ev_p.exists() else None
            cells.append(pct((mb or {}).get("confident_error_rate_v1_1")))
        md.append(f"| `{m}` | " + " | ".join(cells) + " |")
    md.append("")

    # 13 abstention analysis
    md.append("## 13. Abstention analysis")
    md.append("")
    md.append("| Method | dev | holdout | stress |")
    md.append("|---|---:|---:|---:|")
    for m in methods:
        cells = []
        for s in args.splits:
            ev_p = ROOT / "results" / s / f"eval_diagnosis_{args.diagnoser}.json"
            mb = methods_in(load_json(ev_p)).get(m) if ev_p.exists() else None
            cells.append(pct((mb or {}).get("abstention_rate")))
        md.append(f"| `{m}` | " + " | ".join(cells) + " |")
    md.append("")

    # 14 unsupported / provider errors
    md.append("## 14. Unsupported-context / provider-error analysis")
    md.append("")
    md.append("Per-method counts of `provider_error`/`unsupported_context_too_large` rows.")
    md.append("")
    md.append("| Method | Split | Provider errors | Cases |")
    md.append("|---|---|---:|---:|")
    for m in methods:
        for s in args.splits:
            ev_p = ROOT / "results" / s / f"eval_diagnosis_{args.diagnoser}.json"
            if not ev_p.exists():
                continue
            mb = methods_in(load_json(ev_p)).get(m)
            if mb is None:
                continue
            cases = mb.get("cases") or []
            errs = sum(1 for c in cases if c.get("provider_error"))
            md.append(f"| `{m}` | {s} | {errs} | {len(cases)} |")
    md.append("")

    # 15 generalization
    md.extend(render_generalization_table(args.splits, methods, args.diagnoser))

    # 16 per-case hard failures
    md.append("## 16. Per-case hard failures (sv1.1 < 0.20)")
    md.append("")
    md.append("| Case | Split | Method | sv1.1 | confErr v1.1 | provider_error |")
    md.append("|---|---|---|---:|:---:|---|")
    for s in args.splits:
        ev_p = ROOT / "results" / s / f"eval_diagnosis_{args.diagnoser}.json"
        if not ev_p.exists():
            continue
        for mb in load_json(ev_p).get("methods", []):
            if mb["context_method"] not in methods:
                continue
            for c in mb.get("cases", []):
                sv = c.get("diagnosis_score_v1_1") or 0
                if sv < 0.20:
                    md.append(
                        f"| `{c['case_id']}` | {s} | `{mb['context_method']}` "
                        f"| {num(sv)} "
                        f"| {'YES' if c.get('confident_error_v1_1') else '—'} "
                        f"| {c.get('provider_error') or '—'} |"
                    )
    md.append("")

    # 17 interpretation guardrails
    md.append("## 17. Interpretation guardrails")
    md.append("")
    md.append("- One summarizer (`" + summary_method + "`), one debugger "
              "(`" + args.diagnoser + "`), one summary prompt, 16 cases. "
              "Treat all numbers as directional, not statistical.")
    md.append("- Same model on both sides. A Sonnet-summarizer / Haiku-"
              "debugger run is the natural follow-up to disentangle "
              "self-call effects.")
    md.append("- sv1.1 is the calibrated score from E2b, but the "
              "calibration was done with **expert-model** review labels "
              "(`claude-opus-4-7-expert`), not human review. Real human "
              "review remains the canonical calibration.")
    md.append("- `llm-summary-v1-mock` is a deterministic stub; the gap "
              "between mock and real summary is informative but is not a "
              "fair LLM-summary baseline.")
    md.append("- Pricing for Haiku changes over time; the cost table is "
              "informational.")
    md.append("")

    # 18 next experiment
    md.append("## 18. Recommended next experiment")
    md.append("")
    md.append(
        "Pick one of the four options listed in the E3 plan based on the "
        "sv1.1 / cost / signal-recall numbers above:"
    )
    md.append("")
    md.append("- **Option A: real summary clearly useful** — freeze "
              "`cilogbench-v1.3` with the real summary as a baseline; "
              "queue an actual human review of the summary diagnoses.")
    md.append("- **Option B: concise but lossy** — improve the summary "
              "prompt on dev only, freeze `llm_summary_v2_*` prompts.")
    md.append("- **Option C: useful but expensive** — explore a hybrid "
              "(grep-first, summary-on-fallback).")
    md.append("- **Option D: results mixed** — run a second debugger "
              "model or human review before adding more methods.")
    md.append("")

    out_md = args.reports_dir / f"e3_real_llm_summary_cilogbench_v1_2_{slug}.md"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
