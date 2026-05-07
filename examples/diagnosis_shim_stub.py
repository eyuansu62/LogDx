#!/usr/bin/env python3
"""
Stub diagnosis shim for CILogBench M6 — **for infrastructure tests only**.

This script fulfills the stdin/stdout JSON contract documented in
`docs/methods/diagnosis.md` without calling any external model. It gives
you a working `$DIAGNOSIS_COMMAND` so you can:

    1. Smoke-test `tools/run_m6_experiment.py` end-to-end.
    2. Verify the wrapper's external-LLM opt-in gate, privacy audit,
       cache, and manifest generation.
    3. Confirm that the experiment report renders.

It is **not** a real benchmark method. The output is a deterministic
keyword heuristic similar to the mock diagnoser built into
`tools/run_diagnosis.py`. Do not cite numbers produced by this shim as
debugger quality.

Usage (via the M6 wrapper):

    export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_stub.py"
    export CILOGBENCH_ALLOW_EXTERNAL_LLM=0  # stub does not call out
    python tools/run_m6_experiment.py \\
        --split dev --diagnoser-name stub-debugger-v1 \\
        --config configs/diagnosers/example.debugger-v1-command.json \\
        --context-method all --no-external-llm-required

Swap this stub for your real shim when you are ready to run a real model.
"""

import json
import re
import sys

KEYWORDS: list[tuple[str, re.Pattern[str], str]] = [
    ("permission_or_secret",
        re.compile(r"fatal:\s+detected dubious ownership", re.IGNORECASE),
        "Git refused to operate on the workspace due to dubious ownership."),
    ("formatting_failure",
        re.compile(r"prettier|prettier-check|yarn prettier-all", re.IGNORECASE),
        "Prettier reports formatting drift."),
    ("type_error",
        re.compile(r"\bmypy\b|stubtest|\[attr-defined\]|\[no-untyped-call\]", re.IGNORECASE),
        "Type checker reports errors."),
    ("compile_error",
        re.compile(r"error\[E\d+\]|trybuild|mismatched types|panicked at", re.IGNORECASE),
        "Compiler or trybuild compile-fail test failed."),
    ("test_assertion",
        re.compile(r"^FAILED\s|--- FAIL:|AssertionError|DeprecationWarning", re.MULTILINE),
        "A runtime test failed."),
    ("lint_failure",
        re.compile(r"\beslint\b|\bruff\b|\bclippy\b", re.IGNORECASE),
        "Linter reports failures."),
]

MAX_LINE_LEN = 2000


def pick_quote(ctx: str, pat: re.Pattern[str]) -> str:
    m = pat.search(ctx)
    if not m:
        return ""
    pre = ctx.rfind("\n", 0, m.start()) + 1
    post = ctx.find("\n", m.end())
    line = ctx[pre:post if post >= 0 else m.end() + 80].strip()
    return line[:200]


def diagnose(context: str, metadata: dict) -> dict:
    # Skip pathologically long lines so a pytest progress bar can't trigger
    # catastrophic regex backtracking. See the matching guard in the mock
    # diagnoser in tools/run_diagnosis.py.
    safe_ctx = "\n".join(
        ln for ln in context.splitlines() if len(ln) <= MAX_LINE_LEN
    )
    for category, pat, hypothesis in KEYWORDS:
        if pat.search(safe_ctx):
            quote = pick_quote(safe_ctx, pat)
            return {
                "summary": (
                    f"{hypothesis} (stub shim; pattern {pat.pattern!r} "
                    f"on {metadata.get('context_method', 'unknown')} context)"
                ),
                "root_cause_category": category,
                "root_cause": hypothesis,
                "confidence": 0.55,
                "relevant_files": [],
                "relevant_tests": [],
                "evidence": ([{"quote": quote,
                                "reason": f"Matched pattern for {category}."}]
                              if quote else []),
                "suggested_fix": "",
            }
    return {
        "summary": "Stub shim could not identify a known failure pattern.",
        "root_cause_category": "unknown",
        "root_cause": "unknown",
        "confidence": 0.0,
        "relevant_files": [],
        "relevant_tests": [],
        "evidence": [],
        "suggested_fix": "Inspect the full CI log.",
    }


def main() -> int:
    payload = json.load(sys.stdin)
    context = payload.get("context", "")
    metadata = {
        "context_method": payload.get("context_method", ""),
        "case_id": payload.get("case_id", ""),
    }
    diag = diagnose(context, metadata)
    json.dump(diag, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
