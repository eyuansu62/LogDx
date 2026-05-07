#!/usr/bin/env python3
"""
Stub LLM summary shim for CILogBench M7 — **for infrastructure tests only**.

Speaks the stdin/stdout JSON contract of `tools/run_llm_summary_baseline.py`
(the M4 command provider):

  stdin  = {"messages":[{role,content}], "temperature":..., "metadata":{case_id, stage, prompt_version}}
  stdout = {"content": "...", "provider": "...", "model": null, "usage": {"input_tokens":..., "output_tokens":...}}

It is **not** a real LLM. It gives you a working `$LLM_SUMMARY_COMMAND` so
you can smoke-test the M7 wrapper — privacy audit, opt-in gate, signal
recall regeneration, diagnosis flow, experiment manifest, M7 report —
without an API key.

Do not cite numbers from this shim as summarizer quality. Swap for a real
LLM shim when running the actual experiment.
"""

import json
import math
import re
import sys

FAILURE_KEYWORDS = re.compile(
    r"error|failed|failure|traceback|exception|assert|panic|exit code|"
    r"##\[error\]|fatal:|^FAIL\b|--- FAIL|✘|✖|✗",
    re.IGNORECASE | re.MULTILINE,
)
MAX_LINE_LEN = 2000  # same guard used by other stubs — avoid regex blow-up


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def get_messages(payload: dict) -> tuple[str, str]:
    system = ""
    user = ""
    for m in payload.get("messages") or []:
        if m.get("role") == "system":
            system = m.get("content", "")
        elif m.get("role") == "user":
            user = m.get("content", "")
    return system, user


def map_stage(user_content: str) -> str:
    """Mimic the map prompt: emit one `- [CATEGORY] backtick-quoted line` per
    matching line. If nothing matches, return NO_RELEVANT_FAILURE_SIGNAL."""
    bullets: list[str] = []
    for line in user_content.splitlines():
        if len(line) > MAX_LINE_LEN:
            continue
        m = re.match(r"^L(\d+):\s?(.*)$", line)
        if not m:
            continue
        lineno, body = m.group(1), m.group(2)
        if not FAILURE_KEYWORDS.search(body):
            continue
        category = _categorize(body)
        body_short = body.strip()
        if len(body_short) > 200:
            body_short = body_short[:200] + "…"
        bullets.append(f"- [{category}] `{body_short}`  (lines: L{lineno})")
    return "\n".join(bullets) if bullets else "NO_RELEVANT_FAILURE_SIGNAL"


def reduce_stage(user_content: str) -> str:
    """Mimic the reduce prompt: collect bullets by category, write the seven
    required sections. Keeps the stub simple — the real LLM summary will
    produce much richer text."""
    sections: dict[str, list[str]] = {
        "Primary Failure": [],
        "Critical Evidence": [],
        "Failed Tests / Checks": [],
        "Relevant Files and Locations": [],
        "Commands and Exit Codes": [],
        "Possible Root Cause": [],
        "Uncertainties / Missing Context": [],
    }
    for ln in user_content.splitlines():
        if not ln.strip().startswith("- ["):
            continue
        m = re.match(r"- \[([A-Z_]+)\]\s+(.*)", ln)
        if not m:
            continue
        cat, rest = m.group(1), m.group(2)
        sec = _section_for(cat)
        sections[sec].append(f"- {rest}")
    for k, vals in list(sections.items()):
        seen: set[str] = set(); uniq: list[str] = []
        for v in vals:
            if v in seen:
                continue
            seen.add(v); uniq.append(v)
        sections[k] = uniq[:40]
    out = ["# CI Failure Summary (stub-summarizer-v1)"]
    out.append("")
    out.append(
        "_Note: this summary was produced by the CILogBench infrastructure "
        "stub, not a real LLM. The CI-failure categorization below is a "
        "deterministic keyword heuristic._"
    )
    out.append("")
    for header, items in sections.items():
        out.append(f"## {header}")
        out.append("")
        if items:
            out.extend(items)
        else:
            out.append("- _(none identified)_")
        out.append("")
    return "\n".join(out)


def _categorize(body: str) -> str:
    low = body.lower()
    if "##[error]" in low or "process completed with exit code" in low:
        return "GHA_ERROR"
    if re.search(r"^FAILED\b|--- FAIL:|^FAIL\s", body):
        return "FAILED_TEST"
    if "panicked at" in low:
        return "EXCEPTION"
    if "traceback" in low or "assertionerror" in low or body.strip().startswith("E "):
        return "ASSERTION"
    if re.search(r"^\s*error(\[E\d+\])?:", body) or re.search(r":\d+:\s*error:", body):
        return "COMPILE_ERROR"
    if body.strip().startswith("fatal:"):
        return "EXCEPTION"
    if "exit code" in low:
        return "EXIT_CODE"
    if re.search(r"\.(py|js|ts|rs|go|java):\d+", body):
        return "STACK_LOCATION"
    return "ASSERTION"


def _section_for(cat: str) -> str:
    return {
        "FAILED_TEST":    "Failed Tests / Checks",
        "STACK_LOCATION": "Relevant Files and Locations",
        "EXIT_CODE":      "Commands and Exit Codes",
        "GHA_ERROR":      "Commands and Exit Codes",
        "COMMAND":        "Commands and Exit Codes",
        "REMEDIATION":    "Possible Root Cause",
        "UNCERTAINTY":    "Uncertainties / Missing Context",
    }.get(cat, "Critical Evidence")


def main() -> int:
    payload = json.load(sys.stdin)
    _, user_content = get_messages(payload)
    stage = ((payload.get("metadata") or {}).get("stage") or "").lower()

    if stage == "map":
        text = map_stage(user_content)
    elif stage == "reduce":
        text = reduce_stage(user_content)
    else:
        # Fall back to treating the content as a single chunk.
        text = map_stage(user_content)

    response = {
        "content": text,
        "provider": "stub-summarizer",
        "model": None,
        "usage": {
            "input_tokens": estimate_tokens(user_content),
            "output_tokens": estimate_tokens(text),
        },
    }
    json.dump(response, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
