#!/usr/bin/env python3
"""
E3 LLM-summary shim backed by the `claude` CLI (Claude Code, print mode).

Speaks the M4 command-provider contract used by
`tools/run_llm_summary_baseline.py`:

  stdin  = {"messages":[{role,content}], "temperature":...,
            "max_output_chars":..., "metadata":{case_id, prompt_version, stage}}
  stdout = {"content": "...", "provider": "...", "model": null,
            "usage": {"input_tokens":..., "output_tokens":...}}

Usage:
    export LLM_SUMMARY_COMMAND="python3 $(pwd)/examples/summary_shim_claude_cli.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

Optional env overrides:
    CILOGBENCH_CLAUDE_MODEL    — model alias (default: haiku)
    CILOGBENCH_CLAUDE_TIMEOUT  — seconds (default: 240)

Safety invariants:
  - The wrapper (`run_llm_summary_baseline.py`) is responsible for stripping
    ground_truth / failure_category / required_signals / evidence_spans /
    expected_diagnosis from the safe metadata before this shim sees the
    payload. We re-verify defensively and fail loudly if any leak slips
    through.
  - We do NOT log raw model output to disk beyond what is written to stdout.
  - On any error we exit non-zero so the runner records a real
    provider_error rather than a fake "I don't know" summary.
"""

import json
import os
import re
import subprocess
import sys


FORBIDDEN_KEYS = (
    "ground_truth", "failure_category", "required_signals",
    "evidence_spans", "expected_diagnosis",
)


def verify_no_leakage(payload: dict) -> None:
    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kp = f"{path}.{k}" if path else k
                if any(bad in k for bad in FORBIDDEN_KEYS):
                    raise ValueError(f"forbidden key in payload at {kp}")
                walk(v, kp)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{path}[{i}]")
    walk(payload, "")


def get_messages(payload: dict) -> tuple[str, str]:
    system = ""
    user = ""
    for m in payload.get("messages") or []:
        role = m.get("role")
        if role == "system":
            system = m.get("content", "") or ""
        elif role == "user":
            user = m.get("content", "") or ""
    return system, user


# Match the diagnosis shim's single-call ceiling. The summarizer is invoked
# per-chunk so this caps an individual chunk, not the whole log.
MAX_USER_CHARS = 480_000


def invoke_claude(system_prompt: str, user_message: str,
                  model: str, timeout_s: int) -> dict:
    if len(user_message) > MAX_USER_CHARS:
        raise RuntimeError(
            f"summary chunk too large for shim cap "
            f"({len(user_message)} > {MAX_USER_CHARS} chars)"
        )
    argv = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        # --system-prompt (not --append-system-prompt) replaces Claude
        # Code's default agentic system prompt entirely, so the model
        # follows the map/reduce prompt instead of "I am Claude Code".
        "--system-prompt", system_prompt,
        user_message,
    ]
    res = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout_s,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {res.returncode}: {res.stderr[:400]!r}"
        )
    try:
        wrapper = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"claude CLI returned non-JSON envelope: {e}. "
            f"First 400 chars: {res.stdout[:400]!r}"
        ) from e
    if wrapper.get("is_error"):
        raise RuntimeError(
            f"claude CLI reported error: {wrapper.get('result', '')[:400]!r}"
        )
    return wrapper


def strip_fences(text: str) -> str:
    """Drop optional ```text / ```markdown fences if the model emits them."""
    t = (text or "").strip()
    m = re.match(r"```(?:markdown|md|text)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    return t


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    system_prompt, user_message = get_messages(payload)
    if not system_prompt:
        sys.stderr.write("summary_shim_claude_cli: missing system prompt\n")
        return 1
    if not user_message:
        # Empty input — return a minimal non-content response. The wrapper
        # already special-cases empty chunks, but be robust.
        json.dump({
            "content": "",
            "provider": "claude-cli-haiku",
            "model": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    model = os.environ.get("CILOGBENCH_CLAUDE_MODEL", "haiku")
    timeout_s = int(os.environ.get("CILOGBENCH_CLAUDE_TIMEOUT", "240"))

    try:
        wrapper = invoke_claude(system_prompt, user_message, model, timeout_s)
        content = strip_fences(wrapper.get("result", ""))
        # Pull the usage block emitted by the CLI envelope when available.
        # Anthropic's `usage.input_tokens` only counts the *non-cached* prompt
        # tokens; the rest live under `cache_creation_input_tokens` and
        # `cache_read_input_tokens`. Sum them so the per-row total reflects
        # total billed input tokens for the call.
        usage = wrapper.get("usage") or {}
        in_billed = int(
            (usage.get("input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
        )
        if in_billed == 0:
            in_billed = estimate_tokens(user_message)
        out_tok = int(usage.get("output_tokens") or estimate_tokens(content))
        total_cost = wrapper.get("total_cost_usd")
        response = {
            "content": content,
            "provider": "claude-cli",
            "model": model,
            "usage": {
                "input_tokens": in_billed,
                "output_tokens": out_tok,
            },
        }
        if total_cost is not None:
            response["usage"]["total_cost_usd"] = total_cost
        json.dump(response, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"summary_shim_claude_cli: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
