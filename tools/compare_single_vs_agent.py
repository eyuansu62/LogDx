"""Side-by-side comparison: single-shot vs agent-loop on v1.0 corpus.

Reads per-split eval_diagnosis_*.json for both diagnoser families:
  single-shot:  real-debugger-v1 (Haiku 4.5)
                real-debugger-v2 (Sonnet 4.6)
                real-debugger-v3 (gpt-5-mini)
  agent-loop:   real-agent-v1   (Sonnet 4.6)

For each method, aggregates case-count-weighted macro across:
  - 6 splits (dev, holdout, stress, v2/dev, v2/holdout, v2/stress)
  - The 3 single-shot debugger families (averaged), OR the agent only

Outputs:
  - stdout: a side-by-side table
  - /tmp/logdx_v1_vs_v1_1_comparison.json (raw data for downstream plots)

Run:
  python3 tools/compare_single_vs_agent.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]

SINGLE_SHOT_DIAGS = ["real-debugger-v1", "real-debugger-v2", "real-debugger-v3"]
AGENT_DIAG = "real-agent-v1"

METHODS = [
    ("raw",                          "raw"),
    ("tail-200",                     "tail"),
    ("grep",                         "grep"),
    ("rtk-read",                     "rtk-read"),
    ("rtk-log",                      "rtk-log"),
    ("rtk-err-cat",                  "rtk-err-cat"),
    ("llm-summary-v1-mock",          "llm-summary-v1-mock"),
    ("hybrid-grep-4k-rtk-err-cat",   "hybrid-grep-4k-rtk-err-cat-v1"),
    ("hybrid-grep-120k-tail",        "hybrid-grep-120k-tail-v2"),
    ("hybrid-grep-120k-rtk-tail",    "hybrid-grep-120k-rtk-tail-v3"),
]


def _aggregate_across(splits, diags, eval_method):
    """Return case-count-weighted macro of key metrics across splits×diags."""
    sums = {
        "score": 0.0, "conf_err": 0.0,
        "context_tokens": 0.0,
        "agent_iters": 0.0, "agent_tools": 0.0,
        "agent_in": 0.0, "agent_out": 0.0,
        "budget_exh": 0.0,
    }
    counters = {k: 0 for k in sums}

    def add(out_key, src_key, ck, cc):
        v = mb.get(src_key)
        if v is None:
            return
        sums[out_key] += v * cc
        counters[ck] += cc

    for split in splits:
        for diag in diags:
            p = ROOT / f"results/{split}/eval_diagnosis_{diag}.json"
            if not p.exists():
                continue
            j = json.load(p.open())
            cc = j.get("case_count") or 0
            if cc == 0:
                continue
            for mb in j.get("methods", []):
                if mb["context_method"] != eval_method:
                    continue
                add("score",          "diagnosis_score_v1_1",                 "score",         cc)
                add("conf_err",       "confident_error_rate_v1_1",            "conf_err",      cc)
                add("context_tokens", "macro_context_tokens",                 "context_tokens",cc)
                add("agent_iters",    "macro_agent_iterations",               "agent_iters",   cc)
                add("agent_tools",    "macro_agent_tool_call_count",          "agent_tools",   cc)
                add("agent_in",       "macro_agent_total_input_tokens_consumed", "agent_in",   cc)
                add("agent_out",      "macro_agent_total_output_tokens_consumed","agent_out",  cc)
                add("budget_exh",     "budget_exhausted_rate",                "budget_exh",    cc)
                break

    out = {}
    for k in sums:
        out[k] = (sums[k] / counters[k]) if counters[k] else None
    return out


def main():
    rows = []
    for public_label, eval_key in METHODS:
        ss = _aggregate_across(SPLITS, SINGLE_SHOT_DIAGS, eval_key)
        ag = _aggregate_across(SPLITS, [AGENT_DIAG], eval_key)
        rows.append({
            "method": public_label,
            "single_shot": ss,
            "agent": ag,
        })

    # Sort by single-shot score (matching the v1.0 leaderboard order).
    rows.sort(key=lambda r: (r["single_shot"]["score"] or 0), reverse=True)

    def fmt(v, digits=3):
        return "  —  " if v is None else f"{v:.{digits}f}"

    def fmt_int(v):
        return "—" if v is None else f"{int(round(v)):,}"

    print()
    print("=" * 130)
    print(
        f"{'method':32s}  | "
        f"{'SINGLE-SHOT':^45s} | {'AGENT-LOOP (Sonnet 4.6)':^48s}"
    )
    print(
        f"{'':32s}  | "
        f"{'score':>8s} {'conf_err':>9s} {'ctx_tok':>10s} {'? ':>8s}  |  "
        f"{'score':>8s} {'iters':>6s} {'tools':>6s} {'in_tot':>10s} {'budg':>5s}"
    )
    print("-" * 130)
    for r in rows:
        ss = r["single_shot"]
        ag = r["agent"]
        delta = (ag["score"] - ss["score"]) if (ag["score"] is not None and ss["score"] is not None) else None
        delta_str = "—" if delta is None else f"{delta:+.3f}"
        print(
            f"{r['method']:32s}  | "
            f"{fmt(ss['score']):>8s} {fmt(ss['conf_err']):>9s} "
            f"{fmt_int(ss['context_tokens']):>10s} {'':>8s}  |  "
            f"{fmt(ag['score']):>8s} "
            f"{fmt(ag['agent_iters'], digits=2):>6s} "
            f"{fmt(ag['agent_tools'], digits=2):>6s} "
            f"{fmt_int(ag['agent_in']):>10s} "
            f"{fmt(ag['budget_exh']):>5s}"
            f"    Δ score: {delta_str}"
        )

    out_path = "/tmp/logdx_v1_vs_v1_1_comparison.json"
    with open(out_path, "w") as f:
        json.dump(rows, f, indent=2)
    print()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
