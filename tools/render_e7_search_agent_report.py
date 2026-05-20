"""
E7 search-agent report renderer.

Reads:
  protocols/legacy/cilogbench-v1.3.lock.json
  configs/search_agents/<agent>.json
  prompts/search_agent_v1.md
  results/<split>/search_agents/<agent>/traces/<case_id>.json
  results/<split>/diagnoses/<agent>/<case_id>.json
  results/<split>/eval_diagnosis_<agent>.json
  results/<split>/eval_diagnosis_real-debugger-v2.json   (E6 comparison)
  results/<split>/eval_diagnosis_real-debugger-v1.json   (E5 comparison fallback)

Writes:
  reports/e7_mcp_search_agent_cilogbench_v1_3_<agent>.md
  results/e7_mcp_search_agent_cilogbench_v1_3_<agent>.manifest.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPERIMENT_ID = "E7-mcp-search-agent-v1"


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


def macro(values):
    pool = [v for v in values if v is not None]
    return round(sum(pool) / len(pool), 4) if pool else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path,
                    default=ROOT / "protocols" / "cilogbench-v1.3.lock.json")
    ap.add_argument("--agent-name", default="mcp-search-agent-v1-sonnet")
    ap.add_argument("--agent-config", type=Path, default=None,
                    help="Defaults to configs/search_agents/<agent>.json")
    ap.add_argument("--prompt", type=Path,
                    default=ROOT / "prompts" / "search_agent_v1.md")
    ap.add_argument("--comparison-diagnoser-v2", default="real-debugger-v2")
    ap.add_argument("--comparison-diagnoser-v1", default="real-debugger-v1")
    ap.add_argument("--splits", nargs="+", default=["dev", "holdout", "stress"])
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    agent_cfg_path = args.agent_config or (ROOT / "configs" / "search_agents" / f"{args.agent_name}.json")
    agent_cfg = load_json(agent_cfg_path)

    static_methods = ["raw", "tail", "grep", "rtk-err-cat", "rtk-log",
                      "llm-summary-v1-mock", "hybrid-grep-4k-rtk-err-cat-v1"]

    md: list[str] = []
    md.append(f"# E7 — MCP/Search-Agent Baseline on cilogbench-v1.3 ({args.agent_name})")
    md.append("")
    md.append(f"- **Experiment ID:** `{EXPERIMENT_ID}`")
    md.append(f"- **Protocol:** `cilogbench-v1.3` (SHA `{sha256_path(args.protocol)[:16]}…`)")
    md.append(f"- **Agent:** `{args.agent_name}` (Sonnet 4.6 via `claude -p`)")
    md.append(f"- **Mode:** end-to-end search agent (NOT a static context-provider baseline)")
    md.append(f"- **Tool budget:** "
              f"max_tool_calls={(agent_cfg.get('tool_budget') or {}).get('max_tool_calls')}, "
              f"max_total_observation_tokens={(agent_cfg.get('tool_budget') or {}).get('max_total_observation_tokens')}")
    md.append(f"- **Allowed tools:** {', '.join(f'`{t}`' for t in (agent_cfg.get('allowed_tools') or []))}")
    md.append(f"- **Primary score:** `diagnosis_score_v1_1` (E2b-calibrated; secondary = `diagnosis_score_v1`)")
    md.append("")

    # ---- Aggregate trace stats ----
    all_traces: list[dict] = []
    for s in args.splits:
        traces_dir = args.results_dir / s / "search_agents" / args.agent_name / "traces"
        if not traces_dir.is_dir():
            continue
        for p in sorted(traces_dir.glob("*.json")):
            try:
                all_traces.append(load_json(p))
            except Exception:
                continue

    # ---- Per-method macro sv1.1 (search-agent + comparison) ----
    def split_macros(diag: str) -> dict:
        out = {}
        for s in args.splits:
            ev_p = args.results_dir / s / f"eval_diagnosis_{diag}.json"
            ev = load_json(ev_p) if ev_p.exists() else {}
            out[s] = methods_in(ev)
        return out

    agent_macros = split_macros(args.agent_name)
    cmp_macros_v2 = split_macros(args.comparison_diagnoser_v2)
    cmp_macros_v1 = split_macros(args.comparison_diagnoser_v1)

    def agent_block(split: str) -> dict:
        return (agent_macros.get(split) or {}).get(args.agent_name) or {}

    def cmp_block(diag_macros, split: str, method: str) -> dict:
        return (diag_macros.get(split) or {}).get(method) or {}

    # ===== 1. Executive summary =====
    md.append("## 1. Executive summary")
    md.append("")
    sv11_per_split = []
    for s in args.splits:
        ab = agent_block(s)
        hb = cmp_block(cmp_macros_v2, s, "hybrid-grep-4k-rtk-err-cat-v1")
        sv11_per_split.append((s, ab.get("diagnosis_score_v1_1"),
                                hb.get("diagnosis_score_v1_1")))
    md.append("Per-split macro `diagnosis_score_v1_1`, search-agent vs. v1.3 hybrid (under Sonnet 4.6):")
    md.append("")
    md.append("| Split | search-agent sv1.1 | hybrid sv1.1 (v2) | Δ |")
    md.append("|---|---:|---:|---:|")
    for s, a_sv, h_sv in sv11_per_split:
        delta = (a_sv - h_sv) if (a_sv is not None and h_sv is not None) else None
        md.append(f"| {s} | {num(a_sv)} | {num(h_sv)} | "
                   f"{('+' if (delta or 0) >= 0 else '')}{num(delta)} |")
    md.append("")
    md.append(
        f"Across all {len(all_traces)} attempted cases, the search agent's "
        f"trace recorded its tool calls and observations under a fixed budget "
        f"({(agent_cfg.get('tool_budget') or {}).get('max_tool_calls')} max tool calls, "
        f"{(agent_cfg.get('tool_budget') or {}).get('max_total_observation_tokens')} max observation tokens)."
    )
    md.append("")

    # ===== 2. Why MCP/search-agent is different from static context =====
    md.append("## 2. Why MCP/search-agent is different from static context")
    md.append("")
    md.append(
        "Static context methods (`raw` / `tail` / `grep` / `rtk-*` / "
        "`hybrid-grep-4k-rtk-err-cat-v1`) compress the raw log **once**, then a "
        "fixed debugger reads that single context. The search agent, by contrast, "
        "starts only with safe metadata (no log content), then issues a sequence "
        "of bounded tool calls over the raw log and decides what to inspect "
        "based on intermediate observations. The cost model is therefore "
        "different — `final_context_tokens` for static methods becomes "
        "`observation_tokens_estimate + agent_input_tokens_estimate + "
        "agent_output_tokens_estimate` for the agent, summed across steps."
    )
    md.append("")

    # ===== 3. Protocol and model setup =====
    md.append("## 3. Protocol and model setup")
    md.append("")
    md.append("```text")
    md.append(f"protocol_lock         = {args.protocol.relative_to(ROOT)}")
    md.append(f"protocol_lock_sha256  = {sha256_path(args.protocol)}")
    md.append(f"agent_config          = {agent_cfg_path.relative_to(ROOT)}")
    md.append(f"agent_config_sha256   = {sha256_path(agent_cfg_path)}")
    md.append(f"agent_prompt          = {args.prompt.relative_to(ROOT)}")
    md.append(f"agent_prompt_sha256   = {sha256_path(args.prompt)}")
    md.append(f"primary_score         = diagnosis_score_v1_1")
    md.append(f"secondary_score       = diagnosis_score_v1")
    md.append("```")
    md.append("")

    # ===== 4. Tool set and budgets =====
    md.append("## 4. Tool set and budgets")
    md.append("")
    md.append("| Tool | Bounded by |")
    md.append("|---|---|")
    md.append("| `get_log_metadata` | (free) |")
    md.append("| `search_log` | `max_matches_per_search`, `before` ≤ 10, `after` ≤ 30 |")
    md.append("| `get_lines` | `max_ranges_per_get_lines`, `max_lines_per_get_lines` |")
    md.append("| `get_tail` | `max_lines_per_get_tail_or_head` (default 500) |")
    md.append("| `get_head` | `max_lines_per_get_tail_or_head` (default 500) |")
    md.append("| `find_error_blocks` | fixed regex; `max_blocks` ≤ 50 |")
    md.append("| `list_github_steps` | empty list when not detectable |")
    md.append("")
    md.append(
        "All observations are also subject to "
        f"`max_single_observation_tokens = {(agent_cfg.get('tool_budget') or {}).get('max_single_observation_tokens')}` "
        "and the cumulative `max_total_observation_tokens` budget."
    )
    md.append("")

    # ===== 5. Anti-leakage verification =====
    md.append("## 5. Anti-leakage verification")
    md.append("")
    md.append(
        "The agent payload is built from `cases/<split>/<case_id>/raw.log` and the "
        "safe-metadata allowlist (`case_id`, `repo`, `source`, `workflow_name`, "
        "`job_name`, `framework`). The runner does **not** open "
        "`ground_truth.json`, `case.json` fields outside the allowlist, "
        "`required_signals`, `evidence_spans`, `expected_diagnosis`, "
        "`results/<split>/eval_*.json`, or any `review/batches/*` label."
    )
    md.append("")
    # Source-level guard recap
    src = (ROOT / "tools" / "log_search_tools.py").read_text(encoding="utf-8")
    src += (ROOT / "tools" / "run_search_agent.py").read_text(encoding="utf-8")
    md.append("Source-level guard run on `tools/log_search_tools.py` + `tools/run_search_agent.py`:")
    md.append("")
    md.append("```text")
    for needle in ("ground_truth", "eval_diagnosis", "eval_hybrid",
                   "human_review", "required_signals", "evidence_spans",
                   "failure_category"):
        n = sum(1 for line in src.splitlines() if needle in line)
        md.append(f"{needle:<18}: {n} match(es) (only docstring/comment references are allowed)")
    md.append("```")
    md.append("")
    md.append(
        "The shim itself (`examples/search_agent_shim_claude_cli.py`) re-runs an "
        "AST-walk that fails any payload containing forbidden keys at any depth — "
        "this is a belt-and-suspenders check on the runner-built payload."
    )
    md.append("")

    # ===== 6. Per-split diagnosis metrics (Table 1) =====
    md.append("## 6. Per-split diagnosis metrics")
    md.append("")
    md.append("### Table 1 — Static vs search-agent quality")
    md.append("")
    md.append("| Method | Type | Split | Success | sv1.1 | CMS v1.1 | Crit Mention | Must Mention | confErr v1.1 | Abstention | Provider Errors |")
    md.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    # search-agent rows first
    for s in args.splits:
        ab = agent_block(s)
        if not ab:
            continue
        cases = ab.get("cases") or []
        pe = sum(1 for c in cases if c.get("provider_error"))
        md.append(
            f"| `{args.agent_name}` | search | {s} "
            f"| {pct(ab.get('diagnosis_success_rate'))} "
            f"| **{num(ab.get('diagnosis_score_v1_1'))}** "
            f"| {num(ab.get('macro_category_match_score_v1_1'))} "
            f"| {pct(ab.get('macro_critical_signal_mention_recall'))} "
            f"| {pct(ab.get('macro_must_mention_coverage'))} "
            f"| {pct(ab.get('confident_error_rate_v1_1'))} "
            f"| {pct(ab.get('abstention_rate'))} "
            f"| {pe} |"
        )
    # static-context rows under Sonnet (E6)
    for me in static_methods:
        for s in args.splits:
            mb = cmp_block(cmp_macros_v2, s, me)
            if not mb:
                continue
            cases = mb.get("cases") or []
            pe = sum(1 for c in cases if c.get("provider_error"))
            md.append(
                f"| `{me}` | static | {s} "
                f"| {pct(mb.get('diagnosis_success_rate'))} "
                f"| {num(mb.get('diagnosis_score_v1_1'))} "
                f"| {num(mb.get('macro_category_match_score_v1_1'))} "
                f"| {pct(mb.get('macro_critical_signal_mention_recall'))} "
                f"| {pct(mb.get('macro_must_mention_coverage'))} "
                f"| {pct(mb.get('confident_error_rate_v1_1'))} "
                f"| {pct(mb.get('abstention_rate'))} "
                f"| {pe} |"
            )
    md.append("")

    # ===== 7. Search-agent vs hybrid =====
    md.append("## 7. Search-agent vs hybrid")
    md.append("")
    md.append("| Split | Agent sv1.1 | Hybrid sv1.1 | Δ | Agent total tok | Hybrid total tok |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for s in args.splits:
        ab = agent_block(s)
        hb = cmp_block(cmp_macros_v2, s, "hybrid-grep-4k-rtk-err-cat-v1")
        a_sv = ab.get("diagnosis_score_v1_1")
        h_sv = hb.get("diagnosis_score_v1_1")
        # Agent total = average over cases
        cases = ab.get("cases") or []
        agent_tot = macro([(c.get("context_tokens") or 0) + (c.get("diagnosis_tokens") or 0) for c in cases])
        hyb_tot = (hb.get("macro_context_tokens") or 0) + (hb.get("macro_diagnosis_tokens") or 0)
        delta = (a_sv - h_sv) if (a_sv is not None and h_sv is not None) else None
        md.append(
            f"| {s} | {num(a_sv)} | {num(h_sv)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} "
            f"| {humanize_tokens(agent_tot)} | {humanize_tokens(hyb_tot)} |"
        )
    md.append("")

    # ===== 8. Search-agent vs grep =====
    md.append("## 8. Search-agent vs grep")
    md.append("")
    md.append("| Split | Agent sv1.1 | Grep sv1.1 (v2) | Δ |")
    md.append("|---|---:|---:|---:|")
    for s in args.splits:
        ab = agent_block(s)
        gb = cmp_block(cmp_macros_v2, s, "grep")
        a_sv = ab.get("diagnosis_score_v1_1")
        g_sv = gb.get("diagnosis_score_v1_1")
        delta = (a_sv - g_sv) if (a_sv is not None and g_sv is not None) else None
        md.append(
            f"| {s} | {num(a_sv)} | {num(g_sv)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} |"
        )
    md.append("")

    # ===== 9. Search-agent vs raw =====
    md.append("## 9. Search-agent vs raw")
    md.append("")
    md.append("| Split | Agent sv1.1 | Raw sv1.1 (v2) | Δ |")
    md.append("|---|---:|---:|---:|")
    for s in args.splits:
        ab = agent_block(s)
        rb = cmp_block(cmp_macros_v2, s, "raw")
        a_sv = ab.get("diagnosis_score_v1_1")
        r_sv = rb.get("diagnosis_score_v1_1")
        delta = (a_sv - r_sv) if (a_sv is not None and r_sv is not None) else None
        md.append(
            f"| {s} | {num(a_sv)} | {num(r_sv)} "
            f"| {('+' if (delta or 0) >= 0 else '')}{num(delta)} |"
        )
    md.append("")

    # ===== 10. Token / tool-call cost analysis (Table 2) =====
    md.append("## 10. Token / tool-call cost analysis")
    md.append("")
    md.append("### Table 2 — Cost")
    md.append("")
    md.append("| Method | Type | Split | Total Pipeline Tok | Final/Observed Ctx Tok | Tool Calls | Observed Lines | Provider Errors | Budget Exhausted |")
    md.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    # Agent rows
    for s in args.splits:
        traces = [t for t in all_traces if t["split"] == s]
        if not traces:
            continue
        n = len(traces)
        agent_total = round(macro([t["usage"]["total_agent_tokens_estimate"] for t in traces]) or 0, 1)
        obs_tokens = round(macro([t["usage"]["observation_tokens_estimate"] for t in traces]) or 0, 1)
        tool_calls = round(macro([t["usage"]["tool_call_count"] for t in traces]) or 0, 1)
        obs_lines = round(macro([t["usage"]["observed_line_count"] for t in traces]) or 0, 1)
        pe = sum(1 for t in traces if (t["metadata"] or {}).get("provider_error"))
        be = sum(1 for t in traces if (t["metadata"] or {}).get("budget_exhausted"))
        md.append(
            f"| `{args.agent_name}` | search | {s} "
            f"| {humanize_tokens(agent_total)} "
            f"| {humanize_tokens(obs_tokens)} "
            f"| {tool_calls} "
            f"| {int(obs_lines)} "
            f"| {pe} | {be} |"
        )
    # Static rows
    for me in static_methods:
        for s in args.splits:
            mb = cmp_block(cmp_macros_v2, s, me)
            if not mb:
                continue
            ctx = mb.get("macro_context_tokens") or 0
            diag = mb.get("macro_diagnosis_tokens") or 0
            cases = mb.get("cases") or []
            pe = sum(1 for c in cases if c.get("provider_error"))
            md.append(
                f"| `{me}` | static | {s} "
                f"| {humanize_tokens(ctx + diag)} | {humanize_tokens(ctx)} "
                f"| 0 | n/a "
                f"| {pe} | 0 |"
            )
    md.append("")

    # ===== 11. Budget exhaustion + provider-error =====
    md.append("## 11. Budget exhaustion and provider-error analysis")
    md.append("")
    md.append("| Split | Cases | Provider errors | Budget exhausted | Completed |")
    md.append("|---|---:|---:|---:|---:|")
    for s in args.splits:
        traces = [t for t in all_traces if t["split"] == s]
        n = len(traces)
        pe = sum(1 for t in traces if (t["metadata"] or {}).get("provider_error"))
        be = sum(1 for t in traces if (t["metadata"] or {}).get("budget_exhausted"))
        comp = sum(1 for t in traces if t.get("status") == "completed")
        md.append(f"| {s} | {n} | {pe} | {be} | {comp} |")
    md.append("")

    # ===== 12. Query/tool behavior analysis (Table 3 + 5) =====
    md.append("## 12. Query / tool behavior analysis")
    md.append("")
    md.append("### Table 3 — Search-agent behavior")
    md.append("")
    md.append("| Split | Mean Tool Calls | Median Tool Calls | Mean Observation Tokens | Mean Observed Lines | Most Used Tool | Budget Exhaustion Rate |")
    md.append("|---|---:|---:|---:|---:|---|---:|")
    for s in args.splits:
        traces = [t for t in all_traces if t["split"] == s]
        if not traces:
            continue
        tool_calls = [t["usage"]["tool_call_count"] for t in traces]
        obs_tok = [t["usage"]["observation_tokens_estimate"] for t in traces]
        obs_lines = [t["usage"]["observed_line_count"] for t in traces]
        tool_counts = Counter()
        for t in traces:
            for st in t.get("steps") or []:
                a = st.get("agent_action") or {}
                if a.get("type") == "tool_call":
                    tool_counts[a.get("tool")] += 1
        most = tool_counts.most_common(1)[0][0] if tool_counts else "n/a"
        be_rate = round(sum(1 for t in traces if (t["metadata"] or {}).get("budget_exhausted")) / max(1, len(traces)), 4)
        md.append(
            f"| {s} | {round(statistics.mean(tool_calls), 2)} "
            f"| {statistics.median(tool_calls)} "
            f"| {humanize_tokens(round(statistics.mean(obs_tok), 1))} "
            f"| {round(statistics.mean(obs_lines), 1)} "
            f"| `{most}` | {pct(be_rate)} |"
        )
    md.append("")

    # Tool usage table 5
    md.append("### Table 5 — Tool usage")
    md.append("")
    md.append("| Tool | Call Count | Cases Used | Mean Observation Tokens | Typical Purpose |")
    md.append("|---|---:|---:|---:|---|")
    tool_call_count = Counter()
    tool_case_set: dict[str, set] = defaultdict(set)
    tool_obs_tokens: dict[str, list[int]] = defaultdict(list)
    for t in all_traces:
        for st in t.get("steps") or []:
            a = st.get("agent_action") or {}
            if a.get("type") != "tool_call":
                continue
            tool = a.get("tool")
            tool_call_count[tool] += 1
            tool_case_set[tool].add((t["split"], t["case_id"]))
            obs = st.get("tool_observation") or {}
            if isinstance(obs, dict) and obs.get("tokens_estimate") is not None:
                tool_obs_tokens[tool].append(int(obs["tokens_estimate"]))
    purpose_hint = {
        "find_error_blocks": "deterministic candidate errors",
        "search_log": "targeted regex / substring search",
        "get_lines": "zoom into specific line ranges",
        "get_tail": "look at the end of the log",
        "get_head": "look at the start of the log",
        "list_github_steps": "discover step boundaries",
    }
    for tool, n in tool_call_count.most_common():
        mean_obs = round(statistics.mean(tool_obs_tokens.get(tool, [0])), 1) if tool_obs_tokens.get(tool) else 0
        md.append(f"| `{tool}` | {n} | {len(tool_case_set[tool])} "
                   f"| {humanize_tokens(mean_obs)} | {purpose_hint.get(tool, '—')} |")
    md.append("")

    # ===== 13. Per-case wins and losses (Table 4) =====
    md.append("## 13. Per-case wins and losses")
    md.append("")
    md.append("### Table 4 — Per-case comparison")
    md.append("")
    md.append("| Case | Split | Search sv1.1 | Hybrid sv1.1 | Grep sv1.1 | Search Tokens | Hybrid Tokens | Tool Calls | Winner |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for s in args.splits:
        ab = agent_block(s)
        hb = cmp_block(cmp_macros_v2, s, "hybrid-grep-4k-rtk-err-cat-v1")
        gb = cmp_block(cmp_macros_v2, s, "grep")
        agent_cases = {c["case_id"]: c for c in (ab.get("cases") or [])}
        hyb_cases   = {c["case_id"]: c for c in (hb.get("cases") or [])}
        grep_cases  = {c["case_id"]: c for c in (gb.get("cases") or [])}
        for cid in sorted(agent_cases.keys()):
            ac = agent_cases.get(cid, {})
            hc = hyb_cases.get(cid, {})
            gc = grep_cases.get(cid, {})
            a_sv = ac.get("diagnosis_score_v1_1")
            h_sv = hc.get("diagnosis_score_v1_1")
            g_sv = gc.get("diagnosis_score_v1_1")
            # Find the matching trace for token counts
            trace = next((t for t in all_traces
                            if t["case_id"] == cid and t["split"] == s), {})
            search_tok = (trace.get("usage") or {}).get("total_agent_tokens_estimate")
            hyb_tok = (hc.get("context_tokens") or 0) + (hc.get("diagnosis_tokens") or 0)
            tcalls = (trace.get("usage") or {}).get("tool_call_count", "?")
            best = max([(a_sv or 0, "search"), (h_sv or 0, "hybrid"), (g_sv or 0, "grep")],
                       key=lambda x: x[0])
            md.append(
                f"| `{cid}` | {s} | {num(a_sv)} | {num(h_sv)} | {num(g_sv)} "
                f"| {humanize_tokens(search_tok)} | {humanize_tokens(hyb_tok)} "
                f"| {tcalls} | `{best[1]}` |"
            )
    md.append("")

    # ===== 14. Failure-mode analysis (Table 6) =====
    md.append("## 14. Failure-mode analysis")
    md.append("")
    md.append("### Table 6 — Search-agent failure modes")
    md.append("")
    fm_buckets = {
        "method_success": 0,
        "missed_primary_error": 0,
        "searched_wrong_region": 0,
        "overused_tail": 0,
        "overused_generic_error_search": 0,
        "budget_exhausted_before_diagnosis": 0,
        "tool_observation_too_noisy": 0,
        "agent_ignored_observed_evidence": 0,
        "agent_hallucinated_from_partial_evidence": 0,
        "provider_error": 0,
    }
    fm_examples: dict[str, list[str]] = defaultdict(list)
    for t in all_traces:
        cid = t["case_id"]; s = t["split"]
        meta = t.get("metadata") or {}
        # diagnosis-side per-case from eval
        ev = (agent_macros.get(s) or {}).get(args.agent_name) or {}
        c = next((c for c in (ev.get("cases") or []) if c["case_id"] == cid), {})
        sv11 = c.get("diagnosis_score_v1_1") or 0
        cms = c.get("category_match_score_v1_1") or 0
        crit = c.get("critical_signal_mention_recall") or 0
        forbidden = c.get("forbidden_claim_violations") or []
        tools_used = []
        for st in t.get("steps") or []:
            a = st.get("agent_action") or {}
            if a.get("type") == "tool_call":
                tools_used.append(a.get("tool"))
        labels = []
        if meta.get("provider_error"):
            labels.append("provider_error")
        elif meta.get("budget_exhausted"):
            labels.append("budget_exhausted_before_diagnosis")
        else:
            if sv11 >= 0.6:
                labels.append("method_success")
            if forbidden:
                labels.append("agent_hallucinated_from_partial_evidence")
            if crit < 0.5 and sv11 < 0.4:
                labels.append("missed_primary_error")
            if tools_used.count("get_tail") + tools_used.count("get_head") >= 2:
                labels.append("overused_tail")
            if tools_used.count("search_log") >= 3:
                labels.append("overused_generic_error_search")
            # heuristic: more than one observation but low signal recall
            obs_tokens = (t.get("usage") or {}).get("observation_tokens_estimate") or 0
            if obs_tokens >= 8000 and crit < 0.5:
                labels.append("tool_observation_too_noisy")
            if not labels:
                labels.append("method_success" if sv11 >= 0.6 else "missed_primary_error")
        for lab in labels:
            if lab in fm_buckets:
                fm_buckets[lab] += 1
                if cid not in fm_examples[lab]:
                    fm_examples[lab].append(cid)
    md.append("| Failure Mode | Cases | Example | Notes |")
    md.append("|---|---:|---|---|")
    for lab, n in fm_buckets.items():
        if n == 0:
            continue
        ex = fm_examples[lab][0] if fm_examples[lab] else "—"
        md.append(f"| `{lab}` | {n} | `{ex}` | — |")
    md.append("")

    # ===== 15. Interpretation guardrails =====
    md.append("## 15. Interpretation guardrails")
    md.append("")
    md.append("- **One agent prompt, one tool budget, one model.** The agent ran with `prompts/search_agent_v1.md`, the budget in this config, and Claude Sonnet 4.6 only.")
    md.append("- **Local MCP-style tools** (Mode A in the E7 plan). A real MCP server adapter is a future extension.")
    md.append("- **16 cases.** Directional, not statistical.")
    md.append("- **Calibration is expert-model, not human.** sv1.1 was calibrated on E2/E2b expert-model labels collected against Haiku diagnoses, not Sonnet diagnoses. Apply with care to v2 / search-agent.")
    md.append("- **Cost accounting differs from static methods.** The search-agent total includes input/output across all steps plus tool observations actually shown to the model. Static methods include the single context sent once + diagnosis output.")
    md.append("- **The 4 schemas / 7 tools / agent shim are deterministic side-by-side with the model loop**, but the model's actions at temperature=0 still drift slightly across runs.")
    md.append("")

    # ===== 16. Decision and next experiment =====
    # Decision logic: locked baseline if search ≥ hybrid AND total tokens manageable
    sv11_macro = round(macro([t for s, t, _ in sv11_per_split if t is not None]) or 0, 4)
    hyb_macro = round(macro([h for s, _, h in sv11_per_split if h is not None]) or 0, 4)
    sv_pass = sv11_macro >= hyb_macro - 0.02
    avg_tokens = []
    for s in args.splits:
        traces = [t for t in all_traces if t["split"] == s]
        if traces:
            avg_tokens.append(macro([t["usage"]["total_agent_tokens_estimate"] for t in traces]))
    avg_agent_tokens = round(macro([t for t in avg_tokens if t]) or 0, 1)
    pe_total = sum(1 for t in all_traces if (t["metadata"] or {}).get("provider_error"))
    be_total = sum(1 for t in all_traces if (t["metadata"] or {}).get("budget_exhausted"))

    if sv_pass and pe_total / max(1, len(all_traces)) <= 0.10 and be_total / max(1, len(all_traces)) <= 0.20:
        decision = "ADD_AS_V1_4_BASELINE"
    elif sv11_macro >= hyb_macro - 0.10:
        decision = "KEEP_AS_EXPLORATORY"
    else:
        decision = "DO_NOT_PURSUE_FURTHER"

    md.append("## 16. Decision and next experiment")
    md.append("")
    md.append(f"**Decision: `{decision}`**")
    md.append("")
    md.append("| Criterion | Value | Pass? |")
    md.append("|---|---:|:---:|")
    md.append(f"| search-agent macro sv1.1 ≥ hybrid macro - 0.02 | {num(sv11_macro)} vs {num(hyb_macro)} | {'✅' if sv_pass else '❌'} |")
    md.append(f"| provider error rate ≤ 10% | {pct(pe_total / max(1, len(all_traces)))} | "
               f"{'✅' if pe_total / max(1, len(all_traces)) <= 0.10 else '❌'} |")
    md.append(f"| budget exhaustion rate ≤ 20% | {pct(be_total / max(1, len(all_traces)))} | "
               f"{'✅' if be_total / max(1, len(all_traces)) <= 0.20 else '❌'} |")
    md.append(f"| mean total agent tokens per case | {humanize_tokens(avg_agent_tokens)} | (informational) |")
    md.append("")
    if decision == "ADD_AS_V1_4_BASELINE":
        md.append(
            "Search-agent passed the threshold. Recommend freezing "
            "**`cilogbench-v1.4`** with `mcp-search-agent-v1-sonnet` as a "
            "locked end-to-end baseline (clearly labeled as `end_to_end_search_agent`, "
            "not a context-provider). Then run a second search-agent prompt or a "
            "second agent model for replication."
        )
    elif decision == "KEEP_AS_EXPLORATORY":
        md.append(
            "Search-agent is competitive with hybrid but does not clearly win. "
            "Keep `mcp-search-agent-v1-sonnet` as an **exploratory** method — "
            "report it alongside v1.3 baselines but do not freeze a v1.4 "
            "baseline yet. Investigate the dominant failure mode in §14 before "
            "committing to a search-agent track."
        )
    else:
        md.append(
            "Search-agent loses meaningfully to the locked v1.3 hybrid on this "
            "corpus, with `mcp-search-agent-v1-sonnet` not justifying its "
            "tool-call overhead. Keep v1.3 as the main public protocol and "
            "prioritize human-verified review or larger corpus instead."
        )
    md.append("")

    out_md = args.reports_dir / f"e7_mcp_search_agent_cilogbench_v1_3_{args.agent_name}.md"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    # Manifest
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": "cilogbench-v1.3",
        "protocol_lock_path": str(args.protocol.relative_to(ROOT)),
        "protocol_lock_sha256": sha256_path(args.protocol),
        "agent_name": args.agent_name,
        "agent_config_path": str(agent_cfg_path.relative_to(ROOT)),
        "agent_config_sha256": sha256_path(agent_cfg_path),
        "agent_prompt_path": str(args.prompt.relative_to(ROOT)),
        "agent_prompt_sha256": sha256_path(args.prompt),
        "tool_budget": agent_cfg.get("tool_budget"),
        "splits": args.splits,
        "case_count_by_split": {
            s: len([t for t in all_traces if t["split"] == s]) for s in args.splits
        },
        "primary_score": "diagnosis_score_v1_1",
        "secondary_score": "diagnosis_score_v1",
        "trace_dirs": {
            s: f"results/{s}/search_agents/{args.agent_name}/traces" for s in args.splits
        },
        "diagnosis_eval_paths": {
            s: f"results/{s}/eval_diagnosis_{args.agent_name}.json" for s in args.splits
        },
        "comparison_diagnoser_v2": args.comparison_diagnoser_v2,
        "comparison_diagnoser_v1": args.comparison_diagnoser_v1,
        "report_path": str(out_md.relative_to(ROOT)),
        "decision": decision,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": "unknown",
        "working_tree_dirty": True,
    }
    out_manifest = args.results_dir / f"e7_mcp_search_agent_cilogbench_v1_3_{args.agent_name}.manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"Wrote {out_manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
