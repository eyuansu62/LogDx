"""
Flag imbalances between splits: categories present in one split but missing in
others, dominance by a single framework, missing signal-position buckets, etc.

Outputs:
    results/split_balance.json
    reports/split_balance.md

This is diagnostic, not a failure criterion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_tags(split: str) -> list[dict]:
    d = ROOT / "cases" / split
    if not d.is_dir():
        return []
    out: list[dict] = []
    for cd in sorted(p for p in d.iterdir() if p.is_dir()):
        if cd.name.startswith("."):
            continue
        p = cd / "tags.json"
        if p.exists():
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def flags_for(rows: dict[str, list[dict]]) -> list[dict]:
    flags: list[dict] = []

    # 1. Categories / frameworks present in one split but missing in another.
    for axis in ("failure_category", "framework"):
        all_values = {}
        for s, recs in rows.items():
            all_values[s] = {r.get(axis, "unknown") for r in recs}
        union = set().union(*all_values.values()) if all_values else set()
        for v in sorted(union):
            missing_in = [s for s in rows if v not in all_values.get(s, set())]
            present_in = [s for s in rows if v in all_values.get(s, set())]
            if missing_in and present_in:
                flags.append({
                    "kind": f"{axis}_split_mismatch",
                    "value": v,
                    "present_in": present_in,
                    "missing_in": missing_in,
                })

    # 2. Split dominated by a single framework (>=70% of cases).
    for s, recs in rows.items():
        if not recs:
            continue
        fw = {}
        for r in recs:
            fw[r.get("framework", "unknown")] = fw.get(r.get("framework", "unknown"), 0) + 1
        dom_fw, cnt = max(fw.items(), key=lambda kv: kv[1])
        if cnt / len(recs) >= 0.7:
            flags.append({
                "kind": "framework_dominance",
                "split": s, "framework": dom_fw,
                "fraction": round(cnt / len(recs), 3),
            })

    # 3. Splits dominated by small logs.
    for s, recs in rows.items():
        if not recs:
            continue
        small = sum(1 for r in recs if r.get("log_size_bucket") == "small")
        if small / len(recs) >= 0.7:
            flags.append({
                "kind": "log_size_dominance",
                "split": s, "bucket": "small",
                "fraction": round(small / len(recs), 3),
            })

    # 4. Splits with no early/middle/late/scattered diversity.
    for s, recs in rows.items():
        if not recs:
            continue
        positions = {r.get("signal_position") for r in recs}
        if len(positions) == 1:
            flags.append({
                "kind": "signal_position_monoculture",
                "split": s, "position": next(iter(positions)),
            })

    return flags


def render_md(rows: dict[str, list[dict]], flags: list[dict]) -> str:
    md: list[str] = []
    md.append("# Split balance check")
    md.append("")
    md.append("| Split | Cases | Frameworks | Categories | Log-size buckets | Positions |")
    md.append("|---|---:|---|---|---|---|")
    for s, recs in rows.items():
        fw = sorted({r.get("framework", "unknown") for r in recs})
        cats = sorted({r.get("failure_category", "unknown") for r in recs})
        lsb = sorted({r.get("log_size_bucket", "unknown") for r in recs})
        pos = sorted({r.get("signal_position", "unknown") for r in recs})
        md.append(f"| {s} | {len(recs)} | {', '.join(fw)} | {', '.join(cats)} "
                  f"| {', '.join(lsb)} | {', '.join(pos)} |")
    md.append("")

    md.append("## Flags")
    md.append("")
    if not flags:
        md.append("No imbalance flags.")
    else:
        for f in flags:
            md.append(f"- `{f['kind']}`: {json.dumps({k: v for k, v in f.items() if k != 'kind'}, ensure_ascii=False)}")
    md.append("")
    md.append("## Disclaimer")
    md.append("")
    md.append("These flags are diagnostic. A split can be intentionally adversarial "
              "(e.g. `stress` may dominate in small logs to test tail-like methods). "
              "Use flags to inform future additions, not to gate the protocol.")
    return "\n".join(md)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    rows = {s: load_tags(s) for s in splits}
    flags = flags_for(rows)
    summary = {
        "splits": {s: {"case_count": len(rows[s])} for s in splits},
        "flags": flags,
    }
    out_json = args.results_dir / "split_balance.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    out_md = args.reports_dir / "split_balance.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(rows, flags) + "\n", encoding="utf-8")
    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    print(f"  {len(flags)} flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
