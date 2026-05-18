"""Aggregate cost/latency metrics across the v1.0 corpus.

For each method × debugger, computes case-count-weighted macro:
- reducer_input_tokens   (LLM tokens consumed BY the reducer itself, e.g.
                          llm-summary methods that internally call an LLM
                          to produce the context; 0 for grep/tail/rtk/raw)
- reducer_output_tokens  (same; reducer-call output)
- context_tokens         (tokens delivered to the diagnosis LLM == reducer's
                          final stdout token count)
- diagnosis_tokens       (tokens produced by the diagnosis LLM)
- reducer_runtime_ms     (wall-clock time of the reducer itself; only
                          available for RTK methods via external_tool block)
- total_tokens           (reducer_input + reducer_output + context + diagnosis)

Reads:
- results/<split>/eval_diagnosis_<diag>.json  for context_tokens / diagnosis_tokens
- results/<split>/<method>.jsonl              for reducer_input/output + runtime

Output: stdout table + JSON to /tmp/logdx_cost_metrics.json for downstream
plot generation.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]
DIAGNOSERS = [
    ("Haiku 4.5",  "real-debugger-v1"),
    ("Sonnet 4.6", "real-debugger-v2"),
    ("gpt-5-mini", "real-debugger-v3"),
]

# Canonical leaderboard ordering with internal v1.3/v2 labels mapped to
# the public-facing names that appear on the website.
METHOD_FILES = {
    "raw":                          "raw",
    "tail-200":                     "tail",
    "grep":                         "grep",
    "rtk-read":                     "rtk-read",
    "rtk-log":                      "rtk-log",
    "rtk-err-cat":                  "rtk-err-cat",
    "llm-summary-v1-mock":          "llm-summary-v1-mock",
    "hybrid-grep-4k-rtk-err-cat":   "hybrid-grep-4k-rtk-err-cat-v1",
    "hybrid-grep-120k-tail":        "hybrid-grep-120k-tail-v2",
    "hybrid-grep-120k-rtk-tail":    "hybrid-grep-120k-rtk-tail-v3",
}


def _read_baseline_manifest(split: str, method_file: str):
    """Return {case_id: {reducer_input, reducer_output, runtime_ms}}."""
    p = ROOT / f"results/{split}/{method_file}.jsonl"
    if not p.exists():
        return {}
    out = {}
    for line in p.open():
        d = json.loads(line)
        cid = d["case_id"]
        # LLM-summary reducers record their own LLM consumption in
        # metadata.usage.{input,output}_tokens. Default 0 for non-LLM
        # reducers (grep/tail/rtk/raw) — they don't call an LLM.
        usage = (d.get("metadata") or {}).get("usage") or {}
        red_in = int(usage.get("input_tokens") or 0)
        red_out = int(usage.get("output_tokens") or 0)
        ext = d.get("external_tool") or {}
        rt = ext.get("runtime_ms")
        out[cid] = {
            "reducer_input": red_in,
            "reducer_output": red_out,
            "reducer_runtime_ms": float(rt) if rt is not None else None,
        }
    return out


def _read_eval_case_costs(split: str, diag: str, method_canonical: str):
    """Return {case_id: {context_tokens, diagnosis_tokens}} for one method.

    `method_canonical` is the internal name as it appears in the eval JSON
    (e.g. hybrid-grep-120k-rtk-tail-v3, tail), NOT the leaderboard label.
    """
    p = ROOT / f"results/{split}/eval_diagnosis_{diag}.json"
    if not p.exists():
        return {}
    j = json.load(p.open())
    out = {}
    for m in j.get("methods", []):
        if m["context_method"] != method_canonical:
            continue
        cases = m.get("cases", {})
        if isinstance(cases, list):
            cases = {c["case_id"]: c for c in cases}
        for cid, c in cases.items():
            out[cid] = {
                "context_tokens": int(c.get("context_tokens") or 0),
                "diagnosis_tokens": int(c.get("diagnosis_tokens") or 0),
            }
        break
    return out


def aggregate():
    """Returns {public_label: {debugger_label or "Overall": metric_dict}}."""
    result = {}
    for public_label, file_stub in METHOD_FILES.items():
        per_debugger = {}
        for diag_label, diag_id in DIAGNOSERS:
            tot_w = 0
            sums = dict(
                reducer_input=0.0,
                reducer_output=0.0,
                context_tokens=0.0,
                diagnosis_tokens=0.0,
                reducer_runtime_ms=0.0,
                runtime_w=0,  # not all rows have runtime
            )
            for split in SPLITS:
                baseline = _read_baseline_manifest(split, file_stub)
                evals = _read_eval_case_costs(split, diag_id, file_stub)
                # union of case ids (eval is authoritative for which cases
                # made it past the success gate, so use eval keys)
                for cid, ec in evals.items():
                    b = baseline.get(cid, {})
                    sums["reducer_input"] += b.get("reducer_input", 0)
                    sums["reducer_output"] += b.get("reducer_output", 0)
                    sums["context_tokens"] += ec["context_tokens"]
                    sums["diagnosis_tokens"] += ec["diagnosis_tokens"]
                    if b.get("reducer_runtime_ms") is not None:
                        sums["reducer_runtime_ms"] += b["reducer_runtime_ms"]
                        sums["runtime_w"] += 1
                    tot_w += 1
            if tot_w:
                rec = dict(
                    reducer_input=sums["reducer_input"] / tot_w,
                    reducer_output=sums["reducer_output"] / tot_w,
                    context_tokens=sums["context_tokens"] / tot_w,
                    diagnosis_tokens=sums["diagnosis_tokens"] / tot_w,
                )
                rec["total_tokens"] = (
                    rec["reducer_input"] + rec["reducer_output"]
                    + rec["context_tokens"] + rec["diagnosis_tokens"]
                )
                if sums["runtime_w"]:
                    rec["reducer_runtime_ms"] = (
                        sums["reducer_runtime_ms"] / sums["runtime_w"]
                    )
                else:
                    rec["reducer_runtime_ms"] = None
                per_debugger[diag_label] = rec
        # Average across debuggers for the "Overall" row.
        if per_debugger:
            keys = ["reducer_input", "reducer_output", "context_tokens",
                    "diagnosis_tokens", "total_tokens"]
            overall = {}
            for k in keys:
                vals = [d[k] for d in per_debugger.values() if d.get(k) is not None]
                overall[k] = sum(vals) / len(vals) if vals else None
            rt_vals = [d["reducer_runtime_ms"] for d in per_debugger.values()
                       if d.get("reducer_runtime_ms") is not None]
            overall["reducer_runtime_ms"] = (
                sum(rt_vals) / len(rt_vals) if rt_vals else None
            )
            per_debugger["Overall"] = overall
        result[public_label] = per_debugger
    return result


def fmt_int(v):
    if v is None or v == 0:
        return "—" if v is None else "0"
    return f"{int(round(v)):,}"


def fmt_ms(v):
    if v is None:
        return "—"
    return f"{v:.1f}ms"


def main():
    res = aggregate()
    # Sort by Overall.context_tokens ascending (cheapest first).
    rows = []
    for label, d in res.items():
        o = d.get("Overall") or {}
        rows.append((label, o))
    rows.sort(key=lambda r: r[1].get("total_tokens") or float("inf"))

    print(f"\n{'method':36s}  {'reducer_in':>10s}  {'reducer_out':>11s}  "
          f"{'context':>9s}  {'diag_out':>9s}  {'TOTAL':>9s}  {'red_rt':>8s}")
    print("-" * 100)
    for label, o in rows:
        print(
            f"{label:36s}  "
            f"{fmt_int(o.get('reducer_input')):>10s}  "
            f"{fmt_int(o.get('reducer_output')):>11s}  "
            f"{fmt_int(o.get('context_tokens')):>9s}  "
            f"{fmt_int(o.get('diagnosis_tokens')):>9s}  "
            f"{fmt_int(o.get('total_tokens')):>9s}  "
            f"{fmt_ms(o.get('reducer_runtime_ms')):>8s}"
        )

    out_path = "/tmp/logdx_cost_metrics.json"
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
