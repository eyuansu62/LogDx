"""
Aggregate tags.json across splits into a corpus summary.

Outputs:
    results/corpus_summary.json
    reports/corpus_summary.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def collect_split(split: str) -> list[dict]:
    split_dir = ROOT / "cases" / split
    if not split_dir.is_dir():
        return []
    out: list[dict] = []
    for cd in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        if cd.name.startswith("."):
            continue
        tags_path = cd / "tags.json"
        if not tags_path.exists():
            continue
        out.append(json.loads(tags_path.read_text(encoding="utf-8")))
    return out


def tally(rows: list[dict]) -> dict:
    t = {
        "case_count": len(rows),
        "framework": dict(Counter(r.get("framework", "unknown") for r in rows)),
        "failure_category": dict(Counter(r.get("failure_category", "unknown") for r in rows)),
        "log_size_bucket": dict(Counter(r.get("log_size_bucket", "unknown") for r in rows)),
        "signal_position": dict(Counter(r.get("signal_position", "unknown") for r in rows)),
        "evidence_formats": dict(Counter(
            fmt for r in rows for fmt in (r.get("evidence_formats") or [])
        )),
        "noise_profile": dict(Counter(
            n for r in rows for n in (r.get("noise_profile") or [])
        )),
        "diagnosis_difficulty": dict(Counter(r.get("diagnosis_difficulty", "unclear") for r in rows)),
        "multi_failure_count": sum(1 for r in rows if r.get("multi_failure")),
        "flaky_or_transient_count": sum(1 for r in rows if r.get("flaky_or_transient")),
    }
    return t


def render_md(summary: dict, splits: list[str]) -> str:
    md: list[str] = []
    md.append("# CILogBench corpus summary")
    md.append("")
    md.append(f"Generated at {summary['generated_at']}.")
    md.append("")

    md.append("## Case counts")
    md.append("")
    md.append("| Split | Cases |")
    md.append("|---|---:|")
    for s in splits:
        md.append(f"| {s} | {summary['splits'][s]['case_count']} |")
    md.append(f"| **total** | **{summary['totals']['case_count']}** |")
    md.append("")

    for axis in ("framework", "failure_category", "log_size_bucket",
                 "signal_position", "diagnosis_difficulty"):
        md.append(f"## By {axis}")
        md.append("")
        # Gather every value across splits
        values: set[str] = set()
        for s in splits:
            values.update((summary['splits'][s].get(axis) or {}).keys())
        header = "| Value | " + " | ".join(s for s in splits) + " | total |"
        sep = "|---|" + "|".join(["---:"] * (len(splits) + 1)) + "|"
        md.append(header); md.append(sep)
        for v in sorted(values):
            row = [v]
            for s in splits:
                row.append(str((summary['splits'][s].get(axis) or {}).get(v, 0)))
            row.append(str((summary['totals'].get(axis) or {}).get(v, 0)))
            md.append("| " + " | ".join(row) + " |")
        md.append("")

    md.append("## Evidence formats (multi-valued; rows may count multiple tags)")
    md.append("")
    md.append(render_multi("evidence_formats", summary, splits))
    md.append("")
    md.append("## Noise profile (multi-valued)")
    md.append("")
    md.append(render_multi("noise_profile", summary, splits))
    md.append("")

    md.append("## Flags")
    md.append("")
    md.append("| Flag | " + " | ".join(splits) + " | total |")
    md.append("|---|" + "|".join(["---:"] * (len(splits) + 1)) + "|")
    for flag_key, label in (("multi_failure_count", "multi_failure"),
                             ("flaky_or_transient_count", "flaky_or_transient")):
        row = [label]
        total = 0
        for s in splits:
            v = summary['splits'][s].get(flag_key, 0)
            total += v
            row.append(str(v))
        row.append(str(total))
        md.append("| " + " | ".join(row) + " |")
    md.append("")
    return "\n".join(md)


def render_multi(axis: str, summary: dict, splits: list[str]) -> str:
    values: set[str] = set()
    for s in splits:
        values.update((summary['splits'][s].get(axis) or {}).keys())
    lines: list[str] = []
    header = "| Value | " + " | ".join(s for s in splits) + " |"
    sep = "|---|" + "|".join(["---:"] * len(splits)) + "|"
    lines.append(header); lines.append(sep)
    for v in sorted(values):
        row = [v]
        for s in splits:
            row.append(str((summary['splits'][s].get(axis) or {}).get(v, 0)))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aggregate tags across splits.")
    ap.add_argument("--splits", default="dev,holdout,stress")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    split_tags: dict[str, list[dict]] = {}
    for s in splits:
        split_tags[s] = collect_split(s)

    summary = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "splits": {s: tally(rows) for s, rows in split_tags.items()},
        "totals": tally([r for rows in split_tags.values() for r in rows]),
    }

    out_json = args.results_dir / "corpus_summary.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    out_md = args.reports_dir / "corpus_summary.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(summary, splits) + "\n", encoding="utf-8")
    print(f"Wrote {out_json.relative_to(ROOT)}")
    print(f"Wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
