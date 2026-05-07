"""
Generate a human-friendly review pack for E9:

  1. A single-file Markdown rendering of every item in order
     (cases grouped, absolute then pairwise within each case),
     with the diagnosis JSON pretty-printed and the case packet
     up top.

  2. A skeleton labels jsonl with one TODO entry per review_item_id,
     pre-populated with the right `review_item_id`, `reviewer_id`, and
     `label_type`, so the human reviewer only has to fill in the score
     fields.

Open the Markdown in your editor on the left half, the skeleton jsonl
on the right half, and label down the file.

Usage:
    python3 tools/render_e9_review_pack.py \
        --batch-id e9_v1_3_hybrid_vs_grep_human_001 \
        --reviewer-id human_a
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def truncate(s: str, n: int = 120) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[:n] + "…"


def fmt_diagnosis(diag: dict) -> str:
    out = []
    out.append(f"- **summary:** {diag.get('summary', '')}")
    out.append(f"- **root_cause_category:** `{diag.get('root_cause_category', '')}`")
    out.append(f"- **root_cause:** {diag.get('root_cause', '')}")
    out.append(f"- **confidence:** {diag.get('confidence', 0)}")
    if diag.get("relevant_files"):
        out.append(f"- **relevant_files:** {diag['relevant_files']}")
    if diag.get("relevant_tests"):
        out.append(f"- **relevant_tests:** {diag['relevant_tests']}")
    out.append("- **evidence:**")
    if not diag.get("evidence"):
        out.append("    - _(none)_")
    else:
        for ev in diag["evidence"]:
            q = ev.get("quote", "")
            r = ev.get("reason", "")
            out.append(f"    - quote: `{q[:200]}`")
            out.append(f"      reason: {r[:200]}")
    sf = diag.get("suggested_fix", "")
    if sf:
        out.append(f"- **suggested_fix:** {sf}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--reviewer-id", required=True,
                    help="Use a non-model identifier (e.g. 'human_a', 'jy', etc.)")
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    args = ap.parse_args(argv)

    if args.reviewer_id.startswith(("claude", "gpt", "sonnet", "opus", "haiku")) \
            or "expert" in args.reviewer_id:
        print(f"ERROR: reviewer_id {args.reviewer_id!r} looks like a model identifier; "
              f"use a human-shaped name like 'human_a' or your initials.",
              file=sys.stderr)
        return 1

    batch_dir = args.review_root / args.batch_id
    items = load_jsonl(batch_dir / "items.jsonl")
    if not items:
        print(f"ERROR: no items in {batch_dir}", file=sys.stderr)
        return 1
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))

    # ---- 1. render Markdown reading pack ----
    md: list[str] = []
    md.append(f"# E9 review pack — `{args.batch_id}`")
    md.append("")
    md.append(
        f"> Reviewer: **`{args.reviewer_id}`** "
        f"· Items: **{len(items)}** "
        f"· Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}"
    )
    md.append("")
    md.append(
        "Read each item, then write the matching label entry into "
        f"`{(batch_dir / 'labels' / f'reviewer_{args.reviewer_id}.jsonl').relative_to(ROOT)}`. "
        "The label skeleton has one TODO line per `review_item_id` you can fill in directly. "
        "**Do NOT** open `manifest.json` — it reveals the method names. "
        "**Do NOT** name methods (`raw`, `tail`, `grep`, `rtk-*`, `llm-summary-*`) in your `notes`."
    )
    md.append("")

    # Group items by case for readability
    by_case: dict[str, list[dict]] = {}
    for it in items:
        by_case.setdefault(it["case_id"], []).append(it)
    case_order = sorted(by_case.keys())

    for cid in case_order:
        case_items = by_case[cid]
        # Case packet from any item (they share)
        cp = (case_items[0].get("case_packet") or {})
        md.append(f"## case `{cid}`")
        md.append("")
        md.append(f"- **repo:** `{cp.get('repo', '')}`")
        md.append(f"- **workflow:** `{cp.get('workflow_name', '')}`")
        md.append(f"- **job:** `{cp.get('job_name', '')}`")
        md.append(f"- **framework:** `{cp.get('framework', '')}`")
        md.append("")
        md.append("**Ground-truth summary** (the actual cause; use this as the standard you score against):")
        md.append("")
        md.append("> " + (cp.get("allowed_ground_truth_summary", "") or "_(none)_").replace("\n", "\n> "))
        md.append("")
        if cp.get("required_evidence_excerpt"):
            md.append("<details><summary>Required-evidence excerpt (raw log)</summary>")
            md.append("")
            md.append("```text")
            md.append(cp["required_evidence_excerpt"])
            md.append("```")
            md.append("")
            md.append("</details>")
            md.append("")

        # Absolute items first
        abs_items = [it for it in case_items if it["label_type"] == "absolute"]
        for it in sorted(abs_items, key=lambda x: x["review_item_id"]):
            md.append(f"### `{it['review_item_id']}` (absolute)")
            md.append("")
            md.append(fmt_diagnosis(it.get("diagnosis") or {}))
            md.append("")

        # Pairwise items
        pair_items = [it for it in case_items if it["label_type"] == "pairwise"]
        for it in sorted(pair_items, key=lambda x: x["review_item_id"]):
            md.append(f"### `{it['review_item_id']}` (pairwise)")
            md.append("")
            md.append("**Diagnosis A:**")
            md.append("")
            md.append(fmt_diagnosis(it.get("diagnosis_a") or {}))
            md.append("")
            md.append("**Diagnosis B:**")
            md.append("")
            md.append(fmt_diagnosis(it.get("diagnosis_b") or {}))
            md.append("")

        md.append("---")
        md.append("")

    out_md = batch_dir / f"review_pack_{args.reviewer_id}.md"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}  ({len(items)} items rendered)")

    # ---- 2. write skeleton labels jsonl with TODOs ----
    labels_dir = batch_dir / "labels"
    labels_dir.mkdir(exist_ok=True)
    skel_path = labels_dir / f"reviewer_{args.reviewer_id}.skeleton.jsonl"

    if skel_path.exists():
        print(f"WARN: skeleton already exists at {skel_path.relative_to(ROOT)}; "
              f"refusing to overwrite. Move/rename if you want a fresh one.",
              file=sys.stderr)
    else:
        with skel_path.open("w", encoding="utf-8") as f:
            for it in items:
                if it["label_type"] == "absolute":
                    skel = {
                        "review_item_id": it["review_item_id"],
                        "reviewer_id": args.reviewer_id,
                        "label_type": "absolute",
                        "root_cause_correctness": "TODO_0_TO_4",
                        "evidence_support": "TODO_0_TO_4",
                        "localization_quality": "TODO_0_TO_4",
                        "actionability": "TODO_0_TO_4",
                        "hallucination_severity": "TODO_0_TO_4",
                        "overall_usefulness": "TODO_0_TO_4",
                        "abstention_appropriateness":
                            "TODO_appropriate_or_not_appropriate_or_not_applicable",
                        "notes": "TODO_one_line_or_empty_string",
                    }
                else:
                    skel = {
                        "review_item_id": it["review_item_id"],
                        "reviewer_id": args.reviewer_id,
                        "label_type": "pairwise",
                        "winner": "TODO_A_or_B_or_remove_this_field",
                        "tie": False,
                        "both_bad": False,
                        "insufficient_information": False,
                        "reason": "TODO_one_line_or_empty_string",
                    }
                f.write(json.dumps(skel, ensure_ascii=False) + "\n")
        print(f"Wrote {skel_path.relative_to(ROOT)}  ({len(items)} TODO entries)")

    # Print final instructions
    print()
    print("Next:")
    print(f"  1. Open {out_md.relative_to(ROOT)} in your editor.")
    print(f"  2. Open {skel_path.relative_to(ROOT)} in another pane.")
    print(f"  3. For each `review_item_id` block in the Markdown, replace the")
    print(f"     matching TODO_* values in the skeleton with real labels.")
    print(f"  4. When done, rename:")
    print(f"       {skel_path.relative_to(ROOT)}")
    print(f"     →")
    print(f"       {(labels_dir / f'reviewer_{args.reviewer_id}.jsonl').relative_to(ROOT)}")
    print(f"  5. Validate:")
    print(f"       python3 tools/validate_human_review_labels.py "
           f"--batch-id {args.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
