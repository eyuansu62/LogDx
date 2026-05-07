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
    ("hybrid_route",         "schemas/hybrid_route.schema.json"),
]

PROMPT_KEYS: list[tuple[str, str]] = [
    ("llm_summary_map_v1",    "prompts/llm_summary_v1_map.md"),
    ("llm_summary_reduce_v1", "prompts/llm_summary_v1_reduce.md"),
    ("debugger_v1",           "prompts/debugger_v1.md"),
]

EVALUATOR_KEYS: list[tuple[str, str]] = [
    ("signal_recall",          "tools/evaluate_signal_recall.py"),
    ("diagnosis",              "tools/evaluate_diagnosis.py"),
    ("category_compatibility", "configs/evaluation/category_compatibility_v1_1.json"),
    ("hybrid_router",          "tools/run_hybrid_baseline.py"),
]

# Static baseline parameters. The hybrid baseline's content-addressed
# fields (config_sha256, route_schema_sha256, router_sha256) are filled
# dynamically in build_lock() via build_hybrid_baseline_block().
BASELINES_STATIC: dict = {
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

HYBRID_BASELINE_KEY = "hybrid-grep-4k-rtk-err-cat-v1"
HYBRID_CONFIG_PATH       = "configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json"
HYBRID_ROUTE_SCHEMA_PATH = "schemas/hybrid_route.schema.json"
HYBRID_ROUTER_PATH       = "tools/run_hybrid_baseline.py"


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


def build_hybrid_baseline_block() -> dict:
    """Construct the hybrid baseline block with content-addressed hashes.

    The locked hybrid is the v1.3 router (`hybrid-grep-4k-rtk-err-cat-v1`):
    grep when its output fits in 4000 tokens, otherwise rtk-err-cat. The
    config/route_schema/router file hashes pin the router behaviour;
    `anti_leakage` makes the no-ground-truth-leakage assertion explicit
    so a future change that wires ground-truth into routing would either
    have to flip the flag or invalidate the lock.
    """
    config_path  = ROOT / HYBRID_CONFIG_PATH
    schema_path  = ROOT / HYBRID_ROUTE_SCHEMA_PATH
    router_path  = ROOT / HYBRID_ROUTER_PATH
    for p in (config_path, schema_path, router_path):
        if not p.exists():
            raise FileNotFoundError(f"hybrid baseline file missing: {p.relative_to(ROOT)}")
    return {
        "enabled": True,
        "type": "hybrid_context_provider",
        "config_path":         HYBRID_CONFIG_PATH,
        "config_sha256":       sha256_path(config_path),
        "route_schema_path":   HYBRID_ROUTE_SCHEMA_PATH,
        "route_schema_sha256": sha256_path(schema_path),
        "router_path":         HYBRID_ROUTER_PATH,
        "router_sha256":       sha256_path(router_path),
        "primary_method":  "grep",
        "fallback_method": "rtk-err-cat",
        "budget_tokens":   4000,
        "anti_leakage": {
            "uses_ground_truth":   False,
            "uses_signal_eval":    False,
            "uses_diagnosis_eval": False,
            "uses_review_labels":  False,
        },
    }


def build_lock(protocol_id: str, regenerated: bool, splits: list[str]) -> dict:
    baselines = dict(BASELINES_STATIC)
    baselines[HYBRID_BASELINE_KEY] = build_hybrid_baseline_block()
    return {
        "protocol_id": protocol_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "regenerated": regenerated,
        "splits": {s: split_block(s) for s in splits},
        "schemas":    hash_map(SCHEMA_KEYS),
        "prompts":    hash_map(PROMPT_KEYS),
        "evaluators": hash_map(EVALUATOR_KEYS),
        "baselines":  baselines,
        "scoring": {
            "signal_recall_version":            "v1",
            "diagnosis_eval_version":           "v1.1",
            "diagnosis_score_primary":          "diagnosis_score_v1_1",
            "diagnosis_score_secondary":        "diagnosis_score_v1",
            "diagnosis_score_v1_experimental":  False,
            "diagnosis_score_v1_1_experimental": False,
            "calibration_evidence":             "reports/e2b_score_calibration_v1_1.md",
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
