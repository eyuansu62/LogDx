#!/usr/bin/env python3
"""
E1 diagnosis shim backed by the `claude` CLI (Claude Code, print mode).

Fulfills the M5 command-provider contract:
    stdin  = {"case_id","context_method","prompt","context",
              "safe_case_metadata","expected_output_schema"}
    stdout = {"summary","root_cause_category","root_cause","confidence",
              "relevant_files","relevant_tests","evidence","suggested_fix"}

Safety invariants enforced here:
  - The stdin payload is assumed to already exclude ground_truth /
    failure_category / required_signals (guaranteed by run_diagnosis.py).
    This shim RE-VERIFIES that and errors out if it sees any of those
    keys, so a future bug elsewhere cannot leak through.
  - The shim does NOT store the model's raw reply to disk beyond what
    it writes to stdout.

Usage:
    export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_claude_cli.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

Optional env overrides:
    CILOGBENCH_CLAUDE_MODEL    — model alias (default: haiku)
    CILOGBENCH_CLAUDE_TIMEOUT  — seconds (default: 180)
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

CATEGORY_ENUM = {
    "test_assertion", "compile_error", "type_error",
    "lint_failure", "formatting_failure",
    "dependency_install", "docker_build",
    "github_actions_config", "permission_or_secret",
    "network_or_flaky", "timeout_or_oom",
    "unknown", "other",
}


def verify_no_leakage(payload: dict) -> None:
    """Recursively ensure no forbidden key is present anywhere in the payload.
    This is a belt-and-suspenders check — the upstream runner already strips
    these, but we fail loudly rather than silently forwarding anything."""
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


def build_user_message(payload: dict) -> str:
    ctx = payload.get("context", "")
    meta = payload.get("safe_case_metadata") or {}
    # Cap the raw context passed to the model at ~500k chars (~125k tokens)
    # to stay safely within the 200k-token window. If truncation is needed,
    # the shim reports unsupported_context_too_large instead.
    MAX_CHARS = 480_000
    if len(ctx) > MAX_CHARS:
        raise _ContextTooLargeError(
            f"context ({len(ctx)} chars) exceeds shim cap ({MAX_CHARS})"
        )
    parts = [
        "You are diagnosing a failed CI job.",
        "",
        "## Safe case metadata",
        "",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "",
        "## Context",
        "",
        ctx,
        "",
        "Return STRICT JSON matching the schema in the system prompt. No prose, no code fences, no explanation — JSON only.",
    ]
    return "\n".join(parts)


class _ContextTooLargeError(Exception):
    pass


def invoke_claude(system_prompt: str, user_message: str,
                  model: str, timeout_s: int) -> dict:
    argv = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
        # --system-prompt (not --append-system-prompt) replaces Claude
        # Code's default agentic system prompt entirely, so the debugger
        # sees only debugger_v1 and nothing about being "Claude Code".
        # --bare would also do this but requires ANTHROPIC_API_KEY; the
        # interactive OAuth session is fine for running a protocol eval
        # from a developer machine.
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


def parse_diagnosis_json(text: str) -> dict:
    """Extract a diagnosis dict from whatever the model produced."""
    t = text.strip()
    # Strip ```json ... ``` fences if present
    m = re.match(r"```(?:json)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    # First JSON object in the string
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object found in model reply: {t[:200]!r}")
    return json.loads(t[start:end + 1])


def normalize(diag_raw: dict) -> dict:
    out = {
        "summary": str(diag_raw.get("summary", "")),
        "root_cause_category": diag_raw.get("root_cause_category", "unknown"),
        "root_cause": str(diag_raw.get("root_cause", "unknown")),
        "confidence": float(diag_raw.get("confidence", 0.0) or 0.0),
        "relevant_files": list(diag_raw.get("relevant_files", []) or []),
        "relevant_tests": list(diag_raw.get("relevant_tests", []) or []),
        "evidence": list(diag_raw.get("evidence", []) or []),
        "suggested_fix": str(diag_raw.get("suggested_fix", "")),
    }
    if out["root_cause_category"] not in CATEGORY_ENUM:
        out["root_cause_category"] = "other"
    out["confidence"] = max(0.0, min(1.0, out["confidence"]))
    # Evidence items must have quote+reason; drop malformed ones rather than
    # failing the whole diagnosis.
    fixed_ev = []
    for ev in out["evidence"]:
        if isinstance(ev, dict) and "quote" in ev and "reason" in ev:
            fixed_ev.append({"quote": str(ev["quote"]), "reason": str(ev["reason"])})
    out["evidence"] = fixed_ev
    return out


def unknown_body(summary: str) -> dict:
    return {
        "summary": summary,
        "root_cause_category": "unknown",
        "root_cause": "unknown",
        "confidence": 0.0,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "",
    }


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    system_prompt = payload.get("prompt", "")
    model = os.environ.get("CILOGBENCH_CLAUDE_MODEL", "haiku")
    timeout_s = int(os.environ.get("CILOGBENCH_CLAUDE_TIMEOUT", "180"))

    try:
        user_message = build_user_message(payload)
    except _ContextTooLargeError as e:
        # Per Codex 2026-05-11 [high]: exit non-zero so run_diagnosis
        # records this as a real provider_error. Previously returned 0
        # with `_provider_error` set, but run_diagnosis dropped the
        # underscored key, making it look like a valid model abstention.
        sys.stderr.write(
            f"diagnosis_shim_claude_cli: unsupported_context_too_large: {e}\n"
        )
        return 1

    try:
        wrapper = invoke_claude(system_prompt, user_message, model, timeout_s)
        diag_raw = parse_diagnosis_json(wrapper.get("result", ""))
        diag = normalize(diag_raw)
        json.dump(diag, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        # Hard fail: exit non-zero so run_diagnosis.py captures this as
        # provider_error in metadata instead of silently emitting an
        # unknown-with-fake-summary that pollutes the abstention metric.
        msg = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"diagnosis_shim_claude_cli: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
