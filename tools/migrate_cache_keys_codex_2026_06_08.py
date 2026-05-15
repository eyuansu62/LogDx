#!/usr/bin/env python3
"""One-shot migration: Codex 2026-06-08 F2 [high]. Rebuilds the
`results/<split>/.cache/diagnosis/` tree from the canonical manifests
under `results/<split>/diagnoses/`.

Why this exists: the F2 fix's first iteration folded diagnoser-config
SHA and shim-impl SHA directly into the cache key. That broke key
identity for every existing cache file. The shipped F2 design switched
to validation at cache-hit time (no key change), but the intermediate
remap left some local cache entries duplicated/collided. This script
rebuilds the cache from the tracked manifests as the source of truth.

Idempotent — rerun safely. Output is the file count by split.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import run_diagnosis as rd  # noqa: E402


def env_source_for_row(row: dict, config: dict | None) -> dict[str, str] | None:
    if not isinstance(config, dict):
        return None
    keys = config.get("cache_key_env") or []
    if not keys:
        return None
    mi = (row.get("metadata") or {}).get("model_info") or {}
    cfg_model = config.get("model") or {}
    out: dict[str, str] = {}
    for var in keys:
        if var == cfg_model.get("env_var_name"):
            out[var] = mi.get("requested_model") or cfg_model.get("model_name") or ""
        elif var == cfg_model.get("base_url_env_var_name"):
            out[var] = mi.get("base_url") or cfg_model.get("base_url") or ""
        else:
            out[var] = ""
    return out


def rebuild_split(split_root: Path, dry_run: bool) -> tuple[int, int]:
    """Walk the diagnoses tree and write a cache file per manifest row."""
    diagnoses_root = split_root / "diagnoses"
    cache_root = split_root / ".cache" / "diagnosis"
    if not diagnoses_root.exists():
        return 0, 0
    if not dry_run:
        if cache_root.exists():
            shutil.rmtree(cache_root)
        cache_root.mkdir(parents=True)
    written = skipped = 0
    for diag_dir in sorted(diagnoses_root.iterdir()):
        if not diag_dir.is_dir():
            continue
        diagnoser_name = diag_dir.name
        try:
            config = rd.load_diagnoser_config(diagnoser_name)
        except rd.DiagnoserConfigError:
            config = None
        for manifest in sorted(diag_dir.glob("*.jsonl")):
            with manifest.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    case_id = row.get("case_id")
                    context_method = row.get("context_method")
                    if not case_id or not context_method:
                        skipped += 1
                        continue
                    md = row.get("metadata") or {}
                    if md.get("provider_error"):
                        # Per Codex 2026-05-24 F1: provider_error rows are
                        # not cached by default. Manifest carries them
                        # for audit; the cache shouldn't replay them.
                        skipped += 1
                        continue
                    ctx_rel = (row.get("input") or {}).get("context_path")
                    if not ctx_rel:
                        skipped += 1
                        continue
                    ctx_path = REPO / ctx_rel
                    if not ctx_path.exists():
                        skipped += 1
                        continue
                    try:
                        ctx_text = ctx_path.read_text(
                            encoding="utf-8", errors="replace"
                        )
                    except OSError:
                        skipped += 1
                        continue
                    ctx_sha = rd.sha256_text(ctx_text)
                    prompt_sha = md.get("prompt_sha256")
                    if not prompt_sha:
                        skipped += 1
                        continue
                    provider = md.get("provider") or "command"
                    command_str = md.get("command")
                    env_values = rd.cache_key_env_values(
                        config, env_source=env_source_for_row(row, config)
                    )
                    key = rd.cache_key_for(
                        case_id=case_id, context_method=context_method,
                        context_sha=ctx_sha, prompt_sha=prompt_sha,
                        provider=provider, diagnoser=diagnoser_name,
                        command_str=command_str, env_values=env_values,
                    )
                    # Per Codex 2026-06-09 F2 [high]: stamp the current
                    # config + shim SHAs into the migrated cache row so
                    # `cache_hit_is_acceptable`'s 2026-06-08 F2 strict
                    # check has something to validate against. Without
                    # this, every migrated row was null-on-sha and the
                    # validator's "legacy back-compat = accept null"
                    # branch let the row replay across future config /
                    # shim edits. Stamping the SHAs means migrated rows
                    # become first-class entries that DO get rejected
                    # if the config or shim later changes. The migration
                    # is by definition the canonical-state moment, so
                    # stamping current SHAs is correct: the cached row
                    # WAS produced under "this config + this shim" (the
                    # current ones); future edits invalidate.
                    config_sha = rd.diagnoser_config_sha256(diagnoser_name)
                    shim_sha = rd.shim_sha256_for_command(command_str)
                    if dry_run:
                        print(
                            f"  WOULD write {cache_root.name}/{key[:12]}.json "
                            f"diag={diagnoser_name} case={case_id} "
                            f"method={context_method} "
                            f"cfg_sha={config_sha[:8] if config_sha else None} "
                            f"shim_sha={shim_sha[:8] if shim_sha else None}"
                        )
                    else:
                        md = row.setdefault("metadata", {})
                        md["cache_key"] = key
                        md["diagnoser_config_sha256"] = config_sha
                        md["shim_sha256"] = shim_sha
                        cache_file = cache_root / f"{key}.json"
                        cache_file.write_text(
                            json.dumps(
                                {"cache_key": key, "row": row},
                                ensure_ascii=False, indent=2,
                            ) + "\n",
                            encoding="utf-8",
                        )
                    written += 1
    return written, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=REPO / "results")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    total_written = total_skipped = 0
    for split_dir in sorted(args.results_dir.iterdir()):
        if not split_dir.is_dir():
            continue
        if not (split_dir / "diagnoses").exists():
            continue
        print(f"== {split_dir.name} ==")
        w, s = rebuild_split(split_dir, args.dry_run)
        print(f"  written={w} skipped={s}")
        total_written += w
        total_skipped += s
    print(f"\nTotal: written={total_written} skipped={total_skipped}")


if __name__ == "__main__":
    sys.exit(main() or 0)
