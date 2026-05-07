"""
E8 — analyze hybrid-first / search-fallback routing policies offline.

Reads existing E6 (real-debugger-v2 over hybrid) + E7 (search-agent)
outputs and computes per-policy macro sv1.1, macro total tokens,
search-invocation rate, provider-error rate, and per-case route
records. Anti-leakage: the per-case route decision uses only the
deployable signals declared in the policy config; scoring data is
attached AFTER routing.

Usage:
    python tools/analyze_search_fallback_routing.py \
        --protocol protocols/cilogbench-v1.3.lock.json \
        --hybrid-diagnoser real-debugger-v2 \
        --search-agent mcp-search-agent-v1-sonnet \
        --splits dev,holdout,stress
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E8-hybrid-first-search-fallback-analysis-v1"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def macro(values):
    pool = [v for v in values if v is not None]
    return round(sum(pool) / len(pool), 4) if pool else None


# ---------- Per-case feature extraction ----------

def features_for_case(
    *,
    case_id: str,
    split: str,
    cases_dir: Path,
    hybrid_jsonl_row: dict | None,
    hybrid_eval_case: dict | None,
    hybrid_method_row: dict | None,
    hybrid_route_row: dict | None,
    search_jsonl_row: dict | None,
    search_eval_case: dict | None,
    search_trace: dict | None,
) -> dict:
    """Build a `case_features` dict containing both deployable inputs (used
    by routing) and scoring data (used only for evaluation)."""
    raw_p = cases_dir / split / case_id / "raw.log"
    case_p = cases_dir / split / case_id / "case.json"
    raw_lines = 0
    raw_bytes = 0
    if raw_p.exists():
        text = raw_p.read_text(encoding="utf-8", errors="replace")
        raw_lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        raw_bytes = len(text.encode("utf-8"))
    case_meta = load_json(case_p) if case_p.exists() else {}
    safe_meta_keys = ("framework", "repo", "workflow_name", "job_name")

    # ----- HYBRID side -----
    hybrid_diag_body = (hybrid_jsonl_row or {}) or {}
    # The diagnosis JSONL row is shaped like run_diagnosis.py: top-level fields
    # for summary/root_cause/evidence/etc.
    h_conf = hybrid_diag_body.get("confidence")
    h_cat = hybrid_diag_body.get("root_cause_category")
    h_root = hybrid_diag_body.get("root_cause", "") or ""
    h_evidence = list(hybrid_diag_body.get("evidence") or [])
    h_files = list(hybrid_diag_body.get("relevant_files") or [])
    h_tests = list(hybrid_diag_body.get("relevant_tests") or [])
    h_pe = ((hybrid_diag_body.get("metadata") or {}).get("provider_error")
            or (hybrid_eval_case or {}).get("provider_error"))
    # The hybrid context route info comes from hybrid_route_row (the
    # `<hybrid>.routes.jsonl` record) — which method was selected for this
    # case, and that method's context tokens.
    h_selected = (hybrid_route_row or {}).get("selected_method")
    h_ctx_tokens = ((hybrid_method_row or {}).get("output_byte_size") or 0) // 4

    # Verify each evidence quote against the hybrid CONTEXT FILE that the
    # debugger actually saw (the hybrid context wraps the chosen method's
    # output with a small metadata header). Anti-leakage: this never
    # consults ground_truth.json.
    h_ctx_path = ROOT / ((hybrid_method_row or {}).get("context_path", ""))
    h_ctx_text = ""
    if h_ctx_path.exists():
        h_ctx_text = h_ctx_path.read_text(encoding="utf-8", errors="replace")
    h_evidence_in_ctx = 0
    for ev in h_evidence:
        if isinstance(ev, dict):
            quote = (ev.get("quote") or "").strip()
            if quote and quote in h_ctx_text:
                h_evidence_in_ctx += 1

    # ----- SEARCH-AGENT side -----
    s_pe = ((search_jsonl_row or {}).get("metadata") or {}).get("provider_error") \
            or (search_eval_case or {}).get("provider_error")
    s_be = ((search_jsonl_row or {}).get("metadata") or {}).get("budget_exhausted", False)
    s_tool_calls = ((search_jsonl_row or {}).get("metadata") or {}).get("tool_call_count")
    if s_tool_calls is None and search_trace:
        s_tool_calls = (search_trace.get("usage") or {}).get("tool_call_count")

    return {
        "case_id": case_id,
        "split": split,
        # ---- DEPLOYABLE features (allowed for routing) ----
        "deploy": {
            "hybrid_confidence": float(h_conf) if h_conf is not None else None,
            "hybrid_category": h_cat,
            "hybrid_root_cause_text": h_root,
            "hybrid_evidence_count": len(h_evidence),
            "hybrid_evidence_in_context_count": h_evidence_in_ctx,
            "hybrid_relevant_files_count": len(h_files),
            "hybrid_relevant_tests_count": len(h_tests),
            "hybrid_selected_method": h_selected,
            "hybrid_context_token_estimate": int(h_ctx_tokens),
            "hybrid_provider_error": h_pe,
            "raw_log_line_count": raw_lines,
            "raw_log_byte_size": raw_bytes,
            **{k: case_meta.get(k) for k in safe_meta_keys if k in case_meta},
        },
        # ---- SCORING (NEVER consulted by the router; attached after routing) ----
        "scoring": {
            "hybrid_sv1_1": (hybrid_eval_case or {}).get("diagnosis_score_v1_1"),
            "hybrid_sv1": (hybrid_eval_case or {}).get("diagnosis_score_v1"),
            "hybrid_confErr_v1_1": (hybrid_eval_case or {}).get("confident_error_v1_1"),
            "hybrid_total_tokens": (
                int((hybrid_eval_case or {}).get("context_tokens") or 0)
                + int((hybrid_eval_case or {}).get("diagnosis_tokens") or 0)
            ),
            "search_sv1_1": (search_eval_case or {}).get("diagnosis_score_v1_1"),
            "search_sv1": (search_eval_case or {}).get("diagnosis_score_v1"),
            "search_confErr_v1_1": (search_eval_case or {}).get("confident_error_v1_1"),
            "search_total_tokens": (
                int(((search_jsonl_row or {}).get("metadata") or {}).get("total_agent_tokens_estimate")
                    or (int((search_eval_case or {}).get("context_tokens") or 0)
                        + int((search_eval_case or {}).get("diagnosis_tokens") or 0)))
            ),
            "search_provider_error": s_pe,
            "search_budget_exhausted": bool(s_be),
            "search_tool_calls": int(s_tool_calls) if s_tool_calls is not None else None,
        },
    }


# ---------- Policy decision functions (only `deploy` features) ----------

def policy_choose(policy: dict, deploy: dict) -> tuple[str, str]:
    """Return (chosen_method, route_reason) based ONLY on deploy features."""
    rule = policy.get("rule")
    if rule == "always_choose_hybrid":
        return "hybrid", "policy_default_hybrid"
    if rule == "always_choose_search_agent":
        return "search_agent", "policy_default_search"
    if rule == "hybrid_if_confidence_geq":
        thr = float(policy.get("threshold") or 0.0)
        c = deploy.get("hybrid_confidence")
        if c is not None and c >= thr:
            return "hybrid", f"hybrid_confidence>={thr}"
        return "search_agent", f"hybrid_confidence<{thr}"
    if rule == "hybrid_if_known":
        c = deploy.get("hybrid_confidence")
        cat = deploy.get("hybrid_category")
        root = (deploy.get("hybrid_root_cause_text") or "").strip().lower()
        min_c = float(policy.get("min_confidence", 0.50))
        if (cat and cat != "unknown" and root and root != "unknown"
                and c is not None and c >= min_c):
            return "hybrid", "hybrid_known_and_confident"
        return "search_agent", "hybrid_unknown_or_low_confidence"
    if rule == "hybrid_if_evidence_in_context":
        ec = int(deploy.get("hybrid_evidence_count") or 0)
        ec_in_ctx = int(deploy.get("hybrid_evidence_in_context_count") or 0)
        c = deploy.get("hybrid_confidence")
        min_c = float(policy.get("min_confidence", 0.50))
        min_ec = int(policy.get("min_evidence_count", 1))
        if (ec >= min_ec and ec_in_ctx >= 1 and c is not None and c >= min_c):
            return "hybrid", "hybrid_confident_with_evidence_in_context"
        return "search_agent", "hybrid_evidence_missing_or_low_confidence"
    if rule == "hybrid_if_grep_selected":
        sel = deploy.get("hybrid_selected_method")
        if sel == "grep":
            return "hybrid", "hybrid_used_grep_primary"
        return "search_agent", f"hybrid_used_fallback={sel}"
    if rule == "large_log_then_hybrid_else_confidence_gate":
        n = int(deploy.get("raw_log_line_count") or 0)
        thr = int(policy.get("log_line_threshold", 5000))
        c = deploy.get("hybrid_confidence")
        ct = float(policy.get("confidence_threshold", 0.70))
        if n > thr:
            return "hybrid", f"raw_log_lines>{thr}"
        if c is not None and c < ct:
            return "search_agent", f"raw_log_small_low_confidence<{ct}"
        return "hybrid", f"raw_log_small_confident_geq_{ct}"
    if rule == "argmax_sv1_1":
        # ORACLE: this rule is NOT deployable. We make this explicit at call
        # site and only execute it when the policy is marked deployable=False.
        raise RuntimeError("oracle policy must be evaluated via oracle_choose, not policy_choose")
    raise ValueError(f"unknown rule: {rule!r}")


def oracle_choose(scoring: dict) -> tuple[str, str]:
    h = scoring.get("hybrid_sv1_1") or 0
    s = scoring.get("search_sv1_1") or 0
    if h >= s:
        return "hybrid", "oracle_hybrid_geq_search"
    return "search_agent", "oracle_search_gt_hybrid"


def evaluate_policy(policy: dict, all_features: list[dict]) -> dict:
    routes: list[dict] = []
    for f in all_features:
        deploy = f["deploy"]
        scoring = f["scoring"]
        if policy.get("deployable", True):
            chosen, reason = policy_choose(policy, deploy)
        else:
            chosen, reason = oracle_choose(scoring)
        # Map chosen_method -> sv1_1 / total_tokens / confErr / pe
        chosen_sv = scoring.get(f"{'hybrid' if chosen == 'hybrid' else 'search'}_sv1_1")
        chosen_tt = scoring.get(f"{'hybrid' if chosen == 'hybrid' else 'search'}_total_tokens")
        chosen_ce = scoring.get(f"{'hybrid' if chosen == 'hybrid' else 'search'}_confErr_v1_1")
        chosen_pe = scoring.get("hybrid_provider_error" if chosen == "hybrid"
                                  else "search_provider_error")
        routes.append({
            "case_id": f["case_id"],
            "split": f["split"],
            "policy_name": policy["policy_name"],
            "chosen_method": chosen,
            "route_reason": reason,
            "hybrid_confidence": deploy.get("hybrid_confidence"),
            "hybrid_category": deploy.get("hybrid_category"),
            "hybrid_evidence_count": deploy.get("hybrid_evidence_count"),
            "hybrid_evidence_in_context_count": deploy.get("hybrid_evidence_in_context_count"),
            "hybrid_relevant_files_count": deploy.get("hybrid_relevant_files_count"),
            "hybrid_selected_method": deploy.get("hybrid_selected_method"),
            "hybrid_provider_error": deploy.get("hybrid_provider_error"),
            "raw_log_line_count": deploy.get("raw_log_line_count"),
            "search_tool_calls": scoring.get("search_tool_calls"),
            "search_provider_error": scoring.get("search_provider_error"),
            "search_budget_exhausted": scoring.get("search_budget_exhausted"),
            "chosen_sv1_1": chosen_sv,
            "hybrid_sv1_1": scoring.get("hybrid_sv1_1"),
            "search_sv1_1": scoring.get("search_sv1_1"),
            "chosen_total_tokens": chosen_tt,
            "chosen_confident_error_v1_1": chosen_ce,
        })

    # Per-split aggregates
    splits_out: dict[str, dict] = defaultdict(lambda: {
        "case_count": 0,
        "search_invocations": 0,
        "sv1_1": [],
        "total_tokens": [],
        "confErr_v1_1": [],
        "provider_errors": 0,
    })
    n = len(routes)
    n_search = 0
    sv11_all = []
    tot_all = []
    ce_all = []
    pe_all = 0
    for r in routes:
        s = r["split"]
        splits_out[s]["case_count"] += 1
        if r["chosen_method"] == "search_agent":
            n_search += 1
            splits_out[s]["search_invocations"] += 1
        if r["chosen_sv1_1"] is not None:
            splits_out[s]["sv1_1"].append(r["chosen_sv1_1"])
            sv11_all.append(r["chosen_sv1_1"])
        if r["chosen_total_tokens"] is not None:
            splits_out[s]["total_tokens"].append(r["chosen_total_tokens"])
            tot_all.append(r["chosen_total_tokens"])
        if r["chosen_confident_error_v1_1"] is not None:
            splits_out[s]["confErr_v1_1"].append(1 if r["chosen_confident_error_v1_1"] else 0)
            ce_all.append(1 if r["chosen_confident_error_v1_1"] else 0)
        # provider error attribution: chosen-side
        if r["chosen_method"] == "hybrid" and r["hybrid_provider_error"]:
            splits_out[s]["provider_errors"] += 1
            pe_all += 1
        elif r["chosen_method"] == "search_agent" and r["search_provider_error"]:
            splits_out[s]["provider_errors"] += 1
            pe_all += 1

    splits_block: dict[str, dict] = {}
    for s, d in splits_out.items():
        splits_block[s] = {
            "case_count": d["case_count"],
            "search_invocations": d["search_invocations"],
            "search_invocation_rate": (
                round(d["search_invocations"] / d["case_count"], 4)
                if d["case_count"] else None
            ),
            "macro_sv1_1": macro(d["sv1_1"]),
            "macro_total_tokens":
                round(sum(d["total_tokens"]) / len(d["total_tokens"]), 1)
                if d["total_tokens"] else None,
            "macro_confident_error_v1_1":
                round(sum(d["confErr_v1_1"]) / len(d["confErr_v1_1"]), 4)
                if d["confErr_v1_1"] else None,
            "provider_errors": d["provider_errors"],
        }

    return {
        "policy_name": policy["policy_name"],
        "deployable": policy.get("deployable", True),
        "rule": policy.get("rule"),
        "macro_sv1_1": macro(sv11_all),
        "macro_total_tokens":
            round(sum(tot_all) / len(tot_all), 1) if tot_all else None,
        "macro_confident_error_v1_1":
            round(sum(ce_all) / len(ce_all), 4) if ce_all else None,
        "provider_error_rate": round(pe_all / n, 4) if n else None,
        "search_invocation_rate": round(n_search / n, 4) if n else None,
        "splits": splits_block,
        "routes": routes,
    }


# ---------- Build per-case features once for the whole run ----------

def collect_features(
    *,
    splits: list[str],
    hybrid_diagnoser: str,
    search_agent: str,
    cases_dir: Path,
    results_dir: Path,
    hybrid_method: str,
) -> list[dict]:
    out: list[dict] = []
    for s in splits:
        # Hybrid eval (per-case scoring)
        h_eval_p = results_dir / s / f"eval_diagnosis_{hybrid_diagnoser}.json"
        h_eval = load_json(h_eval_p) if h_eval_p.exists() else {}
        h_method_block = next((mb for mb in h_eval.get("methods", [])
                                if mb["context_method"] == hybrid_method), {})
        h_eval_cases = {c["case_id"]: c for c in h_method_block.get("cases", [])}

        # Hybrid diagnosis JSONL (per-case body)
        h_diag_jsonl = results_dir / s / "diagnoses" / hybrid_diagnoser / f"{hybrid_method}.jsonl"
        h_diag_rows = {r["case_id"]: r for r in load_jsonl(h_diag_jsonl)}

        # Hybrid context manifest jsonl (per-case selected method + context tokens)
        h_method_jsonl = results_dir / s / f"{hybrid_method}.jsonl"
        h_method_rows = {r["case_id"]: r for r in load_jsonl(h_method_jsonl)}

        # Hybrid route jsonl (selected_method)
        h_route_jsonl = results_dir / s / f"{hybrid_method}.routes.jsonl"
        h_route_rows = {r["case_id"]: r for r in load_jsonl(h_route_jsonl)}

        # Search-agent eval (per-case scoring)
        s_eval_p = results_dir / s / f"eval_diagnosis_{search_agent}.json"
        s_eval = load_json(s_eval_p) if s_eval_p.exists() else {}
        s_method_block = next((mb for mb in s_eval.get("methods", [])
                                if mb["context_method"] == search_agent), {})
        s_eval_cases = {c["case_id"]: c for c in s_method_block.get("cases", [])}

        # Search-agent diagnosis JSONL (per-case body)
        s_diag_jsonl = results_dir / s / "diagnoses" / search_agent / f"{search_agent}.jsonl"
        s_diag_rows = {r["case_id"]: r for r in load_jsonl(s_diag_jsonl)}

        # Search-agent traces (for tool_call_count fallback if needed)
        traces_dir = results_dir / s / "search_agents" / search_agent / "traces"

        case_dirs = sorted(p for p in (cases_dir / s).iterdir() if p.is_dir())
        for cd in case_dirs:
            cid = cd.name
            trace = None
            tp = traces_dir / f"{cid}.json"
            if tp.exists():
                try:
                    trace = load_json(tp)
                except Exception:
                    trace = None
            f = features_for_case(
                case_id=cid, split=s, cases_dir=cases_dir,
                hybrid_jsonl_row=h_diag_rows.get(cid),
                hybrid_eval_case=h_eval_cases.get(cid),
                hybrid_method_row=h_method_rows.get(cid),
                hybrid_route_row=h_route_rows.get(cid),
                search_jsonl_row=s_diag_rows.get(cid),
                search_eval_case=s_eval_cases.get(cid),
                search_trace=trace,
            )
            out.append(f)
    return out


# ---------- main ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--hybrid-diagnoser", default="real-debugger-v2")
    ap.add_argument("--search-agent", default="mcp-search-agent-v1-sonnet")
    ap.add_argument("--hybrid-method", default="hybrid-grep-4k-rtk-err-cat-v1")
    ap.add_argument("--policy-config", type=Path,
                    default=ROOT / "configs" / "routing"
                            / "hybrid_search_fallback_policy_v1.json")
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "results" / "e8_hybrid_first_search_fallback_cilogbench_v1_3.json")
    args = ap.parse_args(argv)

    if not args.protocol.exists():
        print(f"ERROR: protocol not found: {args.protocol}", file=sys.stderr)
        return 1
    if not args.policy_config.exists():
        print(f"ERROR: policy config not found: {args.policy_config}", file=sys.stderr)
        return 1
    protocol = load_json(args.protocol)
    pol_cfg = load_json(args.policy_config)
    policies = pol_cfg.get("policies") or []
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]

    features = collect_features(
        splits=splits,
        hybrid_diagnoser=args.hybrid_diagnoser,
        search_agent=args.search_agent,
        cases_dir=args.cases_dir,
        results_dir=args.results_dir,
        hybrid_method=args.hybrid_method,
    )

    policy_results: list[dict] = []
    for pol in policies:
        policy_results.append(evaluate_policy(pol, features))

    out_obj = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": protocol.get("protocol_id"),
        "mode": "analysis_only",
        "hybrid_diagnoser": args.hybrid_diagnoser,
        "search_agent": args.search_agent,
        "hybrid_method": args.hybrid_method,
        "splits": splits,
        "case_count": len(features),
        "allowed_route_inputs": pol_cfg.get("allowed_route_inputs", []),
        "forbidden_route_inputs": pol_cfg.get("forbidden_route_inputs", []),
        "policies": policy_results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {args.out.relative_to(ROOT)}")
    print(f"  cases: {len(features)} | policies: {len(policy_results)}")
    for p in policy_results:
        marker = "ORACLE" if not p["deployable"] else "      "
        print(f"  {marker}  {p['policy_name']:<50} sv1.1={p['macro_sv1_1']!s:<7} "
              f"total_tok={p['macro_total_tokens']!s:<8} "
              f"search_rate={p['search_invocation_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
