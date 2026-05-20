#!/usr/bin/env python3
"""
LLM-summary shim backed by OpenAI Chat Completions (gpt-5-mini default).

Mirrors the M4 command-provider contract used by
`tools/run_llm_summary_baseline.py`:

  stdin  = {"messages":[{role,content}], "temperature":...,
            "max_output_chars":..., "metadata":{case_id, prompt_version, stage}}
  stdout = {"content": "...", "provider": "openai", "model": "<resolved>",
            "usage": {"input_tokens":..., "output_tokens":...}}

This is the cross-family counterpart to `summary_shim_claude_cli.py` —
v1.2 introduces `llm-summary-v1-gpt-5-mini` as a non-Anthropic
summarizer so the headline LLM-summary class isn't anchored on a
single provider's family. See the v1.2 release notes for the
self-call-bias context.

Usage:
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
    export OPENAI_API_KEY=...
    export CILOGBENCH_OPENAI_SUMMARY_MODEL=gpt-5-mini   # default

    python tools/run_llm_summary_baseline.py \\
        --split v2/dev --method llm-summary-v1-gpt-5-mini \\
        --provider command \\
        --command "python3 examples/summary_shim_openai.py" \\
        --chunk-lines 500 --chunk-overlap-lines 25 --temperature 0.0

Optional env overrides:
    CILOGBENCH_OPENAI_SUMMARY_MODEL  — model id (default: gpt-5-mini)
    CILOGBENCH_OPENAI_TIMEOUT        — seconds (default: 240)
    CILOGBENCH_OPENAI_BASE_URL       — endpoint (default: https://api.openai.com/v1)

Safety invariants (same as the Claude summary shim):
  - Re-verify FORBIDDEN_KEYS in the payload defensively (ground_truth,
    failure_category, required_signals, evidence_spans,
    expected_diagnosis).
  - Never log raw model output to disk beyond the stdout return.
  - API key read from env only; never logged or written.
  - Exit non-zero on error so the runner records a real provider_error
    rather than a fake "I don't know" summary.
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


# Per-chunk cap. gpt-5-mini's context window is ~400k tokens ≈ 1.6M
# chars; we cap at 700k chars to match the Claude summary shim's
# limit. That keeps the two shims comparable on "did the chunk fit"
# and lets the 3 long-line cases (nodejs, pytest-sklearn ×2) re-chunk
# at chunk_lines=100 the same way the Claude shim does.
MAX_USER_CHARS = 700_000


# ---- HTTP secret-redaction helpers ----
# Lifted from examples/diagnosis_shim_openai.py — same Codex 2026-06-15
# F2 secret-leak guard. Error messages NEVER include raw response
# bodies, bearer tokens, or echoed URLs; replacements preserve a sha256
# prefix so auditors can tell two leaked tokens apart without seeing
# the raw value.
_BEARER_RE = re.compile(
    r"(?i)(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._\-]{20,}"
)
_APIKEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9._\-]{20,}")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9]{40,}\b")
_URL_LIKE_RE = re.compile(r"https?://[^\s'\"<>]+")


def _sha_tag(raw: str) -> str:
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"<redacted-secret sha={sha}…>"


def redact_secrets_in_text(text: str) -> str:
    if not text:
        return text
    text = _URL_LIKE_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _BEARER_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _APIKEY_LIKE_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    text = _LONG_TOKEN_RE.sub(lambda m: _sha_tag(m.group(0)), text)
    return text


def safe_http_error_summary(http_code: int, body: bytes | str) -> str:
    if isinstance(body, str):
        raw = body.encode("utf-8", "replace")
    else:
        raw = body
    body_sha = hashlib.sha256(raw).hexdigest()[:16]
    return f"OpenAI HTTP {http_code} body_sha256={body_sha}… body_len={len(raw)}"


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
        # gpt-5-mini is a reasoning model: uses max_completion_tokens,
        # ignores temperature/top_p. Cap is generous — summaries are
        # short markdown structs.
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
            raise RuntimeError(f"OpenAI request failed: {sanitized}") from e
    raise RuntimeError(f"OpenAI request failed after retries: {last_err}")


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
    if os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") != "1":
        sys.stderr.write(
            "summary_shim_openai: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 required "
            "to invoke the OpenAI API. Set it explicitly to opt in.\n"
        )
        return 1

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.stderr.write("summary_shim_openai: OPENAI_API_KEY env var not set\n")
        return 1

    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    system_prompt, user_message = get_messages(payload)
    if not system_prompt:
        sys.stderr.write("summary_shim_openai: missing system prompt\n")
        return 1

    model = os.environ.get("CILOGBENCH_OPENAI_SUMMARY_MODEL", "gpt-5-mini")
    timeout_s = int(os.environ.get("CILOGBENCH_OPENAI_TIMEOUT", "240"))
    base_url = os.environ.get(
        "CILOGBENCH_OPENAI_BASE_URL", "https://api.openai.com/v1"
    )

    if not user_message:
        json.dump({
            "content": "",
            "provider": "openai",
            "model": model,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if len(user_message) > MAX_USER_CHARS:
        sys.stderr.write(
            f"summary_shim_openai: summary chunk too large for shim cap "
            f"({len(user_message)} > {MAX_USER_CHARS} chars)\n"
        )
        return 1

    try:
        envelope = invoke_openai(
            system_prompt, user_message, model, timeout_s, api_key, base_url
        )
        choices = envelope.get("choices") or []
        if not choices:
            raise RuntimeError(
                f"OpenAI envelope missing choices "
                f"(sha={hashlib.sha256(json.dumps(envelope).encode()).hexdigest()[:16]}…)"
            )
        msg = choices[0].get("message") or {}
        content = strip_fences(msg.get("content") or "")
        usage = envelope.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or estimate_tokens(user_message))
        out_tok = int(usage.get("completion_tokens") or estimate_tokens(content))
        resolved_model = envelope.get("model") or model
        response = {
            "content": content,
            "provider": "openai",
            "model": resolved_model,
            "usage": {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
            },
        }
        json.dump(response, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        msg = redact_secrets_in_text(f"{type(e).__name__}: {e}")
        sys.stderr.write(f"summary_shim_openai: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
