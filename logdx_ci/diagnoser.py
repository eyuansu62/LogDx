"""Diagnoser wrappers — call an LLM (or stub) on reduced context, return diagnosis JSON.

V0 invokes the canonical shim subprocesses used by tools/run_diagnosis.py.
This guarantees bit-for-bit-comparable scores to the v1.2 leaderboard.

Supported diagnoser names (V0):
  - "stub-debugger-v1": deterministic, no API key. Smoke tests only.
  - "real-debugger-v2": Claude Sonnet 4.6 via the `claude` CLI shim.

V0.2 will add "real-debugger-v1" (Haiku), "real-debugger-v3" (gpt-5-mini),
"real-agent-v1" (agent + 4 tools), and an Anthropic-SDK fallback for
external users without the `claude` CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .corpus import find_repo_root

SUPPORTED_DIAGNOSERS = ["stub-debugger-v1", "real-debugger-v2"]

SHIM_BY_DIAGNOSER = {
    "stub-debugger-v1": "examples/diagnosis_shim_stub.py",
    "real-debugger-v2": "examples/diagnosis_shim_claude_cli.py",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _build_safe_metadata(case_id: str, case_metadata: dict) -> dict:
    """Allow-list safe fields from case.json (mirrors tools/run_diagnosis.py)."""
    return {
        "case_id": case_id,
        "repo": case_metadata.get("repo", ""),
        "framework": case_metadata.get("framework", ""),
        "workflow_name": case_metadata.get("workflow_name", ""),
        "job_name": case_metadata.get("job_name", ""),
        "line_count": case_metadata.get("line_count", 0),
        "byte_size": case_metadata.get("byte_size", 0),
    }


def preflight(diagnoser: str) -> None:
    """Raise a clear error early if the diagnoser's requirements aren't met."""
    if diagnoser == "real-debugger-v2":
        if shutil.which("claude") is None:
            raise RuntimeError(
                "real-debugger-v2 requires the `claude` CLI on PATH "
                "(github.com/anthropics/claude-code). Install with: "
                "npm install -g @anthropic-ai/claude-code, then retry."
            )


def diagnose(
    *,
    diagnoser: str,
    case_id: str,
    reduced_context: str,
    case_metadata: dict,
    cache_dir: Path | None = None,
    api_key: str | None = None,  # reserved for V0.2 anthropic-SDK fallback
) -> dict:
    """Run a diagnoser on reduced context. Cached when cache_dir is set."""
    if diagnoser not in SUPPORTED_DIAGNOSERS:
        raise ValueError(
            f"Unknown diagnoser {diagnoser!r}. "
            f"Supported in V0: {SUPPORTED_DIAGNOSERS}"
        )

    cache_path = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = _hash(f"{diagnoser}::{case_id}::{reduced_context}")
        cache_path = cache_dir / f"{diagnoser}__{case_id}__{key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())

    root = find_repo_root()
    shim = root / SHIM_BY_DIAGNOSER[diagnoser]
    if not shim.exists():
        raise FileNotFoundError(f"Diagnoser shim not found: {shim}")
    prompt_text = (root / "prompts" / "debugger_v1.md").read_text()

    payload = {
        "case_id": case_id,
        "context_method": "user_reducer",
        "prompt": prompt_text,
        "context": reduced_context,
        "safe_case_metadata": _build_safe_metadata(case_id, case_metadata),
        "expected_output_schema": "schemas/diagnosis.schema.json",
    }

    env = os.environ.copy()
    if diagnoser == "real-debugger-v2":
        env.setdefault("CILOGBENCH_CLAUDE_MODEL", "sonnet")
        env.setdefault("CILOGBENCH_ALLOW_EXTERNAL_LLM", "1")

    timeout = 30 if diagnoser == "stub-debugger-v1" else 180
    proc = subprocess.run(
        [sys.executable, str(shim)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        env=env,
        cwd=str(root),
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[:600]
        raise RuntimeError(
            f"{diagnoser} shim exited {proc.returncode}: {err}"
        )

    try:
        out = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        head = (proc.stdout or b"").decode("utf-8", errors="replace")[:400]
        raise RuntimeError(
            f"{diagnoser} shim returned non-JSON: {e}. First 400 chars: {head!r}"
        ) from e

    # Fill in the schema fields the scorer expects but the shim doesn't emit.
    out.setdefault("case_id", case_id)
    out.setdefault("context_method", "user_reducer")
    out.setdefault("diagnoser", diagnoser)
    out.setdefault("mode", "root_cause_diagnosis")
    out.setdefault("input", {"context_chars": len(reduced_context)})
    out.setdefault("usage", {"input_tokens": None, "output_tokens": None})
    out.setdefault("metadata", {})

    if cache_path is not None:
        cache_path.write_text(json.dumps(out))
    return out
