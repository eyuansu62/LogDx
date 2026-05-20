"""
E6 second-debugger replication report renderer.

Reads:
  protocols/legacy/cilogbench-v1.3.lock.json
  configs/diagnosers/<diagnoser_v1>.json
  configs/diagnosers/<diagnoser_v2>.json
  results/<split>/eval_diagnosis_<diagnoser_v1>.json
  results/<split>/eval_diagnosis_<diagnoser_v2>.json
  results/<split>/diagnoses/<diagnoser_v2>/*.jsonl

Writes:
  reports/e6_second_debugger_cilogbench_v1_3_<v2_slug>.md
  results/e6_second_debugger_cilogbench_v1_3_<v2_slug>.manifest.json

Implements the 16-section replication report and the 6 required tables
from the E6 plan, including the v1-vs-v2 rank-stability matrix and
per-case model-disagreement table.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E6-second-debugger-replication-v1"


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


def macro_across_splits(method: str, diagnoser: str, splits: list[str], key: str,
                         results_dir: Path) -> float | None:
    vals = []
    for s in splits:
        p = results_dir / s / f"eval_diagnosis_{diagnoser}.json"
        if not p.exists():
            continue
        mb = methods_in(load_json(p)).get(method) or {}
        v = mb.get(key)
        if v is not None:
            vals.append(v)
    return round(sum(vals) / len(vals), 4) if vals else None


def case_score(method: str, diagnoser: str, split: str, case_id: str,
                results_dir: Path, key: str = "diagnosis_score_v1_1") -> float | None:
    p = results_dir / split / f"eval_diagnosis_{diagnoser}.json"
    if not p.exists():
        return None
    mb = methods_in(load_json(p)).get(method)
    if not mb:
        return None
    c = next((c for c in mb.get("cases") or [] if c["case_id"] == case_id), None)
    return (c or {}).get(key)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.3.lock.json")
    ap.add_argument("--diagnoser-v1", default="real-debugger-v1")
    ap.add_argument("--diagnoser-v2", default="real-debugger-v2")
    ap.add_argument("--diagnoser-v1-config", type=Path,
                    default=ROOT / "configs" / "diagnosers" / "real-debugger-v1.json")
    ap.add_argument("--diagnoser-v2-config", type=Path,
                    default=ROOT / "configs" / "diagnosers" / "real-debugger-v2.json")
    ap.add_argument("--debugger-prompt", type=Path,
                    default=ROOT / "prompts" / "debugger_v1.md")
    ap.add_argument("--splits", nargs="+", default=["dev", "holdout", "stress"])
    ap.add_argument("--methods", default="raw,tail,grep,rtk-read,rtk-log,rtk-err-cat,llm-summary-v1-mock,hybrid-grep-4k-rtk-err-cat-v1")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    v2_slug = args.diagnoser_v2.replace("real-debugger-", "")  # crude slug
    if v2_slug == args.diagnoser_v2:
        v2_slug = args.diagnoser_v2

    md: list[str] = []
    md.append(f"# E6 — Second-Debugger Replication on cilogbench-v1.3 ({args.diagnoser_v2})")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `cilogbench-v1.3` (SHA `{sha256_path(args.protocol)[:16]}…`)")
    md.append(f"- **Debugger v1:** `{args.diagnoser_v1}` (Claude Haiku 4.5; held fixed for comparison)")
    md.append(f"- **Debugger v2:** `{args.diagnoser_v2}` (Claude Sonnet 4.6; this run)")
    md.append(f"- **Prompt:** `prompts/debugger_v1.md` (SHA `{sha256_path(args.debugger_prompt)[:16]}…`) — same prompt for both debuggers")
    md.append(f"- **Splits:** {', '.join(args.splits)}")
    md.append(f"- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated; secondary = `diagnosis_score_v1`)")
    md.append("")

    # 1. Executive summary
    md.append("## 1. Executive summary")
    md.append("")
    hb_v1 = macro_across_splits("hybrid-grep-4k-rtk-err-cat-v1", args.diagnoser_v1, args.splits, "diagnosis_score_v1_1", args.results_dir)
    hb_v2 = macro_across_splits("hybrid-grep-4k-rtk-err-cat-v1", args.diagnoser_v2, args.splits, "diagnosis_score_v1_1", args.results_dir)
    grep_v1 = macro_across_splits("grep", args.diagnoser_v1, args.splits, "diagnosis_score_v1_1", args.results_dir)
    grep_v2 = macro_across_splits("grep", args.diagnoser_v2, args.splits, "diagnosis_score_v1_1", args.results_dir)
    md.append(
        f"On `cilogbench-v1.3` with Sonnet 4.6 as `real-debugger-v2`, the "
        f"locked `hybrid-grep-4k-rtk-err-cat-v1` baseline scored macro "
        f"sv1.1 = **{num(hb_v2)}** vs `grep` = **{num(grep_v2)}**. The "
        f"v1 (Haiku) numbers were hybrid {num(hb_v1)} / grep {num(grep_v1)}. "
        f"Detailed rank-stability table is in section 10."
    )
    md.append("")

    # 2. Protocol summary
    md.append("## 2. Protocol summary")
    md.append("")
    lock = load_json(args.protocol)
    md.append(f"- protocol_id: `{lock.get('protocol_id')}`")
    md.append(f"- inherits_from: `{lock.get('inherits_from')}`")
    md.append(f"- splits: " + ", ".join(f"`{s}` ({lock['splits'][s]['case_count']} cases)" for s in args.splits))
    md.append(f"- locked baselines: {len(lock.get('baselines') or {})}")
    md.append(f"- primary score: `{lock.get('scoring', {}).get('diagnosis_score_primary')}`")
    md.append(f"- secondary score: `{lock.get('scoring', {}).get('diagnosis_score_secondary')}`")
    md.append("")

    # 3. Debugger config + model card
    md.append("## 3. Debugger-v2 config and model card")
    md.append("")
    v2_cfg = load_json(args.diagnoser_v2_config)
    m = v2_cfg.get("model") or {}
    md.append(f"- diagnoser_name: `{v2_cfg.get('diagnoser_name')}`")
    md.append(f"- model: `{m.get('model_name')}` @ `{m.get('model_version')}`")
    md.append(f"- temperature: {m.get('temperature')} · max_output_tokens: {m.get('max_output_tokens')}")
    md.append(f"- json_mode: {m.get('json_mode')} · tool_use: {m.get('tool_use')} · web_access: {m.get('web_access')}")
    md.append(f"- prompt SHA: `{sha256_path(args.debugger_prompt)}`")
    md.append(f"- config SHA: `{sha256_path(args.diagnoser_v2_config)}`")
    md.append(f"- model card: `docs/model_cards/{args.diagnoser_v2}.md`")
    md.append("")

    # 4. Privacy audit summary
    md.append("## 4. Privacy audit summary")
    md.append("")
    md.append("Privacy audits were run for all 8+ context methods × 3 splits before this experiment. Result: 0 hits (see `reports/{dev,holdout,stress}_privacy_audit.md`). Re-run before any downstream sharing.")
    md.append("")

    # 5. Methods and splits
    md.append("## 5. Methods and splits evaluated")
    md.append("")
    md.append("| Method | dev | holdout | stress |")
    md.append("|---|:---:|:---:|:---:|")
    for me in methods:
        cells = []
        for s in args.splits:
            p = args.results_dir / s / "diagnoses" / args.diagnoser_v2 / f"{me}.jsonl"
            cells.append(f"{len(load_jsonl(p))}" if p.exists() else "—")
        md.append(f"| `{me}` | " + " | ".join(cells) + " |")
    md.append("")

    # 6. Per-split diagnosis table — v2
    md.append("## 6. Per-split diagnosis metrics (real-debugger-v2)")
    md.append("")
    md.append("### Table 1 — Per-split v2 diagnosis")
    md.append("")
    md.append("| Method | Split | Success | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | sv1.1 | sv1 | Ctx Tok | Provider Errs |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for me in methods:
        for s in args.splits:
            p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
            mb = methods_in(load_json(p) if p.exists() else {}).get(me)
            if not mb:
                continue
            cases = mb.get("cases") or []
            pe = sum(1 for c in cases if c.get("provider_error"))
            md.append(
                f"| `{me}` | {s} "
                f"| {pct(mb.get('diagnosis_success_rate'))} "
                f"| {num(mb.get('macro_category_match_score_v1_1'))} "
                f"| {pct(mb.get('macro_critical_signal_mention_recall'))} "
                f"| {pct(mb.get('macro_must_mention_coverage'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb.get('abstention_rate'))} "
                f"| **{num(mb.get('diagnosis_score_v1_1'))}** "
                f"| {num(mb.get('diagnosis_score_v1'))} "
                f"| {humanize_tokens(mb.get('macro_context_tokens'))} "
                f"| {pe} |"
            )
    md.append("")

    # 7. Hybrid vs grep
    md.append("## 7. Hybrid vs grep (v2)")
    md.append("")
    md.append("### Table 2 — Hybrid vs grep")
    md.append("")
    md.append("| Split | Hybrid sv1.1 | Grep sv1.1 | Δ | Hybrid total tok | Grep total tok | Token reduction |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in args.splits:
        p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
        ev = load_json(p) if p.exists() else {}
        hb = methods_in(ev).get("hybrid-grep-4k-rtk-err-cat-v1") or {}
        gr = methods_in(ev).get("grep") or {}
        hb_sv = hb.get("diagnosis_score_v1_1")
        gr_sv = gr.get("diagnosis_score_v1_1")
        delta = (hb_sv - gr_sv) if (hb_sv is not None and gr_sv is not None) else None
        hb_tot = (hb.get("macro_context_tokens") or 0) + (hb.get("macro_diagnosis_tokens") or 0)
        gr_tot = (gr.get("macro_context_tokens") or 0) + (gr.get("macro_diagnosis_tokens") or 0)
        red = (1 - hb_tot / gr_tot) if gr_tot else None
        md.append(
            f"| {s} | {num(hb_sv)} | {num(gr_sv)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} "
            f"| {humanize_tokens(hb_tot)} | {humanize_tokens(gr_tot)} "
            f"| {pct(red)} |"
        )
    md.append("")

    # 8. Hybrid vs rtk-err-cat
    md.append("## 8. Hybrid vs rtk-err-cat (v2)")
    md.append("")
    md.append("### Table 3 — Hybrid vs rtk-err-cat")
    md.append("")
    md.append("| Split | Hybrid sv1.1 | RTK sv1.1 | Δ | Hybrid total tok | RTK total tok |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for s in args.splits:
        p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
        ev = load_json(p) if p.exists() else {}
        hb = methods_in(ev).get("hybrid-grep-4k-rtk-err-cat-v1") or {}
        rk = methods_in(ev).get("rtk-err-cat") or {}
        hb_sv = hb.get("diagnosis_score_v1_1")
        rk_sv = rk.get("diagnosis_score_v1_1")
        delta = (hb_sv - rk_sv) if (hb_sv is not None and rk_sv is not None) else None
        hb_tot = (hb.get("macro_context_tokens") or 0) + (hb.get("macro_diagnosis_tokens") or 0)
        rk_tot = (rk.get("macro_context_tokens") or 0) + (rk.get("macro_diagnosis_tokens") or 0)
        md.append(
            f"| {s} | {num(hb_sv)} | {num(rk_sv)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} "
            f"| {humanize_tokens(hb_tot)} | {humanize_tokens(rk_tot)} |"
        )
    md.append("")

    # 9. v1 vs v2 debugger comparison
    md.append("## 9. v1 debugger vs v2 debugger comparison")
    md.append("")
    md.append("### Table 4 — Replication (macro across 3 splits)")
    md.append("")
    md.append("| Method | v1 macro sv1.1 | v2 macro sv1.1 | Δ | v1 rank | v2 rank | Rank change |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    # Build rank tables
    v1_macro = {me: macro_across_splits(me, args.diagnoser_v1, args.splits, "diagnosis_score_v1_1", args.results_dir) for me in methods}
    v2_macro = {me: macro_across_splits(me, args.diagnoser_v2, args.splits, "diagnosis_score_v1_1", args.results_dir) for me in methods}
    v1_ranked = sorted([(me, sv) for me, sv in v1_macro.items() if sv is not None], key=lambda x: -x[1])
    v2_ranked = sorted([(me, sv) for me, sv in v2_macro.items() if sv is not None], key=lambda x: -x[1])
    v1_rank = {me: i + 1 for i, (me, _) in enumerate(v1_ranked)}
    v2_rank = {me: i + 1 for i, (me, _) in enumerate(v2_ranked)}
    for me in methods:
        sv1 = v1_macro.get(me); sv2 = v2_macro.get(me)
        delta = (sv2 - sv1) if (sv1 is not None and sv2 is not None) else None
        r1 = v1_rank.get(me); r2 = v2_rank.get(me)
        rdelta = ((r1 or 0) - (r2 or 0)) if (r1 and r2) else None
        rdelta_str = (f"{'+' if rdelta > 0 else ''}{rdelta}" if rdelta is not None and rdelta != 0 else "—" if rdelta == 0 else "n/a")
        md.append(
            f"| `{me}` | {num(sv1)} | {num(sv2)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} "
            f"| {r1 or 'n/a'} | {r2 or 'n/a'} | {rdelta_str} |"
        )
    md.append("")

    # 10. Model-stability analysis
    md.append("## 10. Model-stability analysis")
    md.append("")
    md.append("### Table 5 — Rank stability")
    md.append("")
    md.append("| Method | v1 rank | v2 rank | Stable? | Notes |")
    md.append("|---|---:|---:|:---:|---|")
    for me in methods:
        r1 = v1_rank.get(me); r2 = v2_rank.get(me)
        if r1 is None or r2 is None:
            stable_label = "n/a"; note = "missing eval data"
        else:
            d = abs(r1 - r2)
            stable_label = "✅" if d <= 1 else "⚠" if d <= 3 else "❌"
            if d == 0:
                note = "exact rank match"
            elif d == 1:
                note = f"adjacent ranks (Δ=1)"
            else:
                note = f"rank shift Δ={d}"
        md.append(f"| `{me}` | {r1 or 'n/a'} | {r2 or 'n/a'} | {stable_label} | {note} |")
    md.append("")

    # 11. Cost / token table
    md.append("## 11. Cost / token table")
    md.append("")
    md.append("Per-method macro tokens for v2 (Sonnet) vs v1 (Haiku). Note: per-token cost differs ~5-10× between Sonnet and Haiku at the time of this run.")
    md.append("")
    md.append("| Method | Split | v1 ctx tok | v2 ctx tok | v1 diag tok | v2 diag tok | v1 total | v2 total |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for me in methods:
        for s in args.splits:
            p1 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v1}.json"
            p2 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
            mb1 = methods_in(load_json(p1) if p1.exists() else {}).get(me) or {}
            mb2 = methods_in(load_json(p2) if p2.exists() else {}).get(me) or {}
            v1_ctx = mb1.get("macro_context_tokens") or 0
            v2_ctx = mb2.get("macro_context_tokens") or 0
            v1_diag = mb1.get("macro_diagnosis_tokens") or 0
            v2_diag = mb2.get("macro_diagnosis_tokens") or 0
            md.append(
                f"| `{me}` | {s} "
                f"| {humanize_tokens(v1_ctx)} | {humanize_tokens(v2_ctx)} "
                f"| {humanize_tokens(v1_diag)} | {humanize_tokens(v2_diag)} "
                f"| {humanize_tokens(v1_ctx + v1_diag)} | {humanize_tokens(v2_ctx + v2_diag)} |"
            )
    md.append("")

    # 12. Provider-error analysis
    md.append("## 12. Provider-error and unsupported-context analysis")
    md.append("")
    md.append("| Split | Method | v1 errs | v2 errs |")
    md.append("|---|---|---:|---:|")
    any_pe = False
    for s in args.splits:
        for me in methods:
            for diag in (args.diagnoser_v1, args.diagnoser_v2):
                pass
            p1 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v1}.json"
            p2 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
            mb1 = methods_in(load_json(p1) if p1.exists() else {}).get(me) or {}
            mb2 = methods_in(load_json(p2) if p2.exists() else {}).get(me) or {}
            pe1 = sum(1 for c in (mb1.get("cases") or []) if c.get("provider_error"))
            pe2 = sum(1 for c in (mb2.get("cases") or []) if c.get("provider_error"))
            if pe1 or pe2:
                any_pe = True
                md.append(f"| {s} | `{me}` | {pe1} | {pe2} |")
    if not any_pe:
        md.append("| — | — | 0 | 0 |")
    md.append("")

    # 13. Confident-error and abstention analysis
    md.append("## 13. Confident-error and abstention analysis")
    md.append("")
    md.append("| Method | Split | v1 confErr v1.1 | v2 confErr v1.1 | v1 abstain | v2 abstain |")
    md.append("|---|---|---:|---:|---:|---:|")
    for me in methods:
        for s in args.splits:
            p1 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v1}.json"
            p2 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
            mb1 = methods_in(load_json(p1) if p1.exists() else {}).get(me) or {}
            mb2 = methods_in(load_json(p2) if p2.exists() else {}).get(me) or {}
            md.append(
                f"| `{me}` | {s} "
                f"| {pct(mb1.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb2.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb1.get('abstention_rate'))} "
                f"| {pct(mb2.get('abstention_rate'))} |"
            )
    md.append("")

    # 14. Per-case disagreement
    md.append("## 14. Per-case disagreement analysis")
    md.append("")
    md.append("### Table 6 — Top-10 v1 vs v2 disagreements (|Δsv1.1| highest)")
    md.append("")
    md.append("| Case | Split | Method | v1 sv1.1 | v2 sv1.1 | Δ | Likely reason |")
    md.append("|---|---|---|---:|---:|---:|---|")
    rows = []
    for s in args.splits:
        p1 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v1}.json"
        p2 = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
        ev1 = load_json(p1) if p1.exists() else {}
        ev2 = load_json(p2) if p2.exists() else {}
        for me in methods:
            mb1 = methods_in(ev1).get(me) or {}
            mb2 = methods_in(ev2).get(me) or {}
            cases1 = {c["case_id"]: c for c in (mb1.get("cases") or [])}
            cases2 = {c["case_id"]: c for c in (mb2.get("cases") or [])}
            for cid, c2 in cases2.items():
                c1 = cases1.get(cid) or {}
                sv1 = c1.get("diagnosis_score_v1_1")
                sv2 = c2.get("diagnosis_score_v1_1")
                if sv1 is None or sv2 is None:
                    continue
                delta = sv2 - sv1
                rows.append((s, me, cid, sv1, sv2, delta, c1, c2))
    rows.sort(key=lambda r: -abs(r[5]))
    def reason(c1: dict, c2: dict, delta: float) -> str:
        if delta > 0.2:
            if (c1.get("category_match_score_v1_1") or 0) == 0 and (c2.get("category_match_score_v1_1") or 0) >= 0.5:
                return "v2 fixed wrong category"
            if (c1.get("critical_signal_mention_recall") or 0) < 0.5 and (c2.get("critical_signal_mention_recall") or 0) >= 0.5:
                return "v2 found more critical signals"
            if c1.get("abstained") and not c2.get("abstained"):
                return "v2 stopped abstaining"
            return "larger model uses evidence better"
        if delta < -0.2:
            if c2.get("forbidden_claim_violations") and not c1.get("forbidden_claim_violations"):
                return "v2 introduced forbidden claim"
            if c2.get("abstained") and not c1.get("abstained"):
                return "v2 abstained where v1 answered"
            return "larger model overfocused / lost signal"
        return "small model disagreement"
    for s, me, cid, sv1, sv2, delta, c1, c2 in rows[:10]:
        md.append(
            f"| `{cid}` | {s} | `{me}` "
            f"| {num(sv1)} | {num(sv2)} | "
            f"{('+' if delta >= 0 else '')}{num(delta)} | {reason(c1, c2, delta)} |"
        )
    md.append("")

    # 15. Interpretation guardrails
    md.append("## 15. Interpretation guardrails")
    md.append("")
    md.append("- **Two debugger models, one prompt family.** Conclusions are scoped to Haiku 4.5 + Sonnet 4.6 with `prompts/debugger_v1.md`. Do not generalize to Opus, GPT-class models, or different prompts.")
    md.append("- **16 cases.** Directional, not statistical.")
    md.append("- **Calibration source.** sv1.1 was calibrated in E2/E2b against expert-model labels collected on `real-debugger-v1`. Apply with care to v2.")
    md.append("- **Costs are informational.** Sonnet pricing is roughly 5–10× Haiku at the time of this run; the cost table reflects context+diagnosis tokens only, not external infrastructure.")
    md.append("- **Provider-error carryover.** Cases that hit `unsupported_context_too_large` under v1 may behave differently under v2 because Sonnet has the same 200k-token window but slightly different chunk boundaries.")
    md.append("")

    # 16. Decision
    md.append("## 16. Decision: freeze confirmed or needs more replication")
    md.append("")
    # Decision rules
    sv_pass = (hb_v2 or 0) >= (grep_v2 or 0)
    grep_total_v2 = []
    hybrid_total_v2 = []
    grep_ce_v2 = []
    hybrid_ce_v2 = []
    for s in args.splits:
        p = args.results_dir / s / f"eval_diagnosis_{args.diagnoser_v2}.json"
        ev = load_json(p) if p.exists() else {}
        gr = methods_in(ev).get("grep") or {}
        hb = methods_in(ev).get("hybrid-grep-4k-rtk-err-cat-v1") or {}
        grep_total_v2.append((gr.get("macro_context_tokens") or 0) + (gr.get("macro_diagnosis_tokens") or 0))
        hybrid_total_v2.append((hb.get("macro_context_tokens") or 0) + (hb.get("macro_diagnosis_tokens") or 0))
        grep_ce_v2.append(gr.get("confident_error_rate_v1_1") or 0)
        hybrid_ce_v2.append(hb.get("confident_error_rate_v1_1") or 0)
    cost_pass = (sum(hybrid_total_v2) / max(1, len(hybrid_total_v2))) <= (sum(grep_total_v2) / max(1, len(grep_total_v2)))
    ce_pass = (sum(hybrid_ce_v2) / max(1, len(hybrid_ce_v2))) <= (sum(grep_ce_v2) / max(1, len(grep_ce_v2)))
    hybrid_rank_v2 = v2_rank.get("hybrid-grep-4k-rtk-err-cat-v1")
    hybrid_rank_v1 = v1_rank.get("hybrid-grep-4k-rtk-err-cat-v1")
    rank_pass = (hybrid_rank_v1 is not None and hybrid_rank_v2 is not None
                 and abs(hybrid_rank_v1 - hybrid_rank_v2) <= 1)

    confirmed = sv_pass and cost_pass and ce_pass and rank_pass
    decision = "CONFIRMED_MODEL_STABLE" if confirmed else "MODEL_DEPENDENT"

    md.append(f"**Decision: `{decision}`**")
    md.append("")
    md.append("| Criterion | Hybrid (v2) | Grep (v2) | Pass? |")
    md.append("|---|---:|---:|:---:|")
    md.append(f"| Macro sv1.1 ≥ grep | {num(hb_v2)} | {num(grep_v2)} | {'✅' if sv_pass else '❌'} |")
    md.append(f"| Macro total tokens ≤ grep | "
               f"{humanize_tokens(sum(hybrid_total_v2) / max(1, len(hybrid_total_v2)))} | "
               f"{humanize_tokens(sum(grep_total_v2) / max(1, len(grep_total_v2)))} | "
               f"{'✅' if cost_pass else '❌'} |")
    md.append(f"| Macro confErr v1.1 ≤ grep | "
               f"{pct(sum(hybrid_ce_v2) / max(1, len(hybrid_ce_v2)))} | "
               f"{pct(sum(grep_ce_v2) / max(1, len(grep_ce_v2)))} | "
               f"{'✅' if ce_pass else '❌'} |")
    md.append(f"| Hybrid rank near-stable across debuggers (Δ ≤ 1) | "
               f"v1 rank {hybrid_rank_v1} → v2 rank {hybrid_rank_v2} | "
               f"— | {'✅' if rank_pass else '❌'} |")
    md.append("")
    if confirmed:
        md.append(
            "All four criteria pass. **`cilogbench-v1.3` is model-stable "
            "across the two tested debuggers** (Haiku 4.5 and Sonnet 4.6). "
            "The hybrid baseline retains its E5 advantage. Recommend "
            "moving forward with a public technical report / README "
            "narrative for v1.3, then proceeding to E7 (MCP / search-agent "
            "baseline) per the post-E6 plan."
        )
    else:
        md.append(
            "At least one criterion did not pass. Treat the hybrid "
            "advantage as **model-dependent**. Investigate the failed "
            "criterion before declaring v1.3 model-stable. A third "
            "debugger run (e.g. Opus 4.7) is appropriate only if the next "
            "claim depends on which of the two debuggers is right."
        )
    md.append("")

    out_md = args.reports_dir / f"e6_second_debugger_cilogbench_v1_3_{args.diagnoser_v2}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Manifest
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": "cilogbench-v1.3",
        "protocol_lock_path": str(args.protocol.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol),
        "diagnoser_v1": args.diagnoser_v1,
        "diagnoser_v1_config_path": str(args.diagnoser_v1_config.relative_to(ROOT)),
        "diagnoser_v1_config_sha256": sha256_path(args.diagnoser_v1_config) if args.diagnoser_v1_config.exists() else None,
        "diagnoser_v2": args.diagnoser_v2,
        "diagnoser_v2_config_path": str(args.diagnoser_v2_config.relative_to(ROOT)),
        "diagnoser_v2_config_sha256": sha256_path(args.diagnoser_v2_config),
        "debugger_prompt_path": str(args.debugger_prompt.relative_to(ROOT)),
        "debugger_prompt_sha256": sha256_path(args.debugger_prompt),
        "splits": args.splits,
        "case_count_by_split": {s: int(lock["splits"][s]["case_count"]) for s in args.splits},
        "methods": methods,
        "primary_score": "diagnosis_score_v1_1",
        "secondary_score": "diagnosis_score_v1",
        "diagnosis_eval_paths_v2": {
            s: f"results/{s}/eval_diagnosis_{args.diagnoser_v2}.json" for s in args.splits
        },
        "diagnosis_eval_paths_v1": {
            s: f"results/{s}/eval_diagnosis_{args.diagnoser_v1}.json" for s in args.splits
        },
        "report_path": str(out_md.relative_to(ROOT)),
        "decision": decision,
        "git_commit": "unknown",
        "working_tree_dirty": True,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out_manifest = args.results_dir / f"e6_second_debugger_cilogbench_v1_3_{args.diagnoser_v2}.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
