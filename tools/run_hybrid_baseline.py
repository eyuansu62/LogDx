"""
E5 hybrid baseline runner.

Implements `hybrid-grep-4k-rtk-err-cat-v1` (and any other hybrid configured
similarly). For each case in the split:

  1. Read primary + fallback method manifests.
  2. Compute the routing decision using ONLY pre-diagnosis context metadata
     (case_id, context_path, output_byte_size). The router never opens
     ground_truth.json, eval_*.json, or review labels.
  3. Copy the selected context file (with a small metadata header) to
     `results/<split>/<hybrid_method>/<case_id>.txt`.
  4. Emit one row per case to:
        results/<split>/<hybrid_method>.jsonl          (method_output schema)
        results/<split>/<hybrid_method>.routes.jsonl   (hybrid_route schema)

Usage:
    python tools/run_hybrid_baseline.py \
        --split holdout \
        --config configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def chars_to_tokens(byte_size: int | None) -> int:
    """Match `tools/run_diagnosis.py`'s context_tokens accounting: chars/4."""
    if byte_size is None:
        return 0
    return int(byte_size) // 4


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def manifest_index(split: str, method: str, results_dir: Path) -> dict[str, dict]:
    p = results_dir / split / f"{method}.jsonl"
    return {r["case_id"]: r for r in load_jsonl(p)}


def emit_hybrid_context_file(
    *,
    out_path: Path,
    selected_method: str,
    selected_context_text: str,
    hybrid_method: str,
    selected_reason: str,
    budget_tokens: int,
) -> tuple[int, int]:
    """Write a hybrid context file = small header + selected method's content.
    Returns (line_count, byte_size) of the final file."""
    header_lines = [
        "# CILogBench hybrid context",
        "",
        f"hybrid_method: {hybrid_method}",
        f"selected_method: {selected_method}",
        f"selected_reason: {selected_reason}",
        f"budget_tokens: {budget_tokens}",
        "",
        "--- selected context ---",
        "",
    ]
    header = "\n".join(header_lines)
    body = (selected_context_text or "")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + body, encoding="utf-8")
    final = header + body
    return final.count("\n") + 1, len(final.encode("utf-8"))


def route_and_emit(
    *,
    split: str,
    case_id: str,
    config: dict,
    primary_row: dict | None,
    fallback_row: dict | None,
    raw_log_path: Path,
    out_method_dir: Path,
    out_jsonl_lines: list[str],
    out_routes_lines: list[str],
    cases_dir: Path,
    results_dir: Path,
    intermediate_row: dict | None = None,
) -> None:
    hybrid_method = config["method"]
    budget = int((config.get("routing_rule") or {}).get("budget_tokens") or 0)

    primary_name = config["primary_method"]
    fallback_name = config["fallback_method"]
    # v3+ optional 3-way routing: when grep doesn't fit the budget, try the
    # intermediate method (e.g. rtk-err-cat) BEFORE falling back to tail.
    # The intermediate is selected iff (1) its manifest row's
    # metadata.rtk_input_truncated == False (per Codex 2026-05-08-#2 [high]:
    # rtk silently truncates input at 10 MiB), AND (2) its own context_tokens
    # are within `intermediate_budget_tokens` (per Codex 2026-05-09 [high]:
    # nodejs's rtk-err-cat output was 320k tokens despite a 120k primary
    # budget; routing there reproduced exactly the prompt-blowup the hybrid
    # is supposed to avoid). If either gate fails, fall through to tail.
    intermediate_name = config.get("intermediate_method")
    intermediate_budget = int(
        (config.get("routing_rule") or {}).get("intermediate_budget_tokens")
        or budget  # default: same as primary budget
    )

    def candidate(name: str, row: dict | None) -> dict:
        if not row:
            return {
                "available": False,
                "context_tokens": None,
                "context_path": None,
                "provider_error": None,
                "rtk_input_truncated": False,
            }
        # `provider_error` may live in metadata or top-level depending on the row source.
        meta = row.get("metadata") or {}
        pe = meta.get("provider_error") or row.get("provider_error")
        # Per Codex 2026-05-09-#2 [high]: when output_byte_size is missing
        # from a manifest row (stale or partially regenerated row), the
        # previous code coerced None → 0 tokens via chars_to_tokens(None),
        # which silently passed any budget gate (`0 <= 120000`). A
        # version-skewed rtk-err-cat manifest could therefore route to
        # rtk-err-cat with `context_tokens: 0` while the actual context
        # file was 320k+ tokens — exactly the failure mode the budget gate
        # is meant to block. Fail closed: if the row exists but lacks
        # output_byte_size, treat it as provider-error so the candidate is
        # unavailable and the router falls through to the next branch.
        size = row.get("output_byte_size")
        if size is None:
            return {
                "available": False,
                "context_tokens": None,
                "context_path": row.get("context_path"),
                "provider_error": (
                    pe or
                    "manifest row missing output_byte_size — failing closed per "
                    "Codex 2026-05-09-#2 [high] (cannot prove budget compliance)"
                ),
                "rtk_input_truncated": bool(meta.get("rtk_input_truncated", False)),
            }
        ctx_tok = chars_to_tokens(size)
        return {
            "available": pe is None,
            "context_tokens": ctx_tok,
            "context_path": row.get("context_path"),
            "provider_error": pe,
            "rtk_input_truncated": bool(meta.get("rtk_input_truncated", False)),
        }

    cand_primary = candidate(primary_name, primary_row)
    cand_fallback = candidate(fallback_name, fallback_row)
    cand_intermediate = candidate(intermediate_name, intermediate_row) if intermediate_name else None

    # Routing decision (anti-leakage: only context metadata)
    selected_reason: str | None = None
    selected_method: str | None = None
    if cand_primary["available"]:
        if cand_primary["context_tokens"] <= budget:
            selected_method = primary_name
            selected_reason = "primary_fits_budget"
        elif cand_intermediate is not None:
            # 3-way routing: try intermediate before falling back to tail.
            # Three gates that must ALL pass to use the intermediate:
            #  (a) intermediate manifest row exists and provider_error is None
            #  (b) rtk_input_truncated is False (rtk's INPUT wasn't cut)
            #  (c) context_tokens <= intermediate_budget (rtk's OUTPUT fits)
            # If any gate fails, fall through to fallback (tail).
            if (cand_intermediate["available"]
                    and not cand_intermediate["rtk_input_truncated"]
                    and cand_intermediate["context_tokens"] is not None
                    and cand_intermediate["context_tokens"] <= intermediate_budget):
                selected_method = intermediate_name
                selected_reason = "primary_too_large_used_intermediate"
            elif cand_intermediate["rtk_input_truncated"]:
                # Intermediate's input was truncated — fall through to fallback.
                if cand_fallback["available"]:
                    selected_method = fallback_name
                    selected_reason = "intermediate_truncated_used_fallback"
                else:
                    selected_reason = "fallback_missing_provider_error"
            elif (cand_intermediate["available"]
                    and cand_intermediate["context_tokens"] is not None
                    and cand_intermediate["context_tokens"] > intermediate_budget):
                # Intermediate's OUTPUT exceeds its budget — fall through.
                if cand_fallback["available"]:
                    selected_method = fallback_name
                    selected_reason = "intermediate_too_large_used_fallback"
                else:
                    selected_reason = "fallback_missing_provider_error"
            elif cand_intermediate["provider_error"]:
                if cand_fallback["available"]:
                    selected_method = fallback_name
                    selected_reason = "intermediate_provider_error_used_fallback"
                else:
                    selected_reason = "fallback_provider_error"
            else:
                # Intermediate manifest row missing.
                if cand_fallback["available"]:
                    selected_method = fallback_name
                    selected_reason = "intermediate_missing_used_fallback"
                else:
                    selected_reason = "fallback_missing_provider_error"
        else:
            # 2-way routing (v1, v2)
            if cand_fallback["available"]:
                selected_method = fallback_name
                selected_reason = "primary_too_large_used_fallback"
            elif cand_fallback["provider_error"]:
                selected_reason = "fallback_provider_error"
            else:
                selected_reason = "fallback_missing_provider_error"
    else:
        if cand_primary["provider_error"]:
            # Primary itself failed — try the fallback rather than die silently.
            if cand_fallback["available"]:
                selected_method = fallback_name
                selected_reason = "primary_provider_error_used_fallback"
            else:
                selected_reason = "primary_missing_provider_error"
        else:
            selected_reason = "primary_missing_provider_error"

    # Build the hybrid context file.
    out_ctx_path = out_method_dir / f"{case_id}.txt"
    line_mapping_available = False
    mapping_type = "none"
    included_line_ranges: list = []
    output_line_count = 0
    output_byte_size = 0
    selected_ctx_path: str | None = None

    if selected_method:
        if selected_method == primary_name:
            chosen_row = primary_row
        elif intermediate_name and selected_method == intermediate_name:
            chosen_row = intermediate_row
        else:
            chosen_row = fallback_row
        chosen_path = ROOT / (chosen_row or {}).get("context_path", "")
        if not chosen_path.exists():
            # Treat as a fallback failure
            selected_method = None
            selected_reason = "primary_missing_provider_error" if selected_reason == "primary_fits_budget" else selected_reason
        else:
            text = chosen_path.read_text(encoding="utf-8", errors="replace")
            output_line_count, output_byte_size = emit_hybrid_context_file(
                out_path=out_ctx_path,
                selected_method=selected_method,
                selected_context_text=text,
                hybrid_method=hybrid_method,
                selected_reason=selected_reason,
                budget_tokens=budget,
            )
            selected_ctx_path = str(chosen_path.relative_to(ROOT))
            # Carry line mapping from grep when grep is selected
            if selected_method == primary_name and (chosen_row or {}).get("included_line_ranges"):
                included_line_ranges = (chosen_row or {}).get("included_line_ranges") or []
                line_mapping_available = True
                mapping_type = "line"
            else:
                line_mapping_available = False
                mapping_type = "text"

    # Compose method_output row
    raw_size = raw_log_path.stat().st_size if raw_log_path.exists() else 0
    raw_line_count = 0
    if raw_log_path.exists():
        raw_line_count = sum(1 for _ in raw_log_path.read_bytes().splitlines())
    reduction = 0.0 if raw_size == 0 else round(1.0 - (output_byte_size / raw_size), 6)
    if output_byte_size > raw_size:
        reduction = 0.0

    provider_error_msg = None
    if selected_method is None:
        # Provider error path. Per Codex 2026-05-10 [high]: previously this
        # branch only set provider_error_msg for 3 of N selected_reasons,
        # so a router that exhausts every option (e.g. missing primary +
        # missing fallback) silently emitted a placeholder context file
        # AND a method_row with provider_error=None. run_diagnosis would
        # then evaluate the UNAVAILABLE placeholder as a low-quality
        # diagnosis. Fail closed: ALWAYS set provider_error_msg when no
        # method was selected so downstream tools can detect this state.
        provider_error_msg = (
            f"hybrid: {selected_reason or 'no_method_selected'}; "
            f"primary={primary_name} fallback={fallback_name}"
        )
        # Still write a placeholder context file so downstream tools have
        # a path to read. The placeholder's first line carries an
        # UNAVAILABLE marker that run_diagnosis also checks as a backup
        # signal.
        if not out_ctx_path.exists():
            out_ctx_path.parent.mkdir(parents=True, exist_ok=True)
            out_ctx_path.write_text(
                "UNAVAILABLE: hybrid router could not select a context.\n"
                f"selected_reason: {selected_reason}\n",
                encoding="utf-8",
            )
            output_line_count = 2
            output_byte_size = out_ctx_path.stat().st_size

    method_row = {
        "case_id": case_id,
        "method": hybrid_method,
        "mode": "context_provider",
        "raw_log_path": str(raw_log_path.relative_to(ROOT)) if raw_log_path.exists() else "",
        "context_path": str(out_ctx_path.relative_to(ROOT)),
        "input_line_count": raw_line_count,
        "output_line_count": output_line_count,
        "input_byte_size": raw_size,
        "output_byte_size": output_byte_size,
        "reduction_ratio": reduction,
        "included_line_ranges": included_line_ranges,
        "line_mapping_available": line_mapping_available,
        "mapping_type": mapping_type,
        "metadata": {
            "hybrid": True,
            "router_version": config.get("router_version", "v1"),
            "selected_method": selected_method,
            "selected_reason": selected_reason,
            "budget_tokens": budget,
            "primary_method": primary_name,
            "fallback_method": fallback_name,
            "primary_context_tokens": cand_primary["context_tokens"],
            "fallback_context_tokens": cand_fallback["context_tokens"],
            "route_record_path":
                f"results/{split}/{hybrid_method}.routes.jsonl",
        },
    }
    if provider_error_msg:
        method_row["metadata"]["provider_error"] = provider_error_msg

    out_jsonl_lines.append(json.dumps(method_row, ensure_ascii=False))

    candidates_block = {
        primary_name: cand_primary,
        fallback_name: cand_fallback,
    }
    if intermediate_name and cand_intermediate is not None:
        candidates_block[intermediate_name] = cand_intermediate
    route_row = {
        "case_id": case_id,
        "split": split,
        "hybrid_method": hybrid_method,
        "selected_method": selected_method,
        "selected_reason": selected_reason,
        "budget_tokens": budget,
        "candidates": candidates_block,
        "selected_context_path": selected_ctx_path,
        "output_context_path": str(out_ctx_path.relative_to(ROOT)),
        "line_mapping_available": line_mapping_available,
        "mapping_type": mapping_type,
        "router_version": config.get("router_version", "v1"),
    }
    out_routes_lines.append(json.dumps(route_row, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--cases-dir", type=Path, default=ROOT / "cases")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = ap.parse_args(argv)

    config = load_json(args.config)
    hybrid_method = config["method"]
    primary_name = config["primary_method"]
    fallback_name = config["fallback_method"]
    intermediate_name = config.get("intermediate_method")

    primary_idx = manifest_index(args.split, primary_name, args.results_dir)
    fallback_idx = manifest_index(args.split, fallback_name, args.results_dir)
    intermediate_idx = (
        manifest_index(args.split, intermediate_name, args.results_dir)
        if intermediate_name else {}
    )

    case_dirs = sorted(p for p in (args.cases_dir / args.split).iterdir()
                        if p.is_dir())
    case_ids = [p.name for p in case_dirs]
    if not case_ids:
        print(f"ERROR: no cases under {args.cases_dir / args.split}", file=sys.stderr)
        return 1

    out_method_dir = args.results_dir / args.split / hybrid_method
    out_method_dir.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    routes: list[str] = []
    for case_id in case_ids:
        raw_p = args.cases_dir / args.split / case_id / "raw.log"
        route_and_emit(
            split=args.split,
            case_id=case_id,
            config=config,
            primary_row=primary_idx.get(case_id),
            fallback_row=fallback_idx.get(case_id),
            intermediate_row=intermediate_idx.get(case_id) if intermediate_name else None,
            raw_log_path=raw_p,
            out_method_dir=out_method_dir,
            out_jsonl_lines=rows,
            out_routes_lines=routes,
            cases_dir=args.cases_dir,
            results_dir=args.results_dir,
        )

    out_jsonl = args.results_dir / args.split / f"{hybrid_method}.jsonl"
    out_jsonl.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out_routes = args.results_dir / args.split / f"{hybrid_method}.routes.jsonl"
    out_routes.write_text("\n".join(routes) + "\n", encoding="utf-8")

    # Summary
    sel = {"grep": 0, "rtk-err-cat": 0, "none": 0}
    for r in routes:
        d = json.loads(r)
        sel[d.get("selected_method") or "none"] = sel.get(d.get("selected_method") or "none", 0) + 1
    print(f"Wrote {out_jsonl.relative_to(ROOT)}  ({len(rows)} rows)")
    print(f"Wrote {out_routes.relative_to(ROOT)}  ({len(routes)} routes)")
    print(f"  selected: {sel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
