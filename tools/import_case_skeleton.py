"""
Create a case directory skeleton from a raw log + basic metadata.

Writes:
    cases/<split>/<case_id>/raw.log
    cases/<split>/<case_id>/case.json
    cases/<split>/<case_id>/ground_truth.todo.json     (placeholder to fill)
    cases/<split>/<case_id>/tags.todo.json             (placeholder to fill)

The `.todo.json` names prevent validate_cases from accidentally accepting an
un-annotated case — only `ground_truth.json` counts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GROUND_TRUTH_TODO_TEMPLATE = {
    "root_cause": {
        "summary": "TODO: describe root cause using only evidence in raw.log",
        "category": "unknown"
    },
    "required_signals": [
        {
            "type": "exception",
            "value": "TODO: literal substring from raw.log",
            "importance": "critical",
            "evidence_lines": [[1, 1]]
        }
    ],
    "relevant_files": [],
    "relevant_tests": [],
    "evidence_spans": [
        {"start_line": 1, "end_line": 1, "reason": "TODO"}
    ],
    "expected_diagnosis": {
        "must_mention": ["TODO"],
        "must_not_claim": ["TODO"]
    }
}

TAGS_TODO_TEMPLATE = {
    "case_id": "TODO",
    "split": "TODO",
    "failure_category": "TODO",
    "framework": "TODO",
    "primary_language": "TODO",
    "log_size_bucket": "TODO",
    "signal_position": "TODO",
    "evidence_formats": ["TODO"],
    "noise_profile": ["TODO"],
    "multi_failure": False,
    "flaky_or_transient": False,
    "requires_repo_context": False,
    "diagnosis_difficulty": "unclear",
    "notes": "TODO"
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create a case directory skeleton.")
    ap.add_argument("--split", required=True)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--raw-log", required=True, type=Path)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--framework", default="generic")
    ap.add_argument("--workflow-name", default="unknown")
    ap.add_argument("--job-name", default="unknown")
    ap.add_argument("--source", default="github_actions")
    ap.add_argument("--failure-category", default="unknown")
    ap.add_argument("--force", action="store_true",
                    help="Re-import a raw.log + case.json into an existing "
                         "case directory whose annotations have NOT been "
                         "filled yet. Refuses if ground_truth.json or "
                         "tags.json exists (use --force-clean instead).")
    ap.add_argument("--force-clean", action="store_true",
                    help="Destructive: delete the entire case directory "
                         "(including any accepted ground_truth.json / "
                         "tags.json) and recreate it from scratch. Use "
                         "only when re-importing a different raw.log "
                         "under the same case_id is intentional.")
    args = ap.parse_args(argv)

    case_dir = ROOT / "cases" / args.split / args.case_id
    rel_dir = case_dir.relative_to(ROOT)
    if case_dir.exists():
        accepted_gt = (case_dir / "ground_truth.json").exists()
        accepted_tags = (case_dir / "tags.json").exists()
        if args.force_clean:
            # Per Codex adversarial review 2026-05-07: avoid leaving stale
            # accepted annotations attached to a different raw.log.
            shutil.rmtree(case_dir)
            print(f"NOTE: --force-clean wiped {rel_dir} (was: gt={accepted_gt}, "
                  f"tags={accepted_tags})", file=sys.stderr)
        elif args.force:
            if accepted_gt or accepted_tags:
                print(
                    f"ERROR: {rel_dir} already has accepted annotations "
                    f"(ground_truth.json={accepted_gt}, tags.json={accepted_tags}). "
                    f"Pass --force-clean to wipe-and-recreate, or remove "
                    f"the accepted files manually first. --force alone "
                    f"would leave stale annotations attached to the new "
                    f"raw.log.",
                    file=sys.stderr,
                )
                return 1
            # Safe re-import: only .todo.json / case.json / raw.log will be overwritten.
        else:
            print(f"ERROR: {rel_dir} already exists. Pass --force "
                  f"(if no accepted ground_truth.json/tags.json yet) or "
                  f"--force-clean (destructive: wipes accepted annotations).",
                  file=sys.stderr)
            return 1

    if not args.raw_log.exists():
        print(f"ERROR: raw log not found: {args.raw_log}", file=sys.stderr)
        return 1

    case_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(args.raw_log, case_dir / "raw.log")
    raw_bytes = (case_dir / "raw.log").read_bytes()
    line_count = raw_bytes.count(b"\n")

    case_json = {
        "case_id": args.case_id,
        "repo": args.repo,
        "source": args.source,
        "framework": args.framework,
        "failure_category": args.failure_category,
        "raw_log_path": "raw.log",
        "line_count": line_count,
        "byte_size": len(raw_bytes),
        "workflow_name": args.workflow_name,
        "job_name": args.job_name,
        "notes": "TODO: fill in after reading raw.log"
    }
    (case_dir / "case.json").write_text(
        json.dumps(case_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    todo_gt = dict(GROUND_TRUTH_TODO_TEMPLATE)
    (case_dir / "ground_truth.todo.json").write_text(
        json.dumps(todo_gt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    todo_tags = dict(TAGS_TODO_TEMPLATE)
    todo_tags["case_id"] = args.case_id
    todo_tags["split"] = args.split
    (case_dir / "tags.todo.json").write_text(
        json.dumps(todo_tags, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote skeleton {case_dir.relative_to(ROOT)}  "
          f"(line_count={line_count}, bytes={len(raw_bytes)})")
    print(f"  fill in and rename: ground_truth.todo.json → ground_truth.json")
    print(f"  fill in and rename: tags.todo.json → tags.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
