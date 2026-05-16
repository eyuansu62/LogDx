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


_API_VERSION_SEGMENT_RE = re.compile(r"^v\d+$")


_PUBLIC_HOST_ALLOWLIST = frozenset({
    "api.openai.com", "api.anthropic.com",
    "localhost", "127.0.0.1", "::1",
})

# Per Codex 2026-06-20 F1 [high]: detect the already-redacted host
# placeholder so `sanitize_base_url` is idempotent. Without this,
# re-sanitizing a previously-redacted URL (e.g. during cache-hit
# validation against a row's persisted `metadata.model_info.base_url`)
# wraps the bracket-marker characters as a new "hostname" and
# produces a DIFFERENT sha-prefixed placeholder, then rejects the
# row as un-sanitized.
_REDACTED_HOST_NETLOC_RE = re.compile(
    r"^<redacted-host sha=[0-9a-fA-F]{8,}>$"
)


def _redact_hostname(host: str) -> str:
    """Per Codex 2026-06-19 F1 [high]: non-allowlisted hostnames may
    themselves carry tenant or resource identity (e.g.
    `my-resource.openai.azure.com`, internal proxy names with
    tenant prefixes). Replace the hostname with a stable
    sha-prefixed placeholder; auditors can still distinguish runs
    via the full-URL `base_url_sha256` recorded in model_info."""
    if not host:
        return host
    digest = hashlib.sha256(host.encode("utf-8")).hexdigest()[:16]
    return f"<redacted-host sha={digest}>"


def sanitize_base_url(url: str) -> str:
    """Strip userinfo, query, deep path segments, AND redact
    non-allowlisted hostnames for safe persistence.

    Codex history:
    - 2026-05-12 F3: stripped userinfo + query but kept the full path
    - 2026-05-25 F2 [medium]: kept only the FIRST path segment to drop
      deep `/v1/private/<token>` shapes
    - 2026-05-31 F1 [high]: the 2026-05-25 logic still preserved
      arbitrary first segments — proxies shaped like
      `https://proxy/<tenant-key>/v1` would persist the tenant key.
      Now: only first segments matching `^v\\d+$` (canonical API-
      version routes like /v1, /v2, /v10) are preserved.
    - 2026-06-19 F1 [high]: the path-segment sanitizer still preserved
      arbitrary HOSTNAMES — a private proxy like
      `https://my-tenant-resource.proxy.example.com/v1` persisted
      `my-tenant-resource.proxy.example.com` verbatim in
      `metadata.model_info.base_url`. Now: only hostnames in
      `_PUBLIC_HOST_ALLOWLIST` (api.openai.com, api.anthropic.com,
      localhost, 127.0.0.1, ::1) pass through; everything else is
      replaced with `<redacted-host sha=PREFIX>`. The full URL's
      sha256 is still recorded separately as `base_url_sha256`.

    Examples:
        https://user:pass@api.openai.com/v1?token=xyz
            -> https://api.openai.com/v1
        https://proxy.example.com/v1/private/secret-route
            -> https://<redacted-host sha=...>/v1
        https://my-resource.openai.azure.com/v1
            -> https://<redacted-host sha=...>/v1
        http://localhost:11434/v1
            -> http://localhost:11434/v1
        https://api.openai.com
            -> https://api.openai.com
    """
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if _REDACTED_HOST_NETLOC_RE.fullmatch(host):
        # Per Codex 2026-06-20 F1 [high]: the input has already been
        # redacted (e.g. we're re-sanitizing a row's persisted
        # `metadata.model_info.base_url` during cache-hit validation).
        # Pass through unchanged so the sanitizer is idempotent —
        # without this, the bracket / equals / hex chars would be
        # treated as a new "hostname" and re-redacted to a different
        # sha-prefixed placeholder, then rejected as unsanitized.
        netloc = host
    elif host.lower() in _PUBLIC_HOST_ALLOWLIST:
        netloc = host
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
    else:
        # Redact the host AND drop the port (custom-port info on a
        # private endpoint is also identity-leaking).
        netloc = _redact_hostname(host)
    path = parts.path or ""
    if path and path != "/":
        segments = [s for s in path.split("/") if s]
        if segments and _API_VERSION_SEGMENT_RE.fullmatch(segments[0]):
            # Allowlist hit: keep the canonical `/v<N>` segment.
            path = "/" + segments[0]
        else:
            # First segment isn't a known API-version route. Treat it
            # as potentially secret-bearing and drop the entire path.
            path = ""
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, "", ""))


def base_url_sha256(url: str) -> str:
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()


_URL_LIKE_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]+")

# Per Codex 2026-06-15 F2 [high]: secret-shape redactors applied
# alongside redact_urls_in_text whenever a provider-side text payload
# (HTTP response body, exception string) could land in
# metadata.provider_error. Without these, a compatible endpoint or
# proxy that echoes Authorization headers, API keys, or session
# tokens back in its 4xx error body would persist those secrets into
# committed diagnosis artifacts despite
# `allow_secret_values_in_results=false`.
_BEARER_RE = re.compile(r"(?i)(?:bearer|authorization\s*:)\s*[A-Za-z0-9._\-+/=]{8,}")
# OpenAI-style keys ("sk-..."), generic API-key prefixes, and long
# opaque tokens that look like credentials. We err on the side of
# over-redacting; legitimate prose mentioning short identifiers is
# fine, but anything that looks credential-shaped goes through the
# sha-prefixed placeholder.
_APIKEY_LIKE_RE = re.compile(r"\b(?:sk|pk|rk|api[_-]?key)[-_][A-Za-z0-9]{16,}\b")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")


def redact_urls_in_text(text: str) -> str:
    """Per Codex 2026-06-04 F2 [high]: replace any URL-like substring
    in a message with a redacted placeholder. urllib's exceptions
    (e.g. `ValueError: unknown url type: 'malformed-base-url-with-secret/v1'`)
    include the raw URL verbatim; if we let those flow into stderr,
    the runner promotes them into `metadata.provider_error`, leaking
    secret-bearing proxy URLs / typo'd base_urls into committed
    diagnosis artifacts despite `allow_secret_values_in_results=false`.

    Matches any `<scheme>://...` substring up to whitespace or a
    quote. The replacement carries a sha256 prefix so an auditor
    can still tell two malformed inputs apart without seeing the
    raw text.
    """
    if not text:
        return text
    def repl(m):
        raw = m.group(0)
        try:
            sanitized = sanitize_base_url(raw)
        except Exception:
            sanitized = "<unparseable>"
        return f"<redacted-url sanitized={sanitized!r} sha={base_url_sha256(raw)[:16]}…>"
    return _URL_LIKE_RE.sub(repl, text)


def redact_secrets_in_text(text: str) -> str:
    """Per Codex 2026-06-15 F2 [high]: scrub secret-shape substrings
    from a free-form error message before it lands in
    metadata.provider_error. Combines URL redaction
    (`redact_urls_in_text`) with bearer-token, API-key, and long-
    opaque-token patterns. Replacement preserves a sha256 prefix so
    auditors can tell two leaked tokens apart without seeing the
    raw value.
    """
    if not text:
        return text
    text = redact_urls_in_text(text)

    def _sha_tag(raw: str) -> str:
        return f"<redacted-secret sha={hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}…>"

    text = _BEARER_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _APIKEY_LIKE_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _LONG_TOKEN_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    return text


def safe_http_error_summary(http_code: int, body: bytes | str) -> str:
    """Per Codex 2026-06-15 F2 [high]: return a stable error summary
    that captures the HTTP status and a body digest WITHOUT echoing
    the raw response body. Compatible endpoints / proxies sometimes
    echo Authorization headers, tenant IDs, or session tokens back
    in 4xx error bodies; persisting the raw body into
    `metadata.provider_error` would commit those secrets.

    Format: `OpenAI HTTP {code} body_sha256={prefix} body_len={n}`.
    No body content; an auditor can reproduce the digest if needed."""
    if isinstance(body, str):
        raw = body.encode("utf-8", "replace")
    else:
        raw = body
    body_sha = hashlib.sha256(raw).hexdigest()[:16]
    return (
        f"OpenAI HTTP {http_code} body_sha256={body_sha}… "
        f"body_len={len(raw)}"
    )


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
    # Per Codex 2026-06-15 F2 [high]: error messages NEVER include the
    # raw response body — that body can contain echoed Authorization
    # headers, tenant identifiers, session tokens, or prompt
    # fragments from a compatible proxy/endpoint. Use
    # `safe_http_error_summary` to record status + body digest only,
    # and `redact_secrets_in_text` on any exception text before
    # re-raising so the runner persists a sanitized form.
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            summary = safe_http_error_summary(e.code, err_body)
            if 500 <= e.code < 600 and attempt < 2:
                last_err = summary
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(summary) from e
        except (urllib.error.URLError, TimeoutError) as e:
            sanitized = redact_secrets_in_text(f"{type(e).__name__}: {e}")
            if attempt < 2:
                last_err = sanitized
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"OpenAI request failed: {sanitized}"
            ) from e
    raise RuntimeError(f"OpenAI request failed after retries: {last_err}")


def parse_diagnosis_json(text: str) -> dict:
    """Extract a diagnosis dict from the model's content string.

    Per Codex 2026-06-21 F1 [high]: when no JSON object is found, do
    NOT embed the raw reply (or a slice of it) in the exception
    message. Even after the URL / bearer / API-key / long-token
    redactors, non-token-shape sensitive content (echoed CI log
    text, tenant names, prose) survives. Emit a hash + length
    summary instead — an auditor can still distinguish two
    malformed replies via the sha prefix without seeing their
    content.
    """
    t = (text or "").strip()
    m = re.match(r"```(?:json)?\s*(.+?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
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

    # Per Codex 2026-06-04 F2 [high]: validate base_url shape UPFRONT.
    # If the env value isn't a parseable http(s) URL, fail closed
    # WITHOUT echoing the malformed (potentially secret-bearing)
    # string into stderr — urllib's own ValueError includes the raw
    # URL, which the runner would then promote into
    # metadata.provider_error.
    base_url_parts = urllib.parse.urlsplit(base_url)
    if base_url_parts.scheme not in ("http", "https"):
        envelope = {
            "_provider_error": (
                f"invalid_base_url_scheme: scheme="
                f"{base_url_parts.scheme!r} "
                f"(base_url_sha256={base_url_sha256(base_url)[:16]}…)"
            ),
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(
            f"diagnosis_shim_openai: invalid_base_url_scheme "
            f"(sha={base_url_sha256(base_url)[:16]}…)\n"
        )
        return 1

    try:
        user_message = build_user_message(payload)
    except _ContextTooLargeError as e:
        # Per Codex 2026-05-11 [high]: exit non-zero so run_diagnosis
        # records this as a real provider_error in row metadata.
        # Per Codex 2026-05-19 F2 [medium]: also write a JSON envelope
        # to stdout containing the STRUCTURED taxonomy class so the
        # runner stores `metadata.provider_error =
        # "unsupported_context_too_large: ..."` instead of the
        # subprocess wrapper string (which would prefix
        # "ShimCallError: diagnosis command exited 1: ..." and break
        # downstream by-prefix counting that the model card relies on).
        # No `_model_info` envelope on this path because no API call
        # was made — the row legitimately has model_info: null.
        envelope = {
            "_provider_error": f"unsupported_context_too_large: {e}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(
            f"diagnosis_shim_openai: unsupported_context_too_large: {e}\n"
        )
        return 1

    # Two-phase try: (1) make the API call; if it fails outright, exit 1
    # with no model_info available. (2) Build model_info from the API
    # response IMMEDIATELY, then attempt to parse content; if parsing
    # fails, write a JSON envelope containing model_info to stdout and
    # exit 1 so the runner preserves provenance for the failed-but-
    # attempted call (Codex 2026-05-16 F1).
    try:
        wrapper = invoke_openai(
            system_prompt, user_message, model, timeout_s, api_key, base_url
        )
    except Exception as e:
        # The API call never succeeded — no model_info is available.
        # Per Codex 2026-06-04 F2 [high]: urllib's exceptions
        # include the raw URL (e.g.
        # `ValueError: unknown url type: 'malformed-secret/v1'`).
        # The runner promotes our stderr into metadata.provider_error,
        # so any URL-bearing exception text would leak the secret-
        # carrying value into committed artifacts. Scrub all URL-like
        # substrings before persisting AND before logging.
        # Per Codex 2026-06-16 F1 [high]: also redact bearer / API-key
        # / long-opaque-token shapes here; api_call_failed exceptions
        # from urlopen can still carry credential-shaped substrings.
        msg = redact_secrets_in_text(f"{type(e).__name__}: {e}")
        envelope = {
            "_provider_error": f"api_call_failed: {msg}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(f"diagnosis_shim_openai: {msg}\n")
        return 1

    # Per Codex 2026-05-11 [high] F2 + 2026-05-16 F1: build model_info
    # the moment the API call returns. Used both for the success row
    # AND, if parsing fails below, the partial provider_error envelope.
    model_info = {
        "provider_name": "openai",
        "requested_model": model,
        "resolved_model": wrapper.get("model"),
        # Per Codex 2026-05-12 [medium]: sanitized base_url (no userinfo,
        # no query) plus sha256 of the full URL for audit comparison.
        "base_url": sanitize_base_url(base_url),
        "base_url_sha256": base_url_sha256(base_url),
        "max_completion_tokens": 4096,
        "system_fingerprint": wrapper.get("system_fingerprint"),
        "usage": wrapper.get("usage"),
    }

    try:
        choices = wrapper.get("choices") or []
        if not choices:
            # Per Codex 2026-06-20 F2 [high]: NEVER echo
            # `json.dumps(wrapper)[:400]` in the error message. A
            # compatible 200 response can carry prompt fragments,
            # tenant IDs, CI log text, or non-token-shape sensitive
            # strings that pass the bearer/api-key/long-token
            # redactor. Emit a hash + length summary instead so an
            # auditor can still distinguish two malformed wrappers
            # without seeing the raw body.
            wrapper_json = json.dumps(wrapper, ensure_ascii=False)
            wrapper_sha = hashlib.sha256(
                wrapper_json.encode("utf-8")
            ).hexdigest()[:16]
            raise RuntimeError(
                f"OpenAI returned no choices: "
                f"wrapper_sha256={wrapper_sha}… "
                f"wrapper_len={len(wrapper_json)} "
                f"keys={sorted(wrapper.keys())}"
            )
        content = (choices[0].get("message") or {}).get("content") or ""
        if not content:
            # Per Codex 2026-06-20 F2 [high]: same hash-only summary
            # for empty-content errors. The choice payload may carry
            # echoed prompt content or proxy-injected fields.
            choice_json = json.dumps(choices[0], ensure_ascii=False)
            choice_sha = hashlib.sha256(
                choice_json.encode("utf-8")
            ).hexdigest()[:16]
            raise RuntimeError(
                f"OpenAI choice had empty content: "
                f"choice_sha256={choice_sha}… "
                f"choice_len={len(choice_json)} "
                f"keys={sorted(choices[0].keys()) if isinstance(choices[0], dict) else 'not-a-dict'}"
            )
        diag_raw = parse_diagnosis_json(content)
        diag = normalize(diag_raw)
        diag["_model_info"] = model_info
        json.dump(diag, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        # The API call SUCCEEDED but post-processing (parse/empty-choices)
        # failed. Per Codex 2026-05-16 F1 [high]: write a JSON envelope
        # to stdout that carries model_info + a structured error string
        # so the runner can lift model_info into the provider_error row
        # via tools/run_diagnosis.py:_extract_shim_stdout_metadata.
        # Per Codex 2026-06-04 F2 [high]: scrub URL-like substrings
        # from the exception text before persisting / logging.
        # Per Codex 2026-06-16 F1 [high]: scrub BEARER / API-key /
        # long-opaque-token shapes too. The post-API path can carry
        # `json.dumps(wrapper)` (the full response body) when a
        # compatible endpoint returns an OK status with no choices /
        # empty content — without this, a malformed 200 response
        # that echoes Authorization headers would leak into
        # `metadata.provider_error` despite the 2026-06-15 F2 fix
        # which only covered the HTTP-error path.
        msg = redact_secrets_in_text(f"{type(e).__name__}: {e}")
        envelope = {
            "_model_info": model_info,
            "_provider_error": f"post_api_error: {msg}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(f"diagnosis_shim_openai: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
