#!/usr/bin/env python3
"""Create the single fixed Drain3 baseline for the LogDx v1.3 study."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "configs" / "drain3" / "drain3-templates.json"
SCHEMA_PATH = ROOT / "schemas" / "method_output.schema.json"

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover - CI installs jsonschema
    jsonschema = None

try:
    from drain3 import TemplateMiner  # type: ignore
    from drain3.template_miner_config import TemplateMinerConfig  # type: ignore
except ImportError:  # pragma: no cover - handled with a clear runtime error
    TemplateMiner = None
    TemplateMinerConfig = None


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_miner(config: dict):
    if TemplateMiner is None or TemplateMinerConfig is None:
        raise RuntimeError(
            "Drain3 is not installed. Run `python3 -m pip install 'drain3==0.9.11'`."
        )
    miner_config = TemplateMinerConfig()
    miner_config.profiling_enabled = False
    miner_config.drain_sim_th = float(config["sim_th"])
    miner_config.drain_depth = int(config["depth"])
    miner_config.drain_max_children = int(config["max_children"])
    miner_config.drain_max_clusters = config.get("max_clusters")
    miner_config.parametrize_numeric_tokens = bool(config["parametrize_numeric_tokens"])
    miner_config.masking_instructions = []
    return TemplateMiner(config=miner_config)


def reduce_log(raw_text: str, config: dict) -> tuple[str, dict]:
    miner = make_miner(config)
    first_seen: dict[int, int] = {}
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        result = miner.add_log_message(line)
        cluster_id = int(result["cluster_id"])
        first_seen.setdefault(cluster_id, line_number)

    clusters = []
    for cluster in miner.drain.clusters:
        template = " ".join(cluster.log_template_tokens)
        clusters.append(
            {
                "cluster_id": int(cluster.cluster_id),
                "count": int(cluster.size),
                "template": template,
                "first_line": first_seen[int(cluster.cluster_id)],
            }
        )
    clusters.sort(key=lambda item: (item["first_line"], item["template"]))
    output_lines: list[str] = []
    max_chars = int(config["max_output_line_chars"])
    overlap = int(config["chunk_overlap_chars"])
    payload_chars = max_chars - 80
    for item in clusters:
        template = item["template"]
        if len(template) <= payload_chars:
            parts = [template]
        else:
            step = payload_chars - overlap
            parts = [
                template[start : start + payload_chars]
                for start in range(0, len(template), step)
            ]
        for index, part in enumerate(parts, start=1):
            output_lines.append(
                f"COUNT={item['count']} TEMPLATE_PART={index}/{len(parts)} {part}"
            )
    output = "\n".join(output_lines)
    if output:
        output += "\n"
    return output, {
        "cluster_count": len(clusters),
        "input_message_count": len(raw_text.splitlines()),
        "clusters": clusters,
    }


def build_row(
    *, case_id: str, raw_path: Path, context_path: Path, raw_text: str,
    output_text: str, details: dict, config: dict, config_path: Path,
) -> dict:
    input_bytes = len(raw_text.encode("utf-8"))
    output_bytes = len(output_text.encode("utf-8"))
    reduction_ratio = 0.0 if not input_bytes else 1 - output_bytes / input_bytes
    return {
        "case_id": case_id,
        "method": config["method"],
        "mode": "context_provider",
        "raw_log_path": str(raw_path.relative_to(ROOT)),
        "context_path": str(context_path.relative_to(ROOT)),
        "input_line_count": len(raw_text.splitlines()),
        "output_line_count": len(output_text.splitlines()),
        "input_byte_size": input_bytes,
        "output_byte_size": output_bytes,
        "reduction_ratio": round(max(0.0, min(1.0, reduction_ratio)), 6),
        "included_line_ranges": [],
        "line_mapping_available": False,
        "mapping_type": "text",
        "metadata": {
            "provider": "drain3",
            "version": importlib.metadata.version("drain3"),
            "config_path": str(config_path.relative_to(ROOT)),
            "config_sha256": sha256_path(config_path),
            "configuration_scope": config["configuration_scope"],
            "cluster_count": details["cluster_count"],
            "input_message_count": details["input_message_count"],
            "stable_order": config["output_order"],
            "parametrize_numeric_tokens": config["parametrize_numeric_tokens"],
        },
    }


def validate_row(row: dict) -> None:
    if jsonschema is not None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)


def run(*, split: str, results_dir: Path, config_path: Path) -> int:
    # Manifests store repository-relative paths. Reject unsupported output
    # locations before creating files, and accept ordinary relative paths.
    results_dir = results_dir.resolve()
    config_path = config_path.resolve()
    split_path = Path(split)
    if split_path.is_absolute() or ".." in split_path.parts:
        raise ValueError("split must be a relative path without '..'")
    for label, path in (("results-dir", results_dir), ("config", config_path)):
        if not path.is_relative_to(ROOT):
            raise ValueError(f"{label} must be inside the repository: {path}")
    cases_dir = (ROOT / "cases" / split).resolve()
    if not cases_dir.is_relative_to(ROOT / "cases"):
        raise ValueError("split must be inside the repository cases directory")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    installed = importlib.metadata.version("drain3")
    if installed != config["drain3_version"]:
        raise RuntimeError(
            f"Drain3 version mismatch: installed={installed}, "
            f"config={config['drain3_version']}"
        )
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"split not found: {cases_dir}")
    method = config["method"]
    output_dir = (results_dir / split / method).resolve()
    manifest_path = (results_dir / split / f"{method}.jsonl").resolve()
    if not output_dir.is_relative_to(results_dir) or not manifest_path.is_relative_to(results_dir):
        raise ValueError("output paths must stay inside results-dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for case_dir in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
        raw_path = case_dir / "raw.log"
        if not raw_path.exists():
            continue
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        output_text, details = reduce_log(raw_text, config)
        context_path = output_dir / f"{case_dir.name}.txt"
        context_path.write_text(output_text, encoding="utf-8")
        row = build_row(
            case_id=case_dir.name,
            raw_path=raw_path,
            context_path=context_path,
            raw_text=raw_text,
            output_text=output_text,
            details=details,
            config=config,
            config_path=config_path,
        )
        validate_row(row)
        rows.append(row)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {manifest_path.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        return run(
            split=args.split,
            results_dir=args.results_dir,
            config_path=args.config.resolve(),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
