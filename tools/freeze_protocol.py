"""
Freeze a CILogBench protocol version.

Collects SHA-256 hashes for every schema, prompt, and evaluator, plus
the baseline parameters declared in code, into
`protocols/<protocol_id>.lock.json`. Refuses to overwrite an existing
lock unless `--force` is passed (in which case the new lock records
`"regenerated": true`).

Usage:
    python tools/freeze_protocol.py --protocol-id cilogbench-v1
    python tools/freeze_protocol.py --protocol-id cilogbench-v1 --force
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


SCHEMA_KEYS: list[tuple[str, str]] = [
    ("case",                 "schemas/case.schema.json"),
    ("ground_truth",         "schemas/ground_truth.schema.json"),
    ("method_output",        "schemas/method_output.schema.json"),
    ("diagnosis",            "schemas/diagnosis.schema.json"),
    ("diagnosis_eval",       "schemas/diagnosis_eval.schema.json"),
    ("protocol_lock",        "schemas/protocol_lock.schema.json"),
    ("split_manifest",       "schemas/split_manifest.schema.json"),
    ("diagnoser_config",     "schemas/diagnoser_config.schema.json"),
    ("summarizer_config",    "schemas/summarizer_config.schema.json"),
]

PROMPT_KEYS: list[tuple[str, str]] = [
    ("llm_summary_map_v1",    "prompts/llm_summary_v1_map.md"),
    ("llm_summary_reduce_v1", "prompts/llm_summary_v1_reduce.md"),
    ("debugger_v1",           "prompts/debugger_v1.md"),
]

EVALUATOR_KEYS: list[tuple[str, str]] = [
    ("signal_recall", "tools/evaluate_signal_recall.py"),
    ("diagnosis",     "tools/evaluate_diagnosis.py"),
]

BASELINES = {
    "raw":     {"enabled": True},
    "tail-200": {
        "enabled": True,
        "tail_lines": 200,
    },
    "grep": {
        "enabled": True,
        "regex": (
            "error|failed|failure|traceback|exception|assert|panic|exit code|"
            "##\\[error\\]"
        ),
        "before": 3,
        "after": 8,
    },
    "rtk-read":    {"enabled": True, "external_tool": "rtk", "version_policy": "record_actual_version"},
    "rtk-log":     {"enabled": True, "external_tool": "rtk", "version_policy": "record_actual_version"},
    "rtk-err-cat": {"enabled": True, "external_tool": "rtk", "version_policy": "record_actual_version"},
    "llm-summary-v1-mock": {"enabled": True},
}


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_map(entries: list[tuple[str, str]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, rel in entries:
        p = ROOT / rel
        if not p.exists():
            raise FileNotFoundError(f"locked file missing: {rel}")
        out[key] = {"path": rel, "sha256": sha256_path(p)}
    return out


def split_block(split: str) -> dict:
    manifest_path = ROOT / "cases" / split / "split_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"split manifest missing: {manifest_path}. "
            f"Run `tools/build_split_manifest.py --split {split}` first."
        )
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "path": f"cases/{split}",
        "case_count": int(m.get("case_count", 0)),
        "manifest_path": f"cases/{split}/split_manifest.json",
    }


def build_lock(protocol_id: str, regenerated: bool, splits: list[str]) -> dict:
    return {
        "protocol_id": protocol_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "regenerated": regenerated,
        "splits": {s: split_block(s) for s in splits},
        "schemas":    hash_map(SCHEMA_KEYS),
        "prompts":    hash_map(PROMPT_KEYS),
        "evaluators": hash_map(EVALUATOR_KEYS),
        "baselines":  BASELINES,
        "scoring": {
            "signal_recall_version": "v1",
            "diagnosis_eval_version": "v1",
            "diagnosis_score_v1_experimental": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze a CILogBench protocol.")
    ap.add_argument("--protocol-id", required=True)
    ap.add_argument("--splits", default="dev,holdout",
                    help="Comma-separated split names to include in the lock. "
                         "Each split must have a split_manifest.json.")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite an existing lock; records regenerated=true.")
    args = ap.parse_args(argv)
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]

    out_path = ROOT / "protocols" / f"{args.protocol_id}.lock.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    regenerated = False
    if out_path.exists():
        if not args.force:
            print(f"ERROR: {out_path.relative_to(ROOT)} already exists. "
                  f"Pass --force to regenerate.", file=sys.stderr)
            return 1
        regenerated = True
        print(f"WARNING: regenerating existing lock file; recording "
              f"regenerated=true", file=sys.stderr)

    try:
        lock = build_lock(args.protocol_id, regenerated, splits)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    out_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}  "
          f"(schemas={len(lock['schemas'])}, prompts={len(lock['prompts'])}, "
          f"evaluators={len(lock['evaluators'])}, baselines={len(lock['baselines'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
