"""
Build a blinded human-review batch from existing diagnosis outputs.

Reads:
    results/<split>/diagnoses/<diagnoser>/<method>.jsonl

Writes:
    review/batches/<batch_id>/items.jsonl     reviewer-facing, method NAMES HIDDEN
    review/batches/<batch_id>/manifest.json   hidden method map + batch metadata

Supports:
    --mode absolute     one item per (case × method)
    --mode pairwise     one item per (case × method pair); A/B order randomized
    --mode both         emit both kinds into items.jsonl

Hidden method identity is stored ONLY in manifest.json. Reviewer-facing
items use `method_A` / `method_B` / etc.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import random
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_manifest_rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_case_packet(cases_dir: Path, split: str, case_id: str) -> dict:
    case = json.loads((cases_dir / split / case_id / "case.json").read_text(encoding="utf-8"))
    gt = json.loads((cases_dir / split / case_id / "ground_truth.json").read_text(encoding="utf-8"))
    pkt = {
        "repo": case.get("repo", ""),
        "workflow_name": case.get("workflow_name", ""),
        "job_name": case.get("job_name", ""),
        "framework": case.get("framework", ""),
        "allowed_ground_truth_summary": (gt.get("root_cause") or {}).get("summary", ""),
    }
    # Tiny evidence excerpt: first evidence span, up to 12 lines.
    spans = gt.get("evidence_spans") or []
    if spans:
        s, e = spans[0]["start_line"], spans[0]["end_line"]
        raw = (cases_dir / split / case_id / "raw.log").read_text(encoding="utf-8", errors="replace").splitlines()
        excerpt = "\n".join(raw[s - 1 : min(len(raw), e)][:12])
        pkt["required_evidence_excerpt"] = excerpt
    return pkt


def blind_id(i: int) -> str:
    # method_A, method_B, ...; wraps past Z if >26 methods (unlikely).
    return f"method_{string.ascii_uppercase[i % 26]}{'' if i < 26 else i // 26}"


_METHOD_NAME_PATTERNS = [
    "rtk-read", "rtk-log", "rtk-err-cat",
    "llm-summary-v1", "llm-summary",
    "raw.jsonl", "grep.jsonl", "tail.jsonl",
]


def _sanitize(s: str) -> str:
    """Redact method names in case a diagnoser self-mentions them
    (e.g. stubs that include `(on grep context)`). Keeps the scoring
    fair by removing anything that would un-blind the reviewer."""
    if not isinstance(s, str):
        return s
    out = s
    low = out.lower()
    for name in _METHOD_NAME_PATTERNS:
        while name in low:
            idx = low.find(name)
            out = out[:idx] + "[method]" + out[idx + len(name):]
            low = out.lower()
    return out


def _sanitize_any(v):
    if isinstance(v, str):
        return _sanitize(v)
    if isinstance(v, list):
        return [_sanitize_any(x) for x in v]
    if isinstance(v, dict):
        return {k: _sanitize_any(x) for k, x in v.items()}
    return v


def strip_diagnosis(row: dict) -> dict:
    body = {
        "summary": row.get("summary", ""),
        "root_cause_category": row.get("root_cause_category", ""),
        "root_cause": row.get("root_cause", ""),
        "confidence": row.get("confidence", 0.0),
        "relevant_files": row.get("relevant_files", []),
        "relevant_tests": row.get("relevant_tests", []),
        "evidence": row.get("evidence", []),
        "suggested_fix": row.get("suggested_fix", ""),
    }
    return _sanitize_any(body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a blinded human-review batch.")
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--diagnoser", required=True)
    ap.add_argument("--methods", required=True,
                    help="Comma-separated context methods to include.")
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--mode", default="both", choices=["absolute", "pairwise", "both"])
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    ap.add_argument("--review-root", type=Path, default=ROOT / "review" / "batches")
    ap.add_argument("--seed", type=int, default=20260424,
                    help="Seed for A/B randomization.")
    args = ap.parse_args(argv)

    protocol_path = args.protocol if args.protocol.is_absolute() else (ROOT / args.protocol)
    if not protocol_path.exists():
        print(f"ERROR: protocol not found: {protocol_path}", file=sys.stderr)
        return 1
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    if len(methods) < 2 and args.mode in ("pairwise", "both"):
        print("ERROR: pairwise mode needs at least 2 methods.", file=sys.stderr)
        return 1

    # Stable method-id mapping for the batch: method_A, method_B, ...
    blind_map = {methods[i]: blind_id(i) for i in range(len(methods))}

    batch_dir = args.review_root / args.batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = batch_dir / "labels"
    labels_dir.mkdir(exist_ok=True)

    rng = random.Random(args.seed)
    items: list[dict] = []
    created = dt.datetime.now(dt.timezone.utc).isoformat()

    # Load each method's diagnoses once.
    per_method: dict[str, dict[str, dict]] = {}
    for m in methods:
        p = args.results_dir / args.split / "diagnoses" / args.diagnoser / f"{m}.jsonl"
        rows = load_manifest_rows(p)
        per_method[m] = {r["case_id"]: r for r in rows}

    # Get the set of case IDs that every method diagnosed (intersection).
    case_ids = sorted(set.intersection(*[set(per_method[m].keys()) for m in methods])) \
        if all(per_method.values()) else []
    if not case_ids:
        print("ERROR: no common case IDs across the selected methods.", file=sys.stderr)
        return 1

    # Absolute items: one per case × method.
    if args.mode in ("absolute", "both"):
        counter = 0
        for cid in case_ids:
            for m in methods:
                counter += 1
                diag = per_method[m][cid]
                body = strip_diagnosis(diag)
                diag_sha = sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=False))
                items.append({
                    "review_item_id": f"abs-{counter:04d}",
                    "batch_id": args.batch_id,
                    "case_id": cid,
                    "diagnoser": args.diagnoser,
                    "label_type": "absolute",
                    "blind_method_id": blind_map[m],
                    "case_packet": load_case_packet(args.cases_dir, args.split, cid),
                    "diagnosis": body,
                    "metadata": {
                        "created_at": created,
                        "protocol_id": protocol.get("protocol_id", "unknown"),
                        "diagnosis_sha256": diag_sha,
                        "hidden_context_method": True,
                    },
                })

    # Pairwise items: one per case × method pair; A/B order randomized.
    if args.mode in ("pairwise", "both"):
        counter = 0
        for cid in case_ids:
            for m_a, m_b in itertools.combinations(methods, 2):
                counter += 1
                # Randomize A/B order.
                if rng.random() < 0.5:
                    m_a, m_b = m_b, m_a
                body_a = strip_diagnosis(per_method[m_a][cid])
                body_b = strip_diagnosis(per_method[m_b][cid])
                items.append({
                    "review_item_id": f"pair-{counter:04d}",
                    "batch_id": args.batch_id,
                    "case_id": cid,
                    "diagnoser": args.diagnoser,
                    "label_type": "pairwise",
                    "blind_method_id_a": blind_map[m_a],
                    "blind_method_id_b": blind_map[m_b],
                    "case_packet": load_case_packet(args.cases_dir, args.split, cid),
                    "diagnosis_a": body_a,
                    "diagnosis_b": body_b,
                    "metadata": {
                        "created_at": created,
                        "protocol_id": protocol.get("protocol_id", "unknown"),
                        "diagnosis_sha256_a": sha256_text(json.dumps(body_a, sort_keys=True, ensure_ascii=False)),
                        "diagnosis_sha256_b": sha256_text(json.dumps(body_b, sort_keys=True, ensure_ascii=False)),
                        "hidden_context_method": True,
                    },
                })

    items_path = batch_dir / "items.jsonl"
    with items_path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    manifest = {
        "batch_id": args.batch_id,
        "protocol_id": protocol.get("protocol_id", "unknown"),
        "split": args.split,
        "diagnoser": args.diagnoser,
        "methods": methods,
        "blind_method_map": blind_map,
        "mode": args.mode,
        "seed": args.seed,
        "case_ids": case_ids,
        "item_counts": {
            "absolute": sum(1 for it in items if it["label_type"] == "absolute"),
            "pairwise": sum(1 for it in items if it["label_type"] == "pairwise"),
            "total": len(items),
        },
        "created_at": created,
    }
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {items_path.relative_to(ROOT)}  ({len(items)} items)")
    print(f"Wrote {(batch_dir / 'manifest.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
