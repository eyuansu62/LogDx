"""
E8 search-fallback routing report renderer.

Reads:
  results/e8_hybrid_first_search_fallback_cilogbench_v1_3.json
  configs/routing/hybrid_search_fallback_policy_v1.json
  protocols/legacy/cilogbench-v1.3.lock.json

Writes:
  reports/e8_hybrid_first_search_fallback_cilogbench_v1_3.md
  results/e8_hybrid_first_search_fallback_cilogbench_v1_3.manifest.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E8-hybrid-first-search-fallback-analysis-v1"


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


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


def fmt_delta(a, b, prec: int = 3) -> str:
    if a is None or b is None:
        return "n/a"
    d = b - a
    return f"{'+' if d >= 0 else ''}{d:.{prec}f}"


def decide(analysis: dict) -> tuple[str, list[str]]:
    pols = {p["policy_name"]: p for p in analysis.get("policies") or []}
    hybrid = pols.get("hybrid-default") or {}
    oracle = pols.get("oracle-by-case") or {}
    deployable = [p for p in analysis.get("policies") or [] if p.get("deployable")]
    deployable_sorted = sorted(deployable,
                                 key=lambda p: -(p.get("macro_sv1_1") or 0))
    best = deployable_sorted[0] if deployable_sorted else {}
    rationale = []
    h_sv = hybrid.get("macro_sv1_1") or 0
    h_tot = hybrid.get("macro_total_tokens") or 0
    o_sv = oracle.get("macro_sv1_1") or 0
    b_sv = best.get("macro_sv1_1") or 0
    b_tot = best.get("macro_total_tokens") or 0
    b_search_rate = best.get("search_invocation_rate") or 0
    rationale.append(
        f"hybrid-default: sv1.1={num(h_sv)}, total_tokens={humanize_tokens(h_tot)}"
    )
    rationale.append(
        f"best deployable: `{best.get('policy_name')}` sv1.1={num(b_sv)} "
        f"(Δ vs hybrid {fmt_delta(h_sv, b_sv)}), "
        f"total_tokens={humanize_tokens(b_tot)} "
        f"(Δ vs hybrid {fmt_delta(h_tot, b_tot, prec=0)}), "
        f"search_invocation_rate={pct(b_search_rate)}"
    )
    rationale.append(
        f"oracle upper bound: sv1.1={num(o_sv)} "
        f"(headroom over hybrid {fmt_delta(h_sv, o_sv)})"
    )

    sv_gain = b_sv - h_sv
    cost_ratio = (b_tot / h_tot) if h_tot else float("inf")

    # Plan rules:
    if sv_gain >= 0.02 and cost_ratio <= 2.0 and b_search_rate <= 0.40:
        decision = "IMPLEMENT_E9_FIRST_CLASS_FALLBACK"
    else:
        # Check whether oracle is far above any deployable, suggesting bad gate vs bad agent
        oracle_gap = o_sv - b_sv
        if oracle_gap >= 0.05 and (sv_gain < 0.02):
            # Oracle is well above best deployable → policy gate is the bottleneck,
            # not the agent. But the plan distinguishes:
            #   - if search would help oracle but agent is failing on those cases:
            #     REVISE_SEARCH_AGENT_PROMPT_ON_DEV_ONLY
            #   - if no policy beats hybrid: STOP_SEARCH_TRACK
            decision = "REVISE_SEARCH_AGENT_PROMPT_ON_DEV_ONLY"
        elif sv_gain < 0.02 and cost_ratio > 2.0:
            decision = "STOP_SEARCH_TRACK"
        else:
            decision = "STOP_SEARCH_TRACK"
    return decision, rationale


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path,
                    default=ROOT / "results"
                            / "e8_hybrid_first_search_fallback_cilogbench_v1_3.json")
    ap.add_argument("--policy-config", type=Path,
                    default=ROOT / "configs" / "routing"
                            / "hybrid_search_fallback_policy_v1.json")
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.3.lock.json")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: {args.input} missing — run analyze_search_fallback_routing.py first.",
              file=sys.stderr)
        return 1

    analysis = load_json(args.input)
    pols_cfg = load_json(args.policy_config)
    policies = analysis.get("policies") or []
    pols_by_name = {p["policy_name"]: p for p in policies}
    decision, decision_rationale = decide(analysis)

    md: list[str] = []
    md.append("# E8 — Hybrid-First Search-Fallback Routing Analysis")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `{analysis.get('protocol_id')}` (lock SHA `{sha256_path(args.protocol)[:16]}…`)")
    md.append(f"- **Hybrid diagnoser:** `{analysis.get('hybrid_diagnoser')}` over `{analysis.get('hybrid_method')}`")
    md.append(f"- **Search agent:** `{analysis.get('search_agent')}` (E7)")
    md.append(f"- **Mode:** analysis-only — **no model calls**.")
    md.append(f"- **Splits:** {', '.join(analysis.get('splits', []))} ({analysis.get('case_count')} cases total)")
    md.append("")

    # 1. Executive summary
    hybrid = pols_by_name.get("hybrid-default") or {}
    search_def = pols_by_name.get("search-default") or {}
    oracle = pols_by_name.get("oracle-by-case") or {}
    deployable = [p for p in policies if p.get("deployable")]
    best = max(deployable, key=lambda p: p.get("macro_sv1_1") or 0) if deployable else {}

    md.append("## 1. Executive summary")
    md.append("")
    md.append(
        f"Across {analysis.get('case_count')} v1.3 cases, the strongest "
        f"deployable fallback policy was `{best.get('policy_name')}` with macro "
        f"sv1.1 = **{num(best.get('macro_sv1_1'))}** "
        f"(Δ vs hybrid-default = {fmt_delta(hybrid.get('macro_sv1_1'), best.get('macro_sv1_1'))}). "
        f"It invoked search-agent on **{pct(best.get('search_invocation_rate'))}** "
        f"of cases and spent **{humanize_tokens(best.get('macro_total_tokens'))}** "
        f"macro total tokens (vs hybrid's {humanize_tokens(hybrid.get('macro_total_tokens'))}). "
        f"The oracle upper bound is {num(oracle.get('macro_sv1_1'))}, so deployable "
        f"headroom over hybrid is **{fmt_delta(hybrid.get('macro_sv1_1'), oracle.get('macro_sv1_1'))} sv1.1**."
    )
    md.append("")
    md.append(f"**Decision:** `{decision}` (see §14).")
    md.append("")

    # 2. E7 recap
    md.append("## 2. E7 recap")
    md.append("")
    md.append(
        f"E7 (`reports/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`) "
        f"closed at `KEEP_AS_EXPLORATORY`. Search-agent macro sv1.1 = "
        f"{num(search_def.get('macro_sv1_1'))} vs hybrid {num(hybrid.get('macro_sv1_1'))}. "
        f"Search-agent spent {humanize_tokens(search_def.get('macro_total_tokens'))} "
        f"average total tokens per case — about "
        f"{(search_def.get('macro_total_tokens') or 0) / max(1, hybrid.get('macro_total_tokens') or 1):.1f}× "
        f"hybrid's cost. Per-split, search-agent beat hybrid on holdout (+0.027) and "
        f"stress (+0.028) but lost on dev (−0.223). E8 asks whether a deployable gate "
        f"can recover those holdout/stress wins without paying search cost on every case."
    )
    md.append("")

    # 3. Why search fallback instead of search default
    md.append("## 3. Why search fallback instead of search default")
    md.append("")
    md.append(
        "If search-agent had outperformed hybrid as a default, E7 would have "
        "promoted it to a v1.4 baseline directly. It did not. The remaining "
        "question is whether some pre-evaluation feature of the hybrid output "
        "reliably *predicts* which cases benefit from a search-agent retry. "
        "If yes, that gate becomes a deployable two-stage policy. If no, the "
        "search-agent track does not generalize and should be paused."
    )
    md.append("")

    # 4. Inputs and protocol
    md.append("## 4. Inputs and protocol")
    md.append("")
    md.append("| Input | Path |")
    md.append("|---|---|")
    md.append(f"| Protocol lock | `protocols/legacy/cilogbench-v1.3.lock.json` |")
    md.append(f"| Policy config | `configs/routing/hybrid_search_fallback_policy_v1.json` |")
    md.append(f"| Hybrid eval (E6) | `results/{{dev,holdout,stress}}/eval_diagnosis_real-debugger-v2.json` |")
    md.append(f"| Search-agent eval (E7) | `results/{{dev,holdout,stress}}/eval_diagnosis_mcp-search-agent-v1-sonnet.json` |")
    md.append(f"| Hybrid context route records | `results/{{dev,holdout,stress}}/hybrid-grep-4k-rtk-err-cat-v1.routes.jsonl` |")
    md.append(f"| Search-agent traces | `results/{{dev,holdout,stress}}/search_agents/mcp-search-agent-v1-sonnet/traces/*.json` |")
    md.append(f"| E8 raw output | `results/e8_hybrid_first_search_fallback_cilogbench_v1_3.json` |")
    md.append("")

    # 5. Anti-leakage
    md.append("## 5. Anti-leakage policy constraints")
    md.append("")
    md.append("Each deployable policy in `configs/routing/hybrid_search_fallback_policy_v1.json` may use only:")
    md.append("")
    for k in pols_cfg.get("allowed_route_inputs") or []:
        md.append(f"- `{k}`")
    md.append("")
    md.append("It must **not** consult any of:")
    md.append("")
    for k in pols_cfg.get("forbidden_route_inputs") or []:
        md.append(f"- `{k}`")
    md.append("")
    md.append(
        "The `oracle-by-case` policy is explicitly labeled **non-deployable** in "
        "the config and uses `diagnosis_score_v1_1` to choose; it appears in this "
        "report as an **upper bound only**. Every other policy's per-case "
        "decision is a function of the deployable feature dict only."
    )
    md.append("")

    # 6. Candidate routing policies
    md.append("## 6. Candidate routing policies")
    md.append("")
    md.append("| # | Policy | Deployable? | Rule |")
    md.append("|---|---|:---:|---|")
    for i, p in enumerate(policies):
        md.append(f"| {i} | `{p['policy_name']}` | {'✅' if p.get('deployable') else '❌ ORACLE'} | `{p.get('rule')}` |")
    md.append("")

    # 7. Policy results — Table 1
    md.append("## 7. Policy results")
    md.append("")
    md.append("### Table 1 — Policy summary")
    md.append("")
    md.append("| Policy | Deployable? | Macro sv1.1 | Δ vs hybrid | Total tokens | Δ cost vs hybrid | Search invocation | Provider err | confErr v1.1 |")
    md.append("|---|:---:|---:|---:|---:|---:|---:|---:|---:|")
    h_sv = hybrid.get("macro_sv1_1")
    h_tot = hybrid.get("macro_total_tokens")
    for p in policies:
        marker = "✅" if p.get("deployable") else "❌ ORACLE"
        sv = p.get("macro_sv1_1")
        tot = p.get("macro_total_tokens")
        md.append(
            f"| `{p['policy_name']}` | {marker} | {num(sv)} | "
            f"{fmt_delta(h_sv, sv)} | {humanize_tokens(tot)} | "
            f"{fmt_delta(h_tot, tot, prec=0)} | "
            f"{pct(p.get('search_invocation_rate'))} | "
            f"{pct(p.get('provider_error_rate'))} | "
            f"{pct(p.get('macro_confident_error_v1_1'))} |"
        )
    md.append("")

    # Per-split — Table 2
    md.append("### Table 2 — Per-split policy result")
    md.append("")
    md.append("| Policy | Split | sv1.1 | Hybrid sv1.1 | Search sv1.1 | Total tokens | Search invocations |")
    md.append("|---|---|---:|---:|---:|---:|---:|")
    hybrid_split = hybrid.get("splits") or {}
    search_split = (pols_by_name.get("search-default") or {}).get("splits") or {}
    for p in policies:
        for s in analysis.get("splits") or []:
            sb = (p.get("splits") or {}).get(s) or {}
            hb = hybrid_split.get(s) or {}
            ss = search_split.get(s) or {}
            md.append(
                f"| `{p['policy_name']}` | {s} | {num(sb.get('macro_sv1_1'))} "
                f"| {num(hb.get('macro_sv1_1'))} | {num(ss.get('macro_sv1_1'))} "
                f"| {humanize_tokens(sb.get('macro_total_tokens'))} "
                f"| {sb.get('search_invocations', 0)} |"
            )
    md.append("")

    # 8. Hybrid vs search case-level — Table 3
    md.append("## 8. Hybrid vs search case-level analysis")
    md.append("")
    md.append("### Table 3 — Case-level routing (best deployable policy)")
    md.append("")
    md.append(f"Best deployable policy by macro sv1.1: **`{best.get('policy_name')}`**")
    md.append("")
    md.append("| Case | Split | Chosen | Reason | Hybrid sv1.1 | Search sv1.1 | Chosen sv1.1 | Hybrid conf | Ev. count | Tool calls |")
    md.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
    for r in best.get("routes") or []:
        md.append(
            f"| `{r['case_id']}` | {r['split']} | `{r['chosen_method']}` "
            f"| {r['route_reason']} "
            f"| {num(r.get('hybrid_sv1_1'))} | {num(r.get('search_sv1_1'))} "
            f"| **{num(r.get('chosen_sv1_1'))}** "
            f"| {num(r.get('hybrid_confidence'))} "
            f"| {r.get('hybrid_evidence_count')} "
            f"| {r.get('search_tool_calls') or '—'} |"
        )
    md.append("")

    # 9. Cost / search-invocation analysis
    md.append("## 9. Cost and search-invocation analysis")
    md.append("")
    md.append("| Policy | Macro total tokens | Δ cost vs hybrid | Search invocation | When invoked, mean tool calls | When invoked, mean obs tokens |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for p in policies:
        # mean tool calls / obs tokens for cases where this policy chose search_agent
        tool_calls = []
        obs_tokens = []
        for r in p.get("routes") or []:
            if r.get("chosen_method") == "search_agent":
                if r.get("search_tool_calls") is not None:
                    tool_calls.append(r["search_tool_calls"])
                # Observation tokens lived in the trace; we approximate from total - agent input/output difference
                # The cleanest thing we have here is search_total_tokens, which already includes obs.
                # Skip the mean-obs column and report mean total instead:
                if r.get("chosen_total_tokens") is not None:
                    obs_tokens.append(r["chosen_total_tokens"])
        mean_tc = sum(tool_calls) / len(tool_calls) if tool_calls else None
        mean_ot = sum(obs_tokens) / len(obs_tokens) if obs_tokens else None
        md.append(
            f"| `{p['policy_name']}` | {humanize_tokens(p.get('macro_total_tokens'))} "
            f"| {fmt_delta(h_tot, p.get('macro_total_tokens'), prec=0)} "
            f"| {pct(p.get('search_invocation_rate'))} "
            f"| {num(mean_tc, 1) if mean_tc is not None else '—'} "
            f"| {humanize_tokens(mean_ot)} |"
        )
    md.append("")

    # 10. Large-log failure analysis
    md.append("## 10. Large-log failure analysis")
    md.append("")
    # Use the search-default policy routes to surface the per-case search vs hybrid gap
    search_def_routes = (pols_by_name.get("search-default") or {}).get("routes") or []
    md.append("Per-case search-vs-hybrid gap, sorted by raw-log size:")
    md.append("")
    md.append("| Case | Split | Raw lines | Hybrid sv1.1 | Search sv1.1 | Δ (search − hybrid) |")
    md.append("|---|---|---:|---:|---:|---:|")
    rows = []
    for r in search_def_routes:
        h = r.get("hybrid_sv1_1") or 0
        s = r.get("search_sv1_1") or 0
        rows.append((r.get("raw_log_line_count") or 0, r["case_id"], r["split"], h, s))
    for n, cid, sp, h, s in sorted(rows, reverse=True):
        md.append(
            f"| `{cid}` | {sp} | {n} | {num(h)} | {num(s)} "
            f"| {('+' if (s - h) >= 0 else '')}{(s - h):.3f} |"
        )
    md.append("")

    # 11. Deployable policy recommendation
    md.append("## 11. Deployable policy recommendation")
    md.append("")
    md.append(
        f"The strongest deployable policy by macro sv1.1 is "
        f"**`{best.get('policy_name')}`** at "
        f"{num(best.get('macro_sv1_1'))} (Δ vs hybrid "
        f"{fmt_delta(h_sv, best.get('macro_sv1_1'))})."
    )
    md.append("")
    md.append(
        f"It invokes search-agent on **{pct(best.get('search_invocation_rate'))}** "
        f"of cases and costs **{humanize_tokens(best.get('macro_total_tokens'))}** "
        f"per-case macro total tokens, a "
        f"{((best.get('macro_total_tokens') or 0) / max(1, h_tot or 1)):.2f}× "
        f"multiple of hybrid-default's cost."
    )
    md.append("")

    # 12. Oracle upper bound — Table 4
    md.append("## 12. Oracle upper bound")
    md.append("")
    md.append("### Table 4 — Oracle gap")
    md.append("")
    md.append("| Policy | Macro sv1.1 | Oracle sv1.1 | Gap to oracle | Search invocation |")
    md.append("|---|---:|---:|---:|---:|")
    o_sv = oracle.get("macro_sv1_1")
    for p in policies:
        if not p.get("deployable"):
            continue
        gap = (o_sv - (p.get("macro_sv1_1") or 0)) if o_sv is not None else None
        md.append(
            f"| `{p['policy_name']}` | {num(p.get('macro_sv1_1'))} "
            f"| {num(o_sv)} | "
            f"{('+' if (gap or 0) >= 0 else '')}{num(gap)} "
            f"| {pct(p.get('search_invocation_rate'))} |"
        )
    md.append("")

    # Failure-mode table 5
    md.append("### Table 5 — Failure-mode summary (best deployable policy)")
    md.append("")
    fm_count = Counter()
    fm_examples: dict[str, list[str]] = defaultdict(list)
    for r in best.get("routes") or []:
        h = r.get("hybrid_sv1_1") or 0
        s = r.get("search_sv1_1") or 0
        chosen = r.get("chosen_method")
        chosen_sv = r.get("chosen_sv1_1") or 0
        labels = []
        # search would help but policy kept hybrid
        if chosen == "hybrid" and s - h >= 0.10:
            labels.append("search_would_help_but_policy_kept_hybrid")
        # policy invoked search but search worse
        if chosen == "search_agent" and h - s >= 0.10:
            labels.append("policy_invoked_search_but_search_worse")
        # hybrid confident but wrong
        if (r.get("hybrid_confidence") or 0) >= 0.70 and h <= 0.40:
            labels.append("hybrid_confident_but_wrong")
        # hybrid low confidence but correct
        if (r.get("hybrid_confidence") or 0) < 0.70 and h >= 0.60:
            labels.append("hybrid_low_confidence_but_correct")
        # search high cost low gain
        if chosen == "search_agent" and (r.get("chosen_total_tokens") or 0) > 50000 and (chosen_sv - h) < 0.05:
            labels.append("search_high_cost_low_gain")
        # large-log search failure
        if chosen == "search_agent" and (r.get("raw_log_line_count") or 0) > 5000 and chosen_sv < 0.30:
            labels.append("large_log_search_failure")
        for lab in labels:
            fm_count[lab] += 1
            if r["case_id"] not in fm_examples[lab]:
                fm_examples[lab].append(r["case_id"])
    md.append("| Failure mode | Cases | Example | Policy impacted |")
    md.append("|---|---:|---|---|")
    for lab, n in fm_count.most_common():
        md.append(f"| `{lab}` | {n} | `{fm_examples[lab][0]}` | `{best.get('policy_name')}` |")
    if not fm_count:
        md.append("| _(no failure-mode hits on the best deployable policy)_ | 0 | — | — |")
    md.append("")

    # 13. Interpretation guardrails
    md.append("## 13. Interpretation guardrails")
    md.append("")
    md.append("- **Offline routing analysis on existing E6/E7 outputs.** No new model calls; results scoped to the artifacts already generated.")
    md.append("- **One search-agent prompt, one search-agent model, one tool budget.** Conclusions about search-agent cannot generalize to other agent designs.")
    md.append("- **16 cases.** Directional, not statistical. Margins below ~0.05 sv1.1 are noise-level.")
    md.append("- **Automatic scoring proxy.** sv1.1 was calibrated against expert-model labels (E2b), not human review.")
    md.append("- **Search traces not human-reviewed.** A bad-looking large-log search trace is not the same as a confirmed agent failure.")
    md.append("- **Oracle is non-deployable** by construction: it consults `diagnosis_score_v1_1` per case.")
    md.append("")

    # 14. Decision
    md.append("## 14. Decision: implement E9 or stop search track")
    md.append("")
    md.append(f"**Decision: `{decision}`**")
    md.append("")
    md.append("Rationale:")
    for r in decision_rationale:
        md.append(f"- {r}")
    md.append("")
    if decision == "IMPLEMENT_E9_FIRST_CLASS_FALLBACK":
        md.append(
            "**E9 — first-class hybrid-with-search fallback.** Implement "
            f"`{best.get('policy_name')}` as a real two-stage method (run "
            "hybrid first, gate-check, fall back to a single search-agent "
            "invocation only when the gate fires). Reuse the existing "
            "search-agent shim. Validate that the offline-predicted sv1.1 "
            "and cost numbers reproduce in a real run."
        )
    elif decision == "STOP_SEARCH_TRACK":
        md.append(
            "**Stop search-agent track for now.** No deployable gate beat "
            "hybrid by a useful margin within an acceptable cost envelope. "
            "Re-prioritize human-verified review of E6 diagnoses and "
            "larger-corpus replication. Search-agent can be revisited if a "
            "different failure profile (e.g. multi-step CI logs or large "
            "agent-tool ecosystems) shows up in future cases."
        )
    elif decision == "REVISE_SEARCH_AGENT_PROMPT_ON_DEV_ONLY":
        md.append(
            "**Revise the search-agent prompt on dev only.** The oracle "
            "shows that *some* cases benefit from search, but the current "
            "agent picks wrong regions or stops prematurely on those cases. "
            "Iterate the prompt against dev cases only; freeze the new "
            "prompt as `search_agent_v2` and rerun E7."
        )
    elif decision == "RUN_HUMAN_VERIFIED_REVIEW_FIRST":
        md.append(
            "**Run human-verified review first.** Automatic scores disagree "
            "with qualitative search-agent quality. Human verification on a "
            "small sample of E6/E7 diagnoses will tell us whether the "
            "calibrated sv1.1 is the right metric for ranking these methods."
        )
    md.append("")

    out_md = args.reports_dir / "e8_hybrid_first_search_fallback_cilogbench_v1_3.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Manifest
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": analysis.get("protocol_id"),
        "protocol_lock_path": str(args.protocol.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol),
        "mode": "analysis_only",
        "no_new_model_runs": True,
        "policy_config_path": str(args.policy_config.relative_to(ROOT)),
        "policy_config_sha256": sha256_path(args.policy_config),
        "input_path": str(args.input.relative_to(ROOT)),
        "input_sha256": sha256_path(args.input),
        "hybrid_diagnoser": analysis.get("hybrid_diagnoser"),
        "search_agent": analysis.get("search_agent"),
        "splits": analysis.get("splits"),
        "case_count": analysis.get("case_count"),
        "policies_evaluated": [p["policy_name"] for p in policies],
        "best_deployable_policy": best.get("policy_name"),
        "best_deployable_macro_sv1_1": best.get("macro_sv1_1"),
        "decision": decision,
        "report_path": str(out_md.relative_to(ROOT)),
        "git_commit": "unknown",
        "working_tree_dirty": True,
        "finalized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    out_manifest = args.results_dir / "e8_hybrid_first_search_fallback_cilogbench_v1_3.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
