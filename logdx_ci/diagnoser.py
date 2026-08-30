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

SUPPORTED_DIAGNOSERS = [
    "static-signal-recall",
    "stub-debugger-v1",
    "real-debugger-v1",   # Haiku 4.5 single-shot via `claude` CLI
    "real-debugger-v2",   # Sonnet 4.6 single-shot via `claude` CLI
    "real-debugger-v3",   # gpt-5-mini single-shot via OpenAI HTTPS
    "real-agent-v1",      # Sonnet 4.6 + 4 tools + 5-turn cap via OpenRouter/Anthropic
    "copilot-gpt-5-mini-compat",
    "copilot-luna-compat",
    "copilot-terra-compat",
    "copilot-sol-compat",
    "copilot-luna-native-long",
    "copilot-terra-native-long",
    "copilot-sol-native-long",
]

# Modes that don't call any LLM — score reducer output directly vs ground truth.
STATIC_MODES = {"static-signal-recall"}

# Modes that need access to the raw.log via the `raw_log_path` payload field
# (agent diagnosers can grep / read_file / tail / view_log_lines on it).
AGENT_MODES = {"real-agent-v1"}

SHIM_BY_DIAGNOSER = {
    "stub-debugger-v1": "examples/diagnosis_shim_stub.py",
    "real-debugger-v1": "examples/diagnosis_shim_claude_cli.py",
    "real-debugger-v2": "examples/diagnosis_shim_claude_cli.py",
    "real-debugger-v3": "examples/diagnosis_shim_openai.py",
    "real-agent-v1":    "examples/diagnosis_shim_claude_agent.py",
    "copilot-gpt-5-mini-compat": "examples/diagnosis_shim_copilot_cli.py",
    "copilot-luna-compat": "examples/diagnosis_shim_copilot_cli.py",
    "copilot-terra-compat": "examples/diagnosis_shim_copilot_cli.py",
    "copilot-sol-compat": "examples/diagnosis_shim_copilot_cli.py",
    "copilot-luna-native-long": "examples/diagnosis_shim_copilot_sdk.py",
    "copilot-terra-native-long": "examples/diagnosis_shim_copilot_sdk.py",
    "copilot-sol-native-long": "examples/diagnosis_shim_copilot_sdk.py",
}

# Per-diagnoser prompt template (relative to repo root).
PROMPT_BY_DIAGNOSER = {
    "stub-debugger-v1": "prompts/debugger_v1.md",
    "real-debugger-v1": "prompts/debugger_v1.md",
    "real-debugger-v2": "prompts/debugger_v1.md",
    "real-debugger-v3": "prompts/debugger_v1.md",
    "real-agent-v1":    "prompts/agent_v1.md",
    "copilot-gpt-5-mini-compat": "prompts/debugger_v1.md",
    "copilot-luna-compat": "prompts/debugger_v1.md",
    "copilot-terra-compat": "prompts/debugger_v1.md",
    "copilot-sol-compat": "prompts/debugger_v1.md",
    "copilot-luna-native-long": "prompts/debugger_v1.md",
    "copilot-terra-native-long": "prompts/debugger_v1.md",
    "copilot-sol-native-long": "prompts/debugger_v1.md",
}

# Per-diagnoser shim env defaults — model alias, provider config.
SHIM_ENV_BY_DIAGNOSER = {
    "real-debugger-v1": {"CILOGBENCH_CLAUDE_MODEL": "haiku"},
    "real-debugger-v2": {"CILOGBENCH_CLAUDE_MODEL": "sonnet"},
    "real-debugger-v3": {"CILOGBENCH_OPENAI_MODEL": "gpt-5-mini"},
    "real-agent-v1":    {"CILOGBENCH_CLAUDE_MODEL": "anthropic/claude-sonnet-4.6"},
    "copilot-gpt-5-mini-compat": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5-mini",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "default",
        "CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS": "480000",
    },
    "copilot-luna-compat": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-luna",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "default",
        "CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS": "480000",
    },
    "copilot-terra-compat": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-terra",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "default",
        "CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS": "480000",
    },
    "copilot-sol-compat": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-sol",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "default",
        "CILOGBENCH_COPILOT_MAX_CONTEXT_CHARS": "480000",
    },
    "copilot-luna-native-long": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-luna",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "long_context",
    },
    "copilot-terra-native-long": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-terra",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "long_context",
    },
    "copilot-sol-native-long": {
        "CILOGBENCH_COPILOT_MODEL": "gpt-5.6-sol",
        "CILOGBENCH_COPILOT_REASONING_EFFORT": "low",
        "CILOGBENCH_COPILOT_CONTEXT_MODE": "long_context",
    },
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _effective_shim_env(diagnoser: str) -> dict[str, str]:
    values = dict(SHIM_ENV_BY_DIAGNOSER.get(diagnoser, {}))
    for key in tuple(values):
        if os.environ.get(key) is not None:
            values[key] = os.environ[key]
    return values


def _cache_identity(
    *, diagnoser: str, case_id: str, reduced_context: str,
    prompt_path: Path, shim_path: Path, config_path: Path,
) -> dict:
    """Return every output-affecting SDK cache identity field."""
    return {
        "diagnoser": diagnoser,
        "case_id": case_id,
        "reduced_context_sha256": _sha256_bytes(reduced_context.encode("utf-8")),
        "prompt_sha256": _sha256_bytes(prompt_path.read_bytes()),
        "shim_sha256": _sha256_bytes(shim_path.read_bytes()),
        "diagnoser_config_sha256": (
            _sha256_bytes(config_path.read_bytes()) if config_path.exists() else None
        ),
        "shim_env": _effective_shim_env(diagnoser),
    }


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
    if diagnoser in ("real-debugger-v1", "real-debugger-v2"):
        if shutil.which("claude") is None:
            raise RuntimeError(
                f"{diagnoser} requires the `claude` CLI on PATH "
                "(github.com/anthropics/claude-code). Install with: "
                "npm install -g @anthropic-ai/claude-code, then retry."
            )
    if diagnoser == "real-debugger-v3":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "real-debugger-v3 requires the OPENAI_API_KEY env var. "
                "Set it in your shell or pass api_key=... to evaluate()."
            )
    if diagnoser == "real-agent-v1":
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
        if not (has_anthropic or has_openrouter):
            raise RuntimeError(
                "real-agent-v1 requires ANTHROPIC_API_KEY (direct) or "
                "OPENROUTER_API_KEY (proxy). Set one and retry."
            )
    if diagnoser.startswith("copilot-") and shutil.which("copilot") is None:
        raise RuntimeError(
            f"{diagnoser} requires the GitHub Copilot CLI on PATH."
        )


def is_static(diagnoser: str) -> bool:
    return diagnoser in STATIC_MODES


def diagnose(
    *,
    diagnoser: str,
    case_id: str,
    reduced_context: str,
    case_metadata: dict,
    cache_dir: Path | None = None,
    api_key: str | None = None,  # reserved for V0.2 anthropic-SDK fallback
    raw_log_path: Path | str | None = None,  # required for agent diagnosers
) -> dict:
    """Run a diagnoser on reduced context. Cached when cache_dir is set."""
    if diagnoser not in SUPPORTED_DIAGNOSERS:
        raise ValueError(
            f"Unknown diagnoser {diagnoser!r}. "
            f"Supported in V0: {SUPPORTED_DIAGNOSERS}"
        )
    if diagnoser in AGENT_MODES and raw_log_path is None:
        raise ValueError(
            f"{diagnoser} is an agent diagnoser and needs `raw_log_path` "
            "to dispatch its grep/read_file/tail/view_log_lines tools. "
            "This is normally wired up automatically by evaluate()."
        )

    root = find_repo_root()
    shim = root / SHIM_BY_DIAGNOSER[diagnoser]
    prompt_path = root / PROMPT_BY_DIAGNOSER[diagnoser]
    config_path = root / "configs" / "diagnosers" / f"{diagnoser}.json"
    if not shim.exists():
        raise FileNotFoundError(f"Diagnoser shim not found: {shim}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Diagnoser prompt not found: {prompt_path}")

    cache_path = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        identity = _cache_identity(
            diagnoser=diagnoser,
            case_id=case_id,
            reduced_context=reduced_context,
            prompt_path=prompt_path,
            shim_path=shim,
            config_path=config_path,
        )
        key = _hash(json.dumps(identity, sort_keys=True, separators=(",", ":")))
        cache_path = cache_dir / f"{diagnoser}__{case_id}__{key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())

    prompt_text = prompt_path.read_text()

    payload = {
        "case_id": case_id,
        "context_method": "user_reducer",
        "prompt": prompt_text,
        "context": reduced_context,
        "safe_case_metadata": _build_safe_metadata(case_id, case_metadata),
        "expected_output_schema": "schemas/diagnosis.schema.json",
    }
    if raw_log_path is not None:
        payload["raw_log_path"] = str(Path(raw_log_path).resolve())

    env = os.environ.copy()
    for k, v in SHIM_ENV_BY_DIAGNOSER.get(diagnoser, {}).items():
        env.setdefault(k, v)
    if diagnoser.startswith("real-") or diagnoser.startswith("copilot-"):
        env.setdefault("CILOGBENCH_ALLOW_EXTERNAL_LLM", "1")
    if api_key:
        if diagnoser == "real-debugger-v3":
            env["OPENAI_API_KEY"] = api_key
        elif diagnoser == "real-agent-v1":
            # Agent shim prefers OPENROUTER then ANTHROPIC; pass to whichever
            # is currently in env, default to OPENROUTER.
            if "OPENROUTER_API_KEY" in env:
                env["OPENROUTER_API_KEY"] = api_key
            else:
                env["ANTHROPIC_API_KEY"] = api_key
        elif diagnoser.startswith("real-debugger-v"):
            env["ANTHROPIC_API_KEY"] = api_key

    # Agent diagnoser is multi-turn; default to a higher timeout (~300s)
    # and let the shim's own per-API timeouts handle the per-turn budget.
    timeout = 30 if diagnoser == "stub-debugger-v1" else (
        360 if diagnoser.startswith("copilot-") else (
            300 if diagnoser in AGENT_MODES else 180
        )
    )
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
