"""Aggregate agent-loop metrics across splits × debuggers.

Companion to tools/aggregate_cost_metrics.py and
tools/aggregate_confident_error.py — but operates on the agent_metadata
fields (iterations, tool_call_count, total_input_tokens_consumed,
budget_exhausted_rate) that only agent-loop diagnosers emit.

Reads:
- results/<split>/eval_diagnosis_real-agent-*.json

For each (public_method_label × debugger) cell, returns a record with:
  diagnosis_score_v1_1   (for cross-comparison vs single-shot)
  confident_error_rate_v1_1
  macro_agent_iterations
  macro_agent_tool_call_count
  macro_agent_total_input_tokens_consumed
  macro_agent_total_output_tokens_consumed
  budget_exhausted_rate
  macro_context_tokens          (the static reducer output, unchanged)

Output: stdout table + JSON to /tmp/logdx_agent_metrics.json
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]
AGENT_DIAGNOSERS = [
    ("Sonnet 4.6 agent",  "real-agent-v1"),
    ("Haiku 4.5 agent",   "real-agent-v1-haiku"),
    ("gpt-5-mini agent",  "real-agent-v1-gpt5mini"),
]

METHODS = [
    ("raw",                        "raw"),
    ("tail-200",                   "tail"),
    ("grep",                       "grep"),
    ("rtk-read",                   "rtk-read"),
    ("rtk-log",                    "rtk-log"),
    ("rtk-err-cat",                "rtk-err-cat"),
    ("llm-summary-v1-mock",        "llm-summary-v1-mock"),
    ("hybrid-grep-4k-rtk-err-cat", "hybrid-grep-4k-rtk-err-cat-v1"),
    ("hybrid-grep-120k-tail",      "hybrid-grep-120k-tail-v2"),
    ("hybrid-grep-120k-rtk-tail",  "hybrid-grep-120k-rtk-tail-v3"),
]


def _per_method_per_debugger():
    """Case-count-weighted macro of each metric, per (method × debugger)."""
    out = {}
    for public_label, eval_key in METHODS:
        row = {}
        for diag_label, diag_id in AGENT_DIAGNOSERS:
            agg = {}
            tot_w = 0
            sums = dict(
                score=0.0, conf_err=0.0,
                iterations=0.0, tool_call_count=0.0,
                total_in=0.0, total_out=0.0,
                budget_exhausted=0.0,
                context_tokens=0.0,
            )
            counters = dict(score=0, conf_err=0, iters=0, tcc=0,
                            in_=0, out=0, be=0, ctx=0)
            for split in SPLITS:
                p = ROOT / f"results/{split}/eval_diagnosis_{diag_id}.json"
                if not p.exists():
                    continue
                j = json.load(p.open())
                cc = j.get("case_count") or 0
                if cc == 0:
                    continue
                for mb in j.get("methods", []):
                    if mb["context_method"] != eval_key:
                        continue

                    def _add(key, src):
                        v = mb.get(src)
                        if v is None:
                            return
                        sums[key] += v * cc
                        counters[key.replace("_", "") if key in (
                            "in_", "out", "be"
                        ) else key] = counters.get(
                            key.replace("_", "") if key in (
                                "in_", "out", "be"
                            ) else key, 0
                        ) + cc

                    def add(out_key, src_key, count_key):
                        v = mb.get(src_key)
                        if v is None:
                            return
                        sums[out_key] += v * cc
                        counters[count_key] = counters.get(count_key, 0) + cc

                    add("score", "diagnosis_score_v1_1", "score")
                    add("conf_err", "confident_error_rate_v1_1", "conf_err")
                    add("iterations", "macro_agent_iterations", "iters")
                    add("tool_call_count", "macro_agent_tool_call_count", "tcc")
                    add("total_in", "macro_agent_total_input_tokens_consumed", "in_")
                    add("total_out", "macro_agent_total_output_tokens_consumed", "out")
                    add("budget_exhausted", "budget_exhausted_rate", "be")
                    add("context_tokens", "macro_context_tokens", "ctx")
                    tot_w += cc
                    break

            def _w(sum_key, count_key):
                if counters.get(count_key, 0) == 0:
                    return None
                return sums[sum_key] / counters[count_key]

            agg["diagnosis_score_v1_1"] = _w("score", "score")
            agg["confident_error_rate_v1_1"] = _w("conf_err", "conf_err")
            agg["macro_agent_iterations"] = _w("iterations", "iters")
            agg["macro_agent_tool_call_count"] = _w("tool_call_count", "tcc")
            agg["macro_agent_total_input_tokens_consumed"] = _w("total_in", "in_")
            agg["macro_agent_total_output_tokens_consumed"] = _w("total_out", "out")
            agg["budget_exhausted_rate"] = _w("budget_exhausted", "be")
            agg["macro_context_tokens"] = _w("context_tokens", "ctx")
            row[diag_label] = agg
        out[public_label] = row
    return out


def _fmt(v, digits=3):
    if v is None:
        return "  —  "
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _fmt_int(v):
    if v is None:
        return "  —  "
    return f"{int(round(v)):,}"


def main():
    res = _per_method_per_debugger()
    # Print Sonnet-only table (the smoke-test default).
    diag = "Sonnet 4.6 agent"
    print(f"\n=== Agent-loop metrics on {diag} (case-count-weighted macro) ===\n")
    headers = (
        "method", "score", "conf_err", "iters", "tools",
        "in_total", "out_total", "budget_exh",
    )
    print(
        f"{'method':36s}  {'score':>7s}  {'conf_err':>8s}  "
        f"{'iters':>6s}  {'tools':>6s}  "
        f"{'in_tot':>9s}  {'out_tot':>7s}  {'budg_exh':>9s}"
    )
    print("-" * 100)
    for public_label, _ in METHODS:
        r = (res.get(public_label) or {}).get(diag) or {}
        print(
            f"{public_label:36s}  "
            f"{_fmt(r.get('diagnosis_score_v1_1')):>7s}  "
            f"{_fmt(r.get('confident_error_rate_v1_1')):>8s}  "
            f"{_fmt(r.get('macro_agent_iterations'), digits=2):>6s}  "
            f"{_fmt(r.get('macro_agent_tool_call_count'), digits=2):>6s}  "
            f"{_fmt_int(r.get('macro_agent_total_input_tokens_consumed')):>9s}  "
            f"{_fmt_int(r.get('macro_agent_total_output_tokens_consumed')):>7s}  "
            f"{_fmt(r.get('budget_exhausted_rate')):>9s}"
        )

    out_path = "/tmp/logdx_agent_metrics.json"
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
