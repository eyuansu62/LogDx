#!/usr/bin/env python3
"""
Diagnosis shim backed by OpenAI Chat Completions API.

Mirrors the M5 command-provider contract used by
`examples/diagnosis_shim_claude_cli.py`:
    stdin  = {"case_id","context_method","prompt","context",
              "safe_case_metadata","expected_output_schema"}
    stdout = {"summary","root_cause_category","root_cause","confidence",
              "relevant_files","relevant_tests","evidence","suggested_fix"}

This shim adds a NON-ANTHROPIC debugger so v2's "hybrid-v2 #1
generalizes" finding can be checked across model families (per §3i,
2026-05-11). Implementation uses stdlib urllib to avoid pulling in the
openai package; the project's other shims also use subprocess + stdlib.

Safety invariants enforced here (same as the Claude shim):
  - The stdin payload is assumed to already exclude ground_truth /
    failure_category / required_signals (guaranteed by run_diagnosis.py).
    This shim RE-VERIFIES that and errors out if it sees any of those keys.
  - The shim does NOT store the model's raw reply to disk beyond what it
    writes to stdout.
  - The API key is read from OPENAI_API_KEY env only — never logged,
    never written to any file.

Usage:
    export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_openai.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
    export OPENAI_API_KEY=...               # required
    export CILOGBENCH_OPENAI_MODEL=gpt-5-mini   # default

Optional env overrides:
    CILOGBENCH_OPENAI_TIMEOUT  — seconds (default: 180)
    CILOGBENCH_OPENAI_BASE_URL — for proxies / alt endpoints
                                 (default: https://api.openai.com/v1)
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

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
    """Recursively ensure no forbidden key is present anywhere in the payload."""
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


class _ContextTooLargeError(Exception):
    pass


def sanitize_base_url(url: str) -> str:
    """Strip userinfo and query string from a base_url for safe persistence.

    Per Codex 2026-05-12 [medium]: an env-provided proxy URL can contain
    userinfo (https://user:pass@host) or a signed-URL query token. The shim
    persists base_url into the diagnosis row's metadata.model_info; without
    sanitization those secrets land in committed result artifacts despite
    the v3 config declaring `allow_secret_values_in_results=false`. Strip
    userinfo and query before persisting; the full URL's sha256 is recorded
    separately so a reviewer can still tell a proxy run apart from the
    canonical run.
    """
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def base_url_sha256(url: str) -> str:
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


def build_user_message(payload: dict) -> str:
    ctx = payload.get("context", "")
    meta = payload.get("safe_case_metadata") or {}
    # gpt-5-mini context window is large but we cap at the same 480k chars
    # as the Claude shim for symmetry — keeps both shims comparable on the
    # "did the context fit" axis.
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


def invoke_openai(system_prompt: str, user_message: str, model: str,
                   timeout_s: int, api_key: str, base_url: str) -> dict:
    """POST /chat/completions and return the parsed envelope."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        # gpt-5-mini is a "reasoning" model: it accepts max_completion_tokens
        # instead of max_tokens and ignores temperature/top_p.
        "max_completion_tokens": 4096,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    # Simple retry on 5xx / connection failures (3 attempts, exp backoff).
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "replace")[:400]
            if 500 <= e.code < 600 and attempt < 2:
                last_err = f"HTTP {e.code}: {err_body!r}"
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenAI HTTP {e.code}: {err_body!r}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenAI request failed: {e}") from e
    raise RuntimeError(f"OpenAI request failed after retries: {last_err}")


def parse_diagnosis_json(text: str) -> dict:
    """Extract a diagnosis dict from the model's content string."""
    t = (text or "").strip()
    m = re.match(r"```(?:json)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
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
    model = os.environ.get("CILOGBENCH_OPENAI_MODEL", "gpt-5-mini")
    timeout_s = int(os.environ.get("CILOGBENCH_OPENAI_TIMEOUT", "180"))
    base_url = os.environ.get(
        "CILOGBENCH_OPENAI_BASE_URL", "https://api.openai.com/v1"
    )
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        sys.stderr.write(
            "diagnosis_shim_openai: OPENAI_API_KEY env var not set\n"
        )
        return 1

    # Per Codex 2026-05-13 F1 [high]: the runner enforces this gate via
    # `tools/run_diagnosis.py:check_external_llm_opt_in`, but mirror it
    # here so an off-runner invocation (smoke-tests, ad-hoc DIAGNOSIS_COMMAND
    # calls from another harness) still requires the explicit opt-in
    # before shipping CI log context to OpenAI.
    if (os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") or "").strip().lower() \
            not in {"1", "true", "yes", "on"}:
        sys.stderr.write(
            "diagnosis_shim_openai: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 required "
            "to send CI log context to OpenAI. Set it explicitly to opt in.\n"
        )
        return 1

    try:
        user_message = build_user_message(payload)
    except _ContextTooLargeError as e:
        # Per Codex 2026-05-11 [high]: exit non-zero so run_diagnosis
        # records this as a real provider_error in row metadata.
        # Previously this path returned 0 with `_provider_error` set,
        # but run_diagnosis drops underscored keys when normalizing
        # the shim output, so the row ended up looking like a valid
        # model abstention (confidence=0, unknown category).
        sys.stderr.write(
            f"diagnosis_shim_openai: unsupported_context_too_large: {e}\n"
        )
        return 1

    try:
        wrapper = invoke_openai(
            system_prompt, user_message, model, timeout_s, api_key, base_url
        )
        choices = wrapper.get("choices") or []
        if not choices:
            raise RuntimeError(
                f"OpenAI returned no choices: {json.dumps(wrapper)[:400]!r}"
            )
        content = (choices[0].get("message") or {}).get("content") or ""
        if not content:
            raise RuntimeError(
                f"OpenAI choice had empty content: "
                f"{json.dumps(choices[0])[:400]!r}"
            )
        diag_raw = parse_diagnosis_json(content)
        diag = normalize(diag_raw)
        # Per Codex 2026-05-11 [high] F2: persist model identity so the
        # benchmark artifact records which exact model produced the row.
        # The shim previously took both model and base_url from env and
        # neither was written to the diagnosis row — a run against
        # gpt-5-mini, a dated snapshot, or a proxy would produce
        # indistinguishable committed artifacts. The runner copies
        # `_model_info` (underscored: not part of the M5 contract; runner
        # treats as opt-in metadata) into row.metadata.model_info.
        # Also persist what OpenAI's response says (model field is the
        # snapshot ID the request actually hit; OpenAI may resolve an
        # alias to a dated snapshot).
        diag["_model_info"] = {
            "provider_name": "openai",
            "requested_model": model,
            "resolved_model": wrapper.get("model"),
            # Per Codex 2026-05-12 [medium]: persist a sanitized base_url
            # (no userinfo, no query) plus a sha256 of the full URL. The
            # hash lets an auditor distinguish a proxy/alt-endpoint run
            # from a canonical run without leaking the secret-carrying
            # parts of the URL.
            "base_url": sanitize_base_url(base_url),
            "base_url_sha256": base_url_sha256(base_url),
            "max_completion_tokens": 4096,
            "system_fingerprint": wrapper.get("system_fingerprint"),
            "usage": wrapper.get("usage"),
        }
        json.dump(diag, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        sys.stderr.write(f"diagnosis_shim_openai: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
