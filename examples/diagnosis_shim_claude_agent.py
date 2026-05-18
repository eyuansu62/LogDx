#!/usr/bin/env python3
"""
Diagnosis shim backed by the Anthropic Messages API in **agent-loop**
mode (multi-turn tool use over the case's raw.log).

This is the agent-loop variant of `diagnosis_shim_claude_cli.py`. The
single-shot CLI shim hands the model a pre-reduced `context` string;
this shim instead exposes four deterministic tools on top of the raw
log and lets the model decide what to read, in what order, across
multiple turns.

The 4 tools are:
  - `grep`     : case-insensitive regex search w/ before/after context
  - `read_file`: read explicit line range from raw.log
  - `tail`     : last N lines of raw.log
  - `view_log_lines`: read a window centered on a given line number

All tool outputs are formatted as `LINENO: line content` so the agent
can reference exact line numbers when emitting evidence quotes.

Implementation uses stdlib `urllib.request` (no `anthropic` SDK
required); same pattern as `diagnosis_shim_openai.py`. Requires
`ANTHROPIC_API_KEY` env var — unlike the single-shot CLI shim, this
shim talks DIRECTLY to api.anthropic.com so it cannot ride a
developer's OAuth session.

Fulfills the M5 command-provider contract:
    stdin  = {"case_id","context_method","prompt","context",
              "safe_case_metadata","expected_output_schema",
              "raw_log_path"}                # NEW: agent variant needs this
    stdout = {"summary","root_cause_category","root_cause","confidence",
              "relevant_files","relevant_tests","evidence","suggested_fix",
              "_model_info","_agent_metadata"}

Safety invariants enforced here:
  - The stdin payload is assumed to already exclude ground_truth /
    failure_category / required_signals (guaranteed by run_diagnosis.py).
    This shim RE-VERIFIES that and errors out if it sees any of those
    keys, so a future bug elsewhere cannot leak through.
  - The shim does NOT store the model's raw replies to disk beyond
    what it writes to stdout.
  - The API key is read from ANTHROPIC_API_KEY env only — never logged,
    never written to any file.
  - Exception messages that could embed model-controlled content are
    hashed (sha256 prefix + length) before being persisted into
    `metadata.provider_error`. The token-shape redactors from the
    single-shot shim are reused for stderr / response-body summaries.

Usage:
    export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_claude_agent.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
    export ANTHROPIC_API_KEY=...                    # required
    export CILOGBENCH_CLAUDE_MODEL=claude-haiku-4-5  # default

Optional env overrides:
    CILOGBENCH_CLAUDE_TIMEOUT                     — seconds (default: 180)
    CILOGBENCH_AGENT_V1_MAX_ITERATIONS            — default 5
    CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS    — default 180000
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Redaction helpers (mirror the single-shot CLI shim, lines 36–69)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Leakage / schema constants (mirror the single-shot CLI shim)
# ---------------------------------------------------------------------------

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
    """Recursively ensure no forbidden key is present anywhere in the
    payload. Belt-and-suspenders check — the upstream runner already
    strips these, but we fail loudly rather than silently forwarding
    anything."""
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


# ---------------------------------------------------------------------------
# Output schema helpers (parse / normalize / unknown_body — mirror the
# single-shot CLI shim)
# ---------------------------------------------------------------------------


def parse_diagnosis_json(text: str) -> dict:
    """Extract a diagnosis dict from whatever the model produced.
    Hash-only error reporting (no embedded reply text) to keep
    model-controlled content out of `metadata.provider_error`.
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
            fixed_ev.append(
                {"quote": str(ev["quote"]), "reason": str(ev["reason"])}
            )
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


class _ContextTooLargeError(Exception):
    pass


# ---------------------------------------------------------------------------
# Token estimator — same heuristic as tools/run_diagnosis.py:208
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    import math
    return math.ceil(len(text or "") / 4)


# ---------------------------------------------------------------------------
# Raw-log access helpers and tools
#
# The four tools (grep / read_file / tail / view_log_lines) all operate
# on the case's raw.log path. We cache the line list per process so
# repeated tool calls don't re-read disk; the cache key is the absolute
# path string, which is constant for a single invocation.
# ---------------------------------------------------------------------------

# Cap individual tool observations at ~32k chars (~8k tokens).
_OBSERVATION_MAX_CHARS = 32_000

# Default regex for `grep` (same as tools/run_baseline.py:35).
_DEFAULT_GREP_REGEX = (
    r"error|failed|failure|traceback|exception|assert|panic|exit code|##\[error\]"
)

# Read-file / view-log-lines caps.
_MAX_READ_FILE_LINES = 1000
_MAX_VIEW_LOG_RADIUS = 200
_MAX_VIEW_LOG_SPAN = 401          # 2*200 + 1
_MAX_TAIL_LINES = 1000

# Per-process raw-log line cache. Populated lazily on first tool call.
_RAW_LOG_LINES_CACHE: dict[str, list[str]] = {}


def _load_raw_log_lines(raw_log_path: str) -> list[str]:
    """Read and cache the raw.log file as a list of lines (no trailing \n)."""
    cached = _RAW_LOG_LINES_CACHE.get(raw_log_path)
    if cached is not None:
        return cached
    with open(raw_log_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    lines = text.splitlines()
    _RAW_LOG_LINES_CACHE[raw_log_path] = lines
    return lines


def _format_lines_with_numbers(
    lines: list[str], start_lineno: int
) -> str:
    """Format a slice of lines as `LINENO: content`, 1-indexed."""
    return "\n".join(
        f"{start_lineno + i}: {line}" for i, line in enumerate(lines)
    )


def _truncate_observation(text: str) -> str:
    """Cap an observation at ~8k tokens (32k chars). On truncation we
    keep the LEAD so the agent can still see line numbers near the
    start of matches."""
    if len(text) <= _OBSERVATION_MAX_CHARS:
        return text
    head = text[: _OBSERVATION_MAX_CHARS - 200]
    tail = (
        f"\n…[truncated; observation exceeded "
        f"{_OBSERVATION_MAX_CHARS} chars; "
        f"call grep / view_log_lines with narrower args]"
    )
    return head + tail


# ---- merge_ranges / ranges_to_lines (mirror tools/run_baseline.py:60-79) ----


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    """Merge overlapping or adjacent 1-indexed inclusive [start,end] ranges."""
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: list[list[int]] = [[ranges[0][0], ranges[0][1]]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _ranges_to_lines(ranges: list[list[int]]) -> list[int]:
    """Flatten merged ranges back into a sorted unique list of line numbers."""
    out: list[int] = []
    for s, e in ranges:
        out.extend(range(s, e + 1))
    return out


# ---- The four tool implementations ----


def tool_grep(args: dict, raw_log_path: str) -> str:
    """Case-insensitive regex search; returns matching lines + context.

    Mirrors `baseline_grep` from tools/run_baseline.py:120-146.
    """
    pattern = args.get("pattern")
    if not pattern:
        # Mirror the static-baseline default — useful when the model
        # asks for "any failure signal" without specifying a pattern.
        pattern = _DEFAULT_GREP_REGEX
    before = int(args.get("before", 3))
    after = int(args.get("after", 8))
    max_matches = int(args.get("max_matches", 50))
    # Sanity clamps.
    before = max(0, min(before, 50))
    after = max(0, min(after, 200))
    max_matches = max(1, min(max_matches, 500))

    try:
        pat = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"ERROR: invalid regex pattern: {e}"

    lines = _load_raw_log_lines(raw_log_path)
    n = len(lines)
    raw_ranges: list[tuple[int, int]] = []
    match_count = 0
    for i, line in enumerate(lines, start=1):
        if pat.search(line):
            start = max(1, i - before)
            end = min(n, i + after)
            raw_ranges.append((start, end))
            match_count += 1
            if match_count >= max_matches:
                break

    if not raw_ranges:
        return (
            f"No matches found for pattern {pattern!r} "
            f"(searched {n} lines)."
        )

    merged = _merge_ranges(raw_ranges)
    # Render each merged range as a block separated by a marker — keeps
    # the model from concluding non-adjacent lines are contiguous.
    blocks: list[str] = []
    for s, e in merged:
        block = _format_lines_with_numbers(lines[s - 1:e], s)
        blocks.append(block)

    header = (
        f"grep pattern={pattern!r} before={before} after={after} "
        f"matches={match_count} "
        f"(showing {len(merged)} merged range(s))\n"
    )
    body = "\n---\n".join(blocks)
    return _truncate_observation(header + body)


def tool_read_file(args: dict, raw_log_path: str) -> str:
    """Return lines [start_line, end_line] inclusive from raw.log."""
    try:
        start_line = int(args["start_line"])
        end_line = int(args["end_line"])
    except (KeyError, TypeError, ValueError) as e:
        return f"ERROR: read_file requires integer start_line and end_line: {e}"

    if start_line < 1:
        start_line = 1
    if end_line < start_line:
        return (
            f"ERROR: end_line ({end_line}) must be >= start_line ({start_line})"
        )

    span = end_line - start_line + 1
    if span > _MAX_READ_FILE_LINES:
        return (
            f"ERROR: requested span {span} exceeds max "
            f"{_MAX_READ_FILE_LINES} lines; narrow the range "
            f"or use grep / view_log_lines."
        )

    lines = _load_raw_log_lines(raw_log_path)
    n = len(lines)
    if start_line > n:
        return (
            f"read_file start_line={start_line} is past end of file "
            f"(total lines: {n})."
        )
    end_line = min(end_line, n)
    sliced = lines[start_line - 1:end_line]
    header = (
        f"read_file [{start_line}, {end_line}] (total file lines: {n})\n"
    )
    body = _format_lines_with_numbers(sliced, start_line)
    return _truncate_observation(header + body)


def tool_tail(args: dict, raw_log_path: str) -> str:
    """Return last N lines of raw.log (N ≤ _MAX_TAIL_LINES)."""
    n_arg = int(args.get("n", 200))
    n_arg = max(1, min(n_arg, _MAX_TAIL_LINES))
    lines = _load_raw_log_lines(raw_log_path)
    total = len(lines)
    if total == 0:
        return "tail: file is empty (0 lines)"
    take = min(n_arg, total)
    start = total - take + 1
    sliced = lines[start - 1:]
    header = f"tail n={n_arg} (showing lines {start}-{total} of {total})\n"
    body = _format_lines_with_numbers(sliced, start)
    return _truncate_observation(header + body)


def tool_view_log_lines(args: dict, raw_log_path: str) -> str:
    """Return lines [center-radius, center+radius] from raw.log."""
    try:
        center = int(args["center_line"])
    except (KeyError, TypeError, ValueError) as e:
        return f"ERROR: view_log_lines requires integer center_line: {e}"
    radius = int(args.get("radius", 30))
    radius = max(0, min(radius, _MAX_VIEW_LOG_RADIUS))
    lines = _load_raw_log_lines(raw_log_path)
    n = len(lines)
    if n == 0:
        return "view_log_lines: file is empty (0 lines)"
    start = max(1, center - radius)
    end = min(n, center + radius)
    span = end - start + 1
    if span > _MAX_VIEW_LOG_SPAN:
        # Belt-and-suspenders — the radius clamp above already enforces
        # this, but if a future change relaxes the clamp this guard
        # ensures the observation never explodes.
        end = start + _MAX_VIEW_LOG_SPAN - 1
        end = min(end, n)
    sliced = lines[start - 1:end]
    header = (
        f"view_log_lines center={center} radius={radius} "
        f"(showing lines {start}-{end} of {n})\n"
    )
    body = _format_lines_with_numbers(sliced, start)
    return _truncate_observation(header + body)


# ---- Tool dispatch + specs ----


def dispatch_tool(name: str, args: dict, raw_log_path: str) -> str:
    if name == "grep":
        return tool_grep(args, raw_log_path)
    if name == "read_file":
        return tool_read_file(args, raw_log_path)
    if name == "tail":
        return tool_tail(args, raw_log_path)
    if name == "view_log_lines":
        return tool_view_log_lines(args, raw_log_path)
    return f"ERROR: unknown tool {name!r}. Available: grep, read_file, tail, view_log_lines"


def tool_specs() -> list[dict]:
    """Anthropic tool-use specs for the four log-inspection tools."""
    return [
        {
            "name": "grep",
            "description": (
                "Case-insensitive regex search over the raw CI log. "
                "Returns matching lines together with `before` lines "
                "of context preceding each match and `after` lines "
                "following. Output is formatted as `LINENO: content`. "
                "Use this first to localize errors. If `pattern` is "
                "omitted, a default failure-signal regex is used "
                "(error|failed|failure|traceback|exception|assert|"
                "panic|exit code|##[error])."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python re-flavored regex.",
                    },
                    "before": {
                        "type": "integer",
                        "default": 3,
                        "description": "Lines of context before each match.",
                    },
                    "after": {
                        "type": "integer",
                        "default": 8,
                        "description": "Lines of context after each match.",
                    },
                    "max_matches": {
                        "type": "integer",
                        "default": 50,
                        "description": "Stop after this many matches.",
                    },
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "read_file",
            "description": (
                "Return lines [start_line, end_line] inclusive from "
                "the raw CI log. Use after grep / view_log_lines have "
                "localized an interesting region. Span must be "
                "<= 1000 lines."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "start_line": {
                        "type": "integer",
                        "description": "1-indexed start line, inclusive.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "1-indexed end line, inclusive.",
                    },
                },
                "required": ["start_line", "end_line"],
            },
        },
        {
            "name": "tail",
            "description": (
                "Return the last `n` lines of the raw CI log. Useful "
                "for getting at exit-code / final-error lines without "
                "knowing the file length. Max n = 1000."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "default": 200,
                        "description": "Number of trailing lines to return.",
                    },
                },
            },
        },
        {
            "name": "view_log_lines",
            "description": (
                "Return a window of lines centered on `center_line` "
                "(±`radius`). Use to expand context around a specific "
                "line discovered via grep. Radius capped at 200 "
                "(max 401-line window)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "center_line": {
                        "type": "integer",
                        "description": "1-indexed line to center the window on.",
                    },
                    "radius": {
                        "type": "integer",
                        "default": 30,
                        "description": "Lines above and below center_line.",
                    },
                },
                "required": ["center_line"],
            },
        },
    ]


# ---------------------------------------------------------------------------
# HTTP transport — direct urllib POST to api.anthropic.com/v1/messages
# (no `anthropic` SDK; mirror the OpenAI shim's retry pattern)
# ---------------------------------------------------------------------------


def _safe_http_error_summary(http_code: int, body: bytes | str) -> str:
    """Return a stable HTTP-error summary WITHOUT echoing the raw body
    — Anthropic 4xx/5xx responses can carry echoed prompt fragments
    or tenant identifiers, and persisting those into
    `metadata.provider_error` would commit them to disk."""
    if isinstance(body, str):
        raw = body.encode("utf-8", "replace")
    else:
        raw = body
    body_sha = hashlib.sha256(raw).hexdigest()[:16]
    return (
        f"Anthropic HTTP {http_code} body_sha256={body_sha}… "
        f"body_len={len(raw)}"
    )


def anthropic_post(
    messages: list[dict],
    system_prompt: str,
    max_output_tokens: int,
    tools: list[dict],
    model: str,
    timeout_s: int,
    api_key: str,
) -> dict:
    """POST /v1/messages and return the parsed envelope.

    3-attempt exponential backoff on 5xx and network errors, mirroring
    the OpenAI shim's invoke_openai retry block.
    """
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": model,
        "max_tokens": max_output_tokens,
        "temperature": 0,
        "system": system_prompt,
        "tools": tools,
        "messages": messages,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
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
            summary = _safe_http_error_summary(e.code, err_body)
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
                f"Anthropic request failed: {sanitized}"
            ) from e
    raise RuntimeError(f"Anthropic request failed after retries: {last_err}")


# ---------------------------------------------------------------------------
# Agent loop driver
# ---------------------------------------------------------------------------


def build_initial_user_message(payload: dict) -> str:
    """Initial user-turn content. Includes safe metadata + a *reduced*
    context block. The agent is expected to call `grep` / `tail` /
    etc. to read the raw log directly; the reduced context here is a
    convenience hint, NOT the whole log."""
    meta = payload.get("safe_case_metadata") or {}
    ctx = payload.get("context", "") or ""

    # Keep the seed context tight so token budget goes to tool turns.
    # The agent has tools to fetch more — no reason to spend 80k tokens
    # on a baseline-grep dump up front.
    SEED_MAX_CHARS = 24_000
    if len(ctx) > SEED_MAX_CHARS:
        ctx = (
            ctx[:SEED_MAX_CHARS]
            + f"\n…[seed context truncated at {SEED_MAX_CHARS} chars; "
            f"use grep / read_file / tail / view_log_lines to read more]"
        )

    parts = [
        "You are diagnosing a failed CI job.",
        "",
        "You have four tools to inspect the raw CI log: `grep`, "
        "`read_file`, `tail`, and `view_log_lines`. Use them to find "
        "the actual root-cause lines before answering. Then emit the "
        "STRICT JSON answer matching the schema in the system prompt — "
        "no prose, no code fences, JSON only.",
        "",
        "## Safe case metadata",
        "",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "",
        "## Seed context (a small, possibly truncated, slice of the log)",
        "",
        ctx,
        "",
        "Begin by calling one or more tools. When you have enough "
        "evidence, emit ONLY the final JSON object in a single text "
        "content block.",
    ]
    return "\n".join(parts)


def run_agent_loop(
    payload: dict,
    system_prompt: str,
    raw_log_path: str,
    model: str,
    timeout_s: int,
    api_key: str,
) -> tuple[dict | None, dict, dict | None]:
    """Drive the multi-turn tool-use loop.

    Returns:
        (final_diag_or_None, agent_metadata_dict, model_info_or_None)

    `final_diag_or_None` is the parsed-and-normalized diagnosis JSON,
    or None if the loop never produced one (in which case the caller
    falls back to unknown_body and `agent_metadata.budget_exhausted`
    is True).
    """
    agent_config = {
        "max_iterations": int(
            os.environ.get("CILOGBENCH_AGENT_V1_MAX_ITERATIONS", "5")
        ),
        "max_total_input_tokens": int(
            os.environ.get(
                "CILOGBENCH_AGENT_V1_MAX_TOTAL_INPUT_TOKENS", "180000"
            )
        ),
        "max_output_tokens_per_turn": 1500,
        "tool_observation_max_tokens": 8000,
    }

    specs = tool_specs()
    messages: list[dict] = [
        {"role": "user", "content": build_initial_user_message(payload)},
    ]
    total_input = 0
    total_output = 0
    tool_calls: list[dict] = []
    final: dict | None = None
    final_turn: int | None = None
    budget_exhausted = False
    last_response: dict | None = None
    turn = 0

    for turn in range(1, agent_config["max_iterations"] + 1):
        # HARD BUDGET STOP. Per Codex 2026-05-18 [high]: before
        # consuming another tool-using turn, check that we are still
        # under the cumulative input cap. If we have already exceeded
        # it (typically because the previous turn's tool observations
        # pushed us over), stop calling the model with tools enabled.
        # The post-loop forced-final block below will make ONE last
        # call with tools=[] disabled so the agent must emit JSON. The
        # cap is therefore a hard ceiling on **tool-using** turns; the
        # final no-tools cleanup call may add a small overhead beyond
        # that. Without this check the loop would happily keep paying
        # for tool-using turns until max_iterations even though
        # budget_exhausted was already set true.
        if total_input >= agent_config["max_total_input_tokens"]:
            budget_exhausted = True
            break

        resp = anthropic_post(
            messages,
            system_prompt,
            agent_config["max_output_tokens_per_turn"],
            specs,
            model,
            timeout_s,
            api_key,
        )
        last_response = resp
        usage = resp.get("usage") or {}
        total_input += int(usage.get("input_tokens") or 0)
        total_output += int(usage.get("output_tokens") or 0)

        stop_reason = resp.get("stop_reason")
        content = resp.get("content") or []

        if stop_reason == "tool_use":
            tu_blocks = [b for b in content if b.get("type") == "tool_use"]
            if not tu_blocks:
                # Malformed response — treat as final attempt.
                text = " ".join(
                    b.get("text", "")
                    for b in content
                    if b.get("type") == "text"
                )
                try:
                    final = normalize(parse_diagnosis_json(text))
                    final_turn = turn
                    break
                except Exception:
                    final = unknown_body(
                        "agent produced text without tool_use and "
                        "without final JSON"
                    )
                    final_turn = turn
                    budget_exhausted = True
                    break

            # Execute each tool call sequentially.
            tool_results: list[dict] = []
            for tu in tu_blocks:
                tool_name = tu.get("name") or "<unknown>"
                args = tu.get("input") or {}
                t0 = time.monotonic()
                try:
                    observation_text = dispatch_tool(
                        tool_name, args, raw_log_path
                    )
                    err = None
                except Exception as e:
                    # Hash the exception body — tool errors could echo
                    # filesystem paths / regex strings the model
                    # supplied; class name is fine to keep verbatim.
                    raw_em = f"{type(e).__name__}: {e}"
                    em_sha = hashlib.sha256(
                        raw_em.encode("utf-8")
                    ).hexdigest()[:16]
                    observation_text = (
                        f"ERROR: {type(e).__name__} "
                        f"message_sha256={em_sha}… "
                        f"message_len={len(raw_em)}"
                    )
                    err = (
                        f"{type(e).__name__} message_sha256={em_sha}… "
                        f"message_len={len(raw_em)}"
                    )
                rt_ms = (time.monotonic() - t0) * 1000.0
                obs_tokens = estimate_tokens(observation_text)
                tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "observation_tokens_estimate": obs_tokens,
                    "runtime_ms": rt_ms,
                    "error": err,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.get("id"),
                    "content": observation_text,
                })

            # Append assistant response, then user-role tool_results.
            # The budget enforcement at the TOP of the next loop iteration
            # will fail-closed if total_input now exceeds the cap. We do
            # NOT add a "no more tool calls" user-prompt nudge here —
            # that was a soft suggestion the model could ignore, and
            # tools=specs was still passed, so the next turn could (and
            # often did) issue more tool_use blocks.
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # stop_reason in {"end_turn", "stop_sequence", "max_tokens", ...}
        # — try to parse final JSON from text blocks.
        text = " ".join(
            b.get("text", "")
            for b in content
            if b.get("type") == "text"
        )
        try:
            final = normalize(parse_diagnosis_json(text))
            final_turn = turn
            break
        except Exception:
            # Agent emitted prose without JSON — give it one nudge if
            # budget allows.
            if turn < agent_config["max_iterations"]:
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "Re-emit your answer as STRICT JSON only, "
                        "matching the schema. No prose."
                    ),
                })
                continue
            final = unknown_body(
                "agent emitted non-JSON text and exhausted retries"
            )
            final_turn = turn
            budget_exhausted = True
            break

    if final is None:
        # Forced final no-tools cleanup call. Per Codex 2026-05-18 [high]:
        # when we exit the main loop without a final answer (budget
        # exhausted, max_iterations hit, or non-JSON streak), try ONE
        # last call with tools=[] disabled so the agent must emit JSON
        # rather than another tool_use block. This preserves the chance
        # of getting a final diagnosis even when the tool-using loop
        # ran out of budget. The forced-final call itself consumes some
        # input tokens beyond the configured cap — that is documented
        # in the diagnoser config as "tool-using turns capped".
        budget_exhausted = True
        try:
            messages.append({
                "role": "user",
                "content": (
                    "Budget exhausted; tools are now disabled. Emit your "
                    "best final_diagnosis JSON only, based on what you "
                    "have already observed. Strict JSON, no prose."
                ),
            })
            forced_resp = anthropic_post(
                messages,
                system_prompt,
                agent_config["max_output_tokens_per_turn"],
                [],  # tools disabled — model must respond with text only
                model,
                timeout_s,
                api_key,
            )
            last_response = forced_resp
            usage = forced_resp.get("usage") or {}
            total_input += int(usage.get("input_tokens") or 0)
            total_output += int(usage.get("output_tokens") or 0)
            forced_content = forced_resp.get("content") or []
            forced_text = " ".join(
                b.get("text", "")
                for b in forced_content
                if b.get("type") == "text"
            )
            try:
                final = normalize(parse_diagnosis_json(forced_text))
                # Use max_iterations+1 to signal "forced cleanup turn"
                # in agent_metadata.final_diagnosis_turn.
                final_turn = agent_config["max_iterations"] + 1
            except Exception:
                final = unknown_body(
                    "agent exhausted budget; forced no-tools final call "
                    "returned non-JSON"
                )
                final_turn = agent_config["max_iterations"] + 1
        except Exception:
            # Forced-final API call itself failed (network, 4xx). Fall
            # back to unknown_body without further retries.
            final = unknown_body(
                "agent exhausted iteration budget without emitting "
                "final JSON"
            )
            final_turn = agent_config["max_iterations"]

    # Resolved model (best-effort — `model` field of the last response).
    resolved_model = None
    last_usage = None
    if last_response is not None:
        resolved_model = last_response.get("model")
        last_usage = last_response.get("usage")

    model_info = {
        "provider_name": "anthropic",
        "requested_model": model,
        "resolved_model": resolved_model,
        "base_url": "https://api.anthropic.com/v1",
        # Per-turn usage is in agent_metadata; this is the last turn's
        # usage, kept for compatibility with the single-shot shim's
        # model_info shape.
        "usage": last_usage,
    }

    agent_metadata = {
        "iterations": turn,
        "tool_call_count": len(tool_calls),
        "tool_calls": tool_calls,
        "total_input_tokens_consumed": total_input,
        "total_output_tokens_consumed": total_output,
        "budget_exhausted": budget_exhausted,
        "final_diagnosis_turn": final_turn,
    }
    return final, agent_metadata, model_info


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main() -> int:
    payload = json.load(sys.stdin)
    verify_no_leakage(payload)

    # Privacy gate — mirror the single-shot CLI shim (lines 252-259).
    if (os.environ.get("CILOGBENCH_ALLOW_EXTERNAL_LLM") or "") \
            .strip().lower() not in {"1", "true", "yes", "on"}:
        sys.stderr.write(
            "diagnosis_shim_claude_agent: CILOGBENCH_ALLOW_EXTERNAL_LLM=1 "
            "required to invoke the Anthropic Messages API. Set it "
            "explicitly to opt in.\n"
        )
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.stderr.write(
            "diagnosis_shim_claude_agent: ANTHROPIC_API_KEY env var "
            "not set\n"
        )
        return 1

    system_prompt = payload.get("prompt", "")
    model = os.environ.get("CILOGBENCH_CLAUDE_MODEL", "claude-haiku-4-5")
    timeout_s = int(os.environ.get("CILOGBENCH_CLAUDE_TIMEOUT", "180"))

    raw_log_path = payload.get("raw_log_path")
    if not raw_log_path:
        # The runner is supposed to populate this for agent variants;
        # surface a structured taxonomy class so downstream by-prefix
        # counting works.
        envelope = {
            "_provider_error": (
                "runtime_tool_dispatch_error: raw_log_path missing "
                "from payload"
            ),
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(
            "diagnosis_shim_claude_agent: raw_log_path missing from "
            "payload\n"
        )
        return 1
    if not os.path.exists(raw_log_path):
        envelope = {
            "_provider_error": (
                f"runtime_tool_dispatch_error: raw_log_path does not "
                f"exist (path_sha256="
                f"{hashlib.sha256(raw_log_path.encode('utf-8')).hexdigest()[:16]}…)"
            ),
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(
            "diagnosis_shim_claude_agent: raw_log_path does not exist\n"
        )
        return 1

    # Two-phase try mirroring the single-shot shim:
    #   (1) drive the agent loop (network / auth / tool dispatch)
    #   (2) emit the final stdout JSON
    # Phase 1 failures may or may not have model_info depending on
    # whether ANY API call succeeded — run_agent_loop returns
    # model_info=None if not. Phase 2 failures are basically just
    # serialization issues; they get the model_info we already have.
    try:
        final, agent_metadata, model_info = run_agent_loop(
            payload, system_prompt, raw_log_path,
            model, timeout_s, api_key,
        )
    except Exception as e:
        # The agent loop blew up before producing a final answer. Hash
        # the exception body so model-controlled content cannot leak
        # into `metadata.provider_error`. Class name stays for
        # structural diagnostics.
        raw_msg = f"{type(e).__name__}: {e}"
        msg_sha = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:16]
        msg = (
            f"{type(e).__name__} message_sha256={msg_sha}… "
            f"message_len={len(raw_msg)}"
        )
        envelope = {
            "_provider_error": f"agent_loop_failed: {msg}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(f"diagnosis_shim_claude_agent: {msg}\n")
        return 1

    try:
        out = {**final, "_model_info": model_info,
               "_agent_metadata": agent_metadata}
        json.dump(out, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        raw_msg = f"{type(e).__name__}: {e}"
        msg_sha = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:16]
        msg = (
            f"{type(e).__name__} message_sha256={msg_sha}… "
            f"message_len={len(raw_msg)}"
        )
        envelope = {
            "_model_info": model_info,
            "_agent_metadata": agent_metadata,
            "_provider_error": f"post_agent_error: {msg}",
        }
        json.dump(envelope, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.stderr.write(f"diagnosis_shim_claude_agent: {msg}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
