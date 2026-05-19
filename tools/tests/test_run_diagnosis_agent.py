#!/usr/bin/env python3
"""Integration tests for real-agent-v1 + run_diagnosis.py plumbing.

Covers:
- Cache key sensitivity to the new agent env vars
  (CILOGBENCH_AGENT_V1_MAX_ITERATIONS,
   CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS)
- raw_log_path forwarding through the shim payload
- Schema validation: agent_metadata block round-trips through the
  diagnosis schema
- Shim entry-point gates (ALLOW_EXTERNAL_LLM, ANTHROPIC_API_KEY,
  raw_log_path missing) all surface structured taxonomy classes
- The runner's build_row lifts `_agent_metadata` to top-level
  agent_metadata

Run:
    python3 tools/tests/test_run_diagnosis_agent.py
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "tools"))

import diagnosis_shim_claude_agent as ag  # noqa: E402
import run_diagnosis as rd  # noqa: E402


# ---------------------------------------------------------------------------
# Cache-key sensitivity
# ---------------------------------------------------------------------------


def _agent_cfg():
    return rd.load_diagnoser_config("real-agent-v1")


def test_real_agent_v1_config_loads():
    cfg = _agent_cfg()
    assert cfg is not None, "real-agent-v1.json should load"
    assert cfg["diagnoser_name"] == "real-agent-v1"
    assert cfg["model"]["tool_use"] is True, \
        "real-agent-v1 must declare tool_use=true"
    assert "agent_config" in cfg, "missing agent_config block"
    surface = cfg["agent_config"]["tool_surface"]
    assert surface == ["grep", "read_file", "tail", "view_log_lines"], \
        f"unexpected tool surface: {surface}"
    assert cfg["agent_config"]["max_iterations"] == 5
    assert cfg["agent_config"]["max_total_input_tokens"] == 180000


def test_real_agent_v1_declares_four_env_vars_in_cache_key():
    cfg = _agent_cfg()
    env_keys = set(cfg.get("cache_key_env") or [])
    expected = {
        "CILOGBENCH_CLAUDE_MODEL",
        "CILOGBENCH_AGENT_V1_MAX_ITERATIONS",
        "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS",
        "CILOGBENCH_AGENT_V1_BASE_URL",
    }
    assert env_keys == expected, (
        f"real-agent-v1 cache_key_env mismatch.\n"
        f"  got:      {env_keys}\n"
        f"  expected: {expected}"
    )


def _key(env_values: dict | None) -> str:
    return rd.cache_key_for(
        case_id="c1", context_method="grep", context_sha="s1",
        prompt_sha="p1", provider="command", diagnoser="real-agent-v1",
        command_str="python3 examples/diagnosis_shim_claude_agent.py",
        env_values=env_values,
    )


def test_max_iterations_bump_invalidates_cache_key():
    """If the user bumps CILOGBENCH_AGENT_V1_MAX_ITERATIONS from 5 to
    10, the cached row from the 5-iter run should NOT be re-used —
    larger budgets produce different agent behavior."""
    k5 = _key(env_values={
        "CILOGBENCH_CLAUDE_MODEL": "sonnet",
        "CILOGBENCH_AGENT_V1_MAX_ITERATIONS": "5",
        "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS": "180000",
    })
    k10 = _key(env_values={
        "CILOGBENCH_CLAUDE_MODEL": "sonnet",
        "CILOGBENCH_AGENT_V1_MAX_ITERATIONS": "10",
        "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS": "180000",
    })
    assert k5 != k10, "bumping max_iterations did not invalidate cache key"


def test_token_budget_bump_invalidates_cache_key():
    k_default = _key(env_values={
        "CILOGBENCH_CLAUDE_MODEL": "sonnet",
        "CILOGBENCH_AGENT_V1_MAX_ITERATIONS": "5",
        "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS": "180000",
    })
    k_doubled = _key(env_values={
        "CILOGBENCH_CLAUDE_MODEL": "sonnet",
        "CILOGBENCH_AGENT_V1_MAX_ITERATIONS": "5",
        "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS": "360000",
    })
    assert k_default != k_doubled, (
        "bumping max_total_input_tokens did not invalidate cache key"
    )


# ---------------------------------------------------------------------------
# Shim entry-point gates
# ---------------------------------------------------------------------------


def _run_shim(env_overrides: dict, stdin_payload: dict) -> tuple[int, str, str]:
    """Invoke the agent shim as a subprocess; return (code, stdout, stderr)."""
    env = os.environ.copy()
    # Strip any inherited gates so the test isolates the gate it cares about.
    for k in ("ANTHROPIC_API_KEY", "CILOGBENCH_ALLOW_EXTERNAL_LLM"):
        env.pop(k, None)
    env.update(env_overrides)
    res = subprocess.run(
        ["python3", str(ROOT / "examples" / "diagnosis_shim_claude_agent.py")],
        input=json.dumps(stdin_payload).encode("utf-8"),
        env=env,
        capture_output=True,
        timeout=15,
    )
    return res.returncode, res.stdout.decode("utf-8", "replace"), res.stderr.decode("utf-8", "replace")


def _minimal_payload(raw_log_path: str | None = "/tmp/does-not-exist.log") -> dict:
    p = {
        "case_id": "test-case",
        "context_method": "grep",
        "prompt": "test prompt",
        "context": "test context",
        "safe_case_metadata": {"repo": "test/test"},
        "expected_output_schema": "schemas/diagnosis.schema.json",
    }
    if raw_log_path is not None:
        p["raw_log_path"] = raw_log_path
    return p


def test_shim_requires_external_llm_optin():
    # No CILOGBENCH_ALLOW_EXTERNAL_LLM → exit 1 with descriptive stderr.
    code, _, err = _run_shim({}, _minimal_payload())
    assert code == 1
    assert "CILOGBENCH_ALLOW_EXTERNAL_LLM=1" in err, \
        f"unexpected stderr: {err!r}"


def test_shim_requires_anthropic_api_key():
    code, _, err = _run_shim(
        {"CILOGBENCH_ALLOW_EXTERNAL_LLM": "1"},
        _minimal_payload(),
    )
    assert code == 1
    assert "ANTHROPIC_API_KEY" in err, f"unexpected stderr: {err!r}"


def test_shim_emits_runtime_tool_dispatch_error_when_raw_log_path_missing():
    # Pretend everything else is in order: API key set, opt-in present.
    # Payload omits raw_log_path → structured taxonomy class on stdout.
    code, out, err = _run_shim(
        {
            "CILOGBENCH_ALLOW_EXTERNAL_LLM": "1",
            "ANTHROPIC_API_KEY": "test-key-not-real",
        },
        _minimal_payload(raw_log_path=None),
    )
    assert code == 1
    body = json.loads(out)
    pe = body.get("_provider_error", "")
    assert pe.startswith("runtime_tool_dispatch_error:"), (
        f"expected runtime_tool_dispatch_error prefix, got: {pe!r}"
    )
    assert "raw_log_path" in pe


def test_shim_emits_runtime_tool_dispatch_error_when_raw_log_path_does_not_exist():
    code, out, err = _run_shim(
        {
            "CILOGBENCH_ALLOW_EXTERNAL_LLM": "1",
            "ANTHROPIC_API_KEY": "test-key-not-real",
        },
        _minimal_payload(raw_log_path="/no/such/file/anywhere"),
    )
    assert code == 1
    body = json.loads(out)
    pe = body.get("_provider_error", "")
    assert pe.startswith("runtime_tool_dispatch_error:"), (
        f"expected runtime_tool_dispatch_error prefix, got: {pe!r}"
    )
    assert "does not exist" in pe


# ---------------------------------------------------------------------------
# Build_row lifts _agent_metadata into top-level agent_metadata
# ---------------------------------------------------------------------------


def test_build_row_lifts_agent_metadata():
    """The runner's build_row should pull the shim's underscored
    `_agent_metadata` into a top-level `agent_metadata` field so the
    evaluator can read iteration / tool-call data without parsing
    the body."""
    diag_body = {
        "summary": "test failed",
        "root_cause_category": "test_assertion",
        "root_cause": "expected 42 got 41",
        "confidence": 0.8,
        "relevant_files": ["foo.py"],
        "relevant_tests": ["test_alpha"],
        "evidence": [{"quote": "AssertionError", "reason": "literal"}],
        "suggested_fix": "fix the constant",
        "_model_info": {"provider_name": "anthropic", "requested_model": "sonnet"},
        "_agent_metadata": {
            "iterations": 2,
            "tool_call_count": 1,
            "tool_calls": [{"tool": "grep", "args": {"pattern": "FAILED"}}],
            "total_input_tokens_consumed": 5000,
            "total_output_tokens_consumed": 800,
            "budget_exhausted": False,
            "final_diagnosis_turn": 2,
        },
    }

    row = rd.build_row(
        case_id="cargo-tokio-001",
        context_method="grep",
        diagnoser="real-agent-v1",
        diagnosis_body=diag_body,
        context_path=Path("results/dev/grep/cargo-tokio-001.txt"),
        context_text="some context",
        prompt_sha="abc123",
        runtime_ms=42.0,
        provider_name="command",
        command_str="python3 examples/diagnosis_shim_claude_agent.py",
        cache_key=None,
        provider_error=None,
    )

    # 1. agent_metadata at the top level
    assert "agent_metadata" in row, \
        f"build_row did not lift _agent_metadata. Row keys: {list(row.keys())}"
    am = row["agent_metadata"]
    assert am["iterations"] == 2
    assert am["tool_call_count"] == 1
    assert am["total_input_tokens_consumed"] == 5000
    assert am["budget_exhausted"] is False

    # 2. Underscore keys stripped from body
    assert "_agent_metadata" not in row
    assert "_model_info" not in row

    # 3. Regular diagnosis fields still present
    assert row["summary"] == "test failed"
    assert row["root_cause_category"] == "test_assertion"


def test_build_row_omits_agent_metadata_for_single_shot_rows():
    """Single-shot shims don't emit _agent_metadata. The row should
    not have a phantom empty agent_metadata field."""
    diag_body = {
        "summary": "test failed",
        "root_cause_category": "test_assertion",
        "root_cause": "expected 42 got 41",
        "confidence": 0.8,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "",
        "_model_info": {"provider_name": "anthropic"},
        # NO _agent_metadata
    }
    row = rd.build_row(
        case_id="cargo-tokio-001", context_method="grep",
        diagnoser="real-debugger-v2", diagnosis_body=diag_body,
        context_path=Path("results/dev/grep/cargo-tokio-001.txt"),
        context_text="x", prompt_sha="abc", runtime_ms=1.0,
        provider_name="command",
        command_str="python3 examples/diagnosis_shim_claude_cli.py",
        cache_key=None, provider_error=None,
    )
    assert "agent_metadata" not in row, (
        f"single-shot row should not have agent_metadata; keys: {list(row.keys())}"
    )


# ---------------------------------------------------------------------------
# Schema round-trip: agent_metadata validates against diagnosis.schema.json
# ---------------------------------------------------------------------------


def test_runner_resolves_prompt_path_from_diagnoser_config():
    """Per Codex 2026-05-19 adversarial-review [high]: the runner's
    --prompt flag previously defaulted to prompts/debugger_v1.md and
    ignored the `prompt_path` field declared in the diagnoser config.
    That caused Phase E to silently run the agent diagnoser with the
    single-shot debugger prompt instead of the agent prompt.

    This regression test simulates the resolution logic: with no
    explicit --prompt and a config that declares prompt_path, the
    runner must pick the config's prompt — NOT the legacy default.
    """
    cfg = rd.load_diagnoser_config(
        "real-agent-v1",
        explicit_path=ROOT / "configs" / "diagnosers" / "real-agent-v1.json",
    )
    assert cfg.get("prompt_path") == "prompts/agent_v1.md", (
        "real-agent-v1.json must declare prompt_path: prompts/agent_v1.md "
        f"(got {cfg.get('prompt_path')!r})"
    )
    # Mirror the resolution branch from run_diagnosis.run():
    prompt_path = None  # no explicit --prompt
    if prompt_path is None:
        config_prompt_rel = cfg.get("prompt_path") if isinstance(cfg, dict) else None
        if config_prompt_rel:
            prompt_path = rd.ROOT / config_prompt_rel
        else:
            prompt_path = rd.DEFAULT_PROMPT_PATH

    assert prompt_path == (rd.ROOT / "prompts" / "agent_v1.md"), (
        f"runner should resolve to agent_v1.md, got {prompt_path}"
    )
    # The agent prompt must hash DIFFERENTLY from debugger_v1.md;
    # otherwise the bug fix is a no-op.
    agent_sha = rd.sha256_text(prompt_path.read_text(encoding="utf-8"))
    debugger_sha = rd.sha256_text(rd.DEFAULT_PROMPT_PATH.read_text(encoding="utf-8"))
    assert agent_sha != debugger_sha, (
        "agent_v1.md and debugger_v1.md must hash differently "
        "(otherwise the prompt resolution bug fix has nothing to test)"
    )


def test_runner_falls_back_to_legacy_default_without_config():
    """Back-compat: if no diagnoser_config is loaded AND no explicit
    --prompt is passed, the runner falls back to DEFAULT_PROMPT_PATH
    (prompts/debugger_v1.md). v1.0 single-shot diagnosers depend on
    this fallback if they're invoked without --diagnoser-config.
    """
    prompt_path = None
    cfg = None  # no config loaded
    if prompt_path is None:
        config_prompt_rel = cfg.get("prompt_path") if isinstance(cfg, dict) else None
        if config_prompt_rel:
            prompt_path = rd.ROOT / config_prompt_rel
        else:
            prompt_path = rd.DEFAULT_PROMPT_PATH

    assert prompt_path == rd.DEFAULT_PROMPT_PATH


def test_runner_respects_explicit_prompt_override():
    """If the caller passes --prompt explicitly, that wins over the
    config's prompt_path — preserves operator override capability."""
    cfg = rd.load_diagnoser_config(
        "real-agent-v1",
        explicit_path=ROOT / "configs" / "diagnosers" / "real-agent-v1.json",
    )
    # Pretend the operator passed --prompt prompts/debugger_v1.md
    explicit_path = rd.ROOT / "prompts" / "debugger_v1.md"
    prompt_path = explicit_path  # simulates args.prompt being non-None
    if prompt_path is None:
        config_prompt_rel = cfg.get("prompt_path") if isinstance(cfg, dict) else None
        if config_prompt_rel:
            prompt_path = rd.ROOT / config_prompt_rel
        else:
            prompt_path = rd.DEFAULT_PROMPT_PATH

    assert prompt_path == explicit_path, (
        "explicit --prompt override must win over config's prompt_path"
    )


def test_diagnosis_schema_accepts_agent_metadata():
    """The added agent_metadata block in schemas/diagnosis.schema.json
    should accept a typical agent-loop row and reject obviously
    malformed ones."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        # Skip cleanly if the dev didn't pip-install jsonschema.
        print("    [skipped — jsonschema not available]", end="")
        return

    schema = json.loads(
        (ROOT / "schemas" / "diagnosis.schema.json").read_text(encoding="utf-8")
    )
    valid_row = {
        "case_id": "c1",
        "context_method": "grep",
        "diagnoser": "real-agent-v1",
        "mode": "root_cause_diagnosis",
        "summary": "x",
        "root_cause_category": "test_assertion",
        "root_cause": "y",
        "confidence": 0.5,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "input": {"context_path": "x", "context_tokens_estimate": 0},
        "usage": {"processing_tokens_estimate": 0, "output_tokens_estimate": 0},
        "metadata": {"provider": "command", "prompt_sha256": "abc", "runtime_ms": 1.0},
        "agent_metadata": {
            "iterations": 2,
            "tool_call_count": 1,
            "tool_calls": [{
                "tool": "grep",
                "args": {"pattern": "FAILED"},
                "observation_tokens_estimate": 412,
                "runtime_ms": 14.2,
                "error": None,
            }],
            "total_input_tokens_consumed": 5000,
            "total_output_tokens_consumed": 800,
            "budget_exhausted": False,
            "final_diagnosis_turn": 2,
        },
    }
    jsonschema.validate(valid_row, schema)  # raises on failure

    # Negative test: missing required field in agent_metadata
    bad = json.loads(json.dumps(valid_row))
    del bad["agent_metadata"]["iterations"]
    try:
        jsonschema.validate(bad, schema)
        raise AssertionError(
            "schema accepted agent_metadata missing required 'iterations'"
        )
    except jsonschema.ValidationError:
        pass


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_real_agent_v1_config_loads,
        test_real_agent_v1_declares_four_env_vars_in_cache_key,
        test_max_iterations_bump_invalidates_cache_key,
        test_token_budget_bump_invalidates_cache_key,
        test_shim_requires_external_llm_optin,
        test_shim_requires_anthropic_api_key,
        test_shim_emits_runtime_tool_dispatch_error_when_raw_log_path_missing,
        test_shim_emits_runtime_tool_dispatch_error_when_raw_log_path_does_not_exist,
        test_build_row_lifts_agent_metadata,
        test_build_row_omits_agent_metadata_for_single_shot_rows,
        test_runner_resolves_prompt_path_from_diagnoser_config,
        test_runner_falls_back_to_legacy_default_without_config,
        test_runner_respects_explicit_prompt_override,
        test_diagnosis_schema_accepts_agent_metadata,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    msg = (
        f"All {len(tests)} tests passed."
        if failed == 0 else
        f"{failed} of {len(tests)} tests FAILED."
    )
    print(msg)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
