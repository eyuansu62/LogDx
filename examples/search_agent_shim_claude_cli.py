#!/usr/bin/env python3
"""
E7 search-agent shim backed by the `claude` CLI (Claude Code, print mode).

Speaks the M5-style command-provider contract used by `tools/run_search_agent.py`:

  stdin  = {
    "case_id": "...",
    "agent_name": "mcp-search-agent-v1-sonnet",
    "prompt": "<contents of prompts/search_agent_v1.md>",
    "safe_case_metadata": {...},
    "available_tools": [...],
    "conversation": [
      {"role": "tool", "name": "<tool>", "content": "<json-stringified obs>"},
      {"role": "assistant", "content": "<previous JSON action>"},
      ...
    ],
    "budget_remaining": {"tool_calls": int, "observation_tokens": int}
  }

  stdout = ONE strict JSON action object (either tool_call or final_diagnosis)

Usage:
    export SEARCH_AGENT_COMMAND="python3 $(pwd)/examples/search_agent_shim_claude_cli.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

Optional env overrides:
    CILOGBENCH_CLAUDE_MODEL    — model alias (default: sonnet)
    CILOGBENCH_CLAUDE_TIMEOUT  — seconds (default: 240)

Safety invariants:
  - Anti-leakage: refuses to forward a payload that contains any of
    {ground_truth, failure_category, required_signals, evidence_spans,
     expected_diagnosis} anywhere in the JSON tree.
  - Returns non-zero exit status on any failure (so the runner records a
    real `provider_error` instead of a synthetic "I don't know" answer).
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


MAX_USER_CHARS = 480_000


def build_user_message(payload: dict) -> str:
    """Build a flat textual representation of the conversation that the model
    can read. The system prompt is provided separately via --system-prompt;
    here we include only the user-facing context for *this step*."""
    case_id = payload.get("case_id", "?")
    safe_meta = payload.get("safe_case_metadata") or {}
    available = payload.get("available_tools") or []
    convo = payload.get("conversation") or []
    budget = payload.get("budget_remaining") or {}

    parts: list[str] = []
    parts.append(f"# CILogBench search-agent step")
    parts.append("")
    parts.append(f"You are diagnosing CI failure `{case_id}`.")
    parts.append("")
    parts.append("## Safe case metadata")
    parts.append("")
    parts.append("```json")
    parts.append(json.dumps(safe_meta, ensure_ascii=False, indent=2))
    parts.append("```")
    parts.append("")
    parts.append("## Available tools")
    parts.append("")
    parts.append("You may call ANY of these tools. Each takes JSON arguments and returns a JSON observation.")
    parts.append("")
    parts.append("```json")
    parts.append(json.dumps(available, ensure_ascii=False, indent=2))
    parts.append("```")
    parts.append("")
    parts.append("## Budget remaining")
    parts.append("")
    parts.append("```json")
    parts.append(json.dumps(budget, ensure_ascii=False, indent=2))
    parts.append("```")
    parts.append("")
    parts.append("## Conversation so far")
    parts.append("")
    if not convo:
        parts.append("_(this is the first step; no observations yet)_")
    else:
        for msg in convo:
            role = msg.get("role")
            if role == "tool":
                parts.append(f"### tool observation: `{msg.get('name')}`")
                parts.append("")
                parts.append("```json")
                parts.append(msg.get("content", "{}"))
                parts.append("```")
                parts.append("")
            elif role == "assistant":
                parts.append("### your previous action")
                parts.append("")
                parts.append("```json")
                parts.append(msg.get("content", "{}"))
                parts.append("```")
                parts.append("")
            elif role == "system_note":
                parts.append(f"### system note")
                parts.append("")
                parts.append(msg.get("content", ""))
                parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("Now produce your **next** strict-JSON action — either")
    parts.append("`{\"type\":\"tool_call\", ...}` or `{\"type\":\"final_diagnosis\", ...}`.")
    parts.append("Output ONLY the JSON, nothing else.")
    return "\n".join(parts)


def invoke_claude(system_prompt: str, user_message: str,
                   model: str, timeout_s: int) -> dict:
    if len(user_message) > MAX_USER_CHARS:
        raise RuntimeError(
            f"step too large for shim cap ({len(user_message)} > {MAX_USER_CHARS} chars)"
        )
    argv = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        "--system-prompt", system_prompt,
        user_message,
    ]
    res = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
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


def parse_action_json(text: str) -> dict:
    """Extract a strict JSON action object from whatever the model produced."""
    t = (text or "").strip()
    m = re.match(r"```(?:json)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object found in model reply: {t[:200]!r}")
    return json.loads(t[start:end + 1])


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    system_prompt = payload.get("prompt", "")
    if not system_prompt:
        sys.stderr.write("search_agent_shim_claude_cli: missing system prompt\n")
        return 1

    model = os.environ.get("CILOGBENCH_CLAUDE_MODEL", "sonnet")
    timeout_s = int(os.environ.get("CILOGBENCH_CLAUDE_TIMEOUT", "240"))

    try:
        user_message = build_user_message(payload)
        wrapper = invoke_claude(system_prompt, user_message, model, timeout_s)
        action = parse_action_json(wrapper.get("result", ""))
        usage = wrapper.get("usage") or {}
        in_billed = int(
            (usage.get("input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
        )
        if in_billed == 0:
            in_billed = max(1, len(user_message) // 4)
        out_tok = int(usage.get("output_tokens") or 0)
        if out_tok == 0:
            out_tok = max(1, len(json.dumps(action, ensure_ascii=False)) // 4)
        total_cost = wrapper.get("total_cost_usd")

        # Echo back the action plus shim-side accounting
        response = {
            "action": action,
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
        sys.stderr.write(f"search_agent_shim_claude_cli: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
