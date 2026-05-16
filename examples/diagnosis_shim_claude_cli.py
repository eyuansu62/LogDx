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

import hashlib
import json
import os
import re
import subprocess
import sys

# Per Codex 2026-06-17 F1 [high]: secret-shape redactors mirror the
# OpenAI shim's set. Applied to every error message that could land
# in `_provider_error` or stderr — defense-in-depth so a Claude CLI
# transient that prints credentials to its own stderr doesn't end
# up persisted in committed diagnosis artifacts.
_URL_LIKE_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]+")
_BEARER_RE = re.compile(r"(?i)(?:bearer|authorization\s*:)\s*[A-Za-z0-9._\-+/=]{8,}")
_APIKEY_LIKE_RE = re.compile(r"\b(?:sk|pk|rk|api[_-]?key)[-_][A-Za-z0-9]{16,}\b")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")


def redact_secrets_in_text(text: str) -> str:
    if not text:
        return text

    def _sha_tag(raw: str) -> str:
        return (
            "<redacted-secret sha="
            + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            + "…>"
        )

    def _url_repl(m):
        raw = m.group(0)
        return (
            "<redacted-url sha="
            + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            + "…>"
        )

    text = _URL_LIKE_RE.sub(_url_repl, text)
    text = _BEARER_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _APIKEY_LIKE_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _LONG_TOKEN_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    return text


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
        # Per Codex 2026-06-17 F1 [high]: redact secret-shape
        # substrings from `claude` CLI stderr before re-raising.
        # The runner lifts our exception text into
        # `metadata.provider_error_detail`; without redaction,
        # credentials echoed in CLI errors could leak through.
        stderr_redacted = redact_secrets_in_text(res.stderr or "")
        raise RuntimeError(
            f"claude CLI exited {res.returncode}: {stderr_redacted[:400]!r}"
        )
    try:
        wrapper = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        stdout_redacted = redact_secrets_in_text(res.stdout or "")
        raise RuntimeError(
            f"claude CLI returned non-JSON envelope: {e}. "
            f"First 400 chars: {stdout_redacted[:400]!r}"
        ) from e
    if wrapper.get("is_error"):
        result_redacted = redact_secrets_in_text(wrapper.get("result", ""))
        raise RuntimeError(
            f"claude CLI reported error: {result_redacted[:400]!r}"
        )
    return wrapper


def parse_diagnosis_json(text: str) -> dict:
    """Extract a diagnosis dict from whatever the model produced.

    Per Codex 2026-06-21 F2 [high]: when no JSON object is found,
    do NOT embed the raw reply (or a slice of it) in the exception
    message. The 2026-06-17 redactors only catch URL / bearer /
    API-key / long-token shapes, so prose / CI log text / tenant
    names / emails / short secrets survive into
    `metadata.provider_error`. Emit a hash + length summary instead.
    """
    t = text.strip()
    # Strip ```json ... ``` fences if present
    m = re.match(r"```(?:json)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    # First JSON object in the string
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end <= start:
        body_sha = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
        raise ValueError(
            f"no JSON object found in model reply: "
            f"reply_sha256={body_sha}… reply_len={len(t)}"
        )
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

    # Per Codex 2026-05-13 F1 [high]: defense-in-depth opt-in gate. The
    # v1 and v2 configs declare requires_explicit_external_llm_opt_in and
    # the runner enforces it; mirror here so an off-runner DIAGNOSIS_COMMAND
    # invocation still cannot ship CI log context to Anthropic without
    # the explicit opt-in.
    if (os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") or "").strip().lower() \
            not in {"1", "true", "yes", "on"}:
        sys.stderr.write(
            "diagnosis_shim_claude_cli: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 "
            "required to invoke an external LLM via the claude CLI. Set "
            "it explicitly to opt in.\n"
        )
        return 1

    system_prompt = payload.get("prompt", "")
    model = os.environ.get("CILOGBENCH_CLAUDE_MODEL", "haiku")
    timeout_s = int(os.environ.get("CILOGBENCH_CLAUDE_TIMEOUT", "180"))

    try:
        user_message = build_user_message(payload)
    except _ContextTooLargeError as e:
        # Per Codex 2026-05-11 [high] + 2026-05-19 F2 [medium]: exit 1
        # AND emit a structured _provider_error envelope so the runner
        # stores the taxonomy class as primary metadata.provider_error
        # (instead of the wrapper "ShimCallError: ..." string).
        envelope = {
            "_provider_error": f"unsupported_context_too_large: {e}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(
            f"diagnosis_shim_claude_cli: unsupported_context_too_large: {e}\n"
        )
        return 1

    # Two-phase try: (1) the CLI subprocess (network/auth). (2) post-CLI
    # parsing of the model's response. Phase 1 failures have no
    # model_info; phase 2 failures DO (we already got a wrapper back).
    try:
        wrapper = invoke_claude(system_prompt, user_message, model, timeout_s)
    except Exception as e:
        # Per Codex 2026-06-22 F2 [high]: invoke_claude raises
        # RuntimeError with `redacted[:400]!r` of CLI stderr / stdout
        # / `wrapper.get("result")` — those slices are token-shape-
        # redacted but prose / CI log text / tenant names / emails
        # / short secrets survive. Hash the entire exception text so
        # the persisted stderr (lifted into `metadata.provider_error_
        # detail` by the runner) carries NO model-controlled content.
        # Same pattern as the post-CLI parse/normalize handler below.
        raw_msg = f"{type(e).__name__}: {e}"
        msg_sha = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:16]
        msg = (
            f"{type(e).__name__} message_sha256={msg_sha}… "
            f"message_len={len(raw_msg)}"
        )
        sys.stderr.write(f"diagnosis_shim_claude_cli: {msg}\n")
        return 1

    # Per Codex 2026-05-14 F2 [high] + 2026-05-16 F1: build model_info
    # the moment invoke_claude returns. resolved_model is best-effort
    # (the claude CLI does not always include a dated snapshot in its
    # envelope), but recording even the alias + session_id beats null.
    model_info = {
        "provider_name": "anthropic",
        "requested_model": model,
        "resolved_model": wrapper.get("model"),
        "usage": wrapper.get("usage"),
        "session_id": wrapper.get("session_id"),
    }

    try:
        diag_raw = parse_diagnosis_json(wrapper.get("result", ""))
        diag = normalize(diag_raw)
        diag["_model_info"] = model_info
        json.dump(diag, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        # Post-CLI failure (e.g. parse_diagnosis_json choked on a model
        # response containing unescaped control chars). Per Codex
        # 2026-05-16 F1 [high]: write a JSON envelope carrying
        # model_info + the structured error string to stdout so the
        # runner can preserve provenance via
        # tools/run_diagnosis.py:_extract_shim_stdout_metadata.
        # Per Codex 2026-06-22 F2 [high]: post-CLI exceptions include
        # MODEL-CONTROLLED text. `normalize()` raises ValueError from
        # e.g. `float(diag_raw["confidence"])` when the model returns
        # a non-numeric string; the offending raw value lands in the
        # exception message. The 2026-06-17 token-shape redactor does
        # NOT catch prose / CI log text / tenant names / emails /
        # short secrets the model may echo. Replace the exception
        # body with a hash + length summary so `_provider_error`
        # carries NO model-controlled content. The exception CLASS
        # name stays (structural, non-sensitive) so operators can
        # tell apart "ValueError" (parse / normalize) from
        # "RuntimeError" (CLI errors).
        raw_msg = f"{type(e).__name__}: {e}"
        msg_sha = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:16]
        msg = (
            f"{type(e).__name__} message_sha256={msg_sha}… "
            f"message_len={len(raw_msg)}"
        )
        envelope = {
            "_model_info": model_info,
            "_provider_error": f"post_cli_error: {msg}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(f"diagnosis_shim_claude_cli: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
