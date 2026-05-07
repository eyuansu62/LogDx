"""Regression tests for tools/audit_context_privacy.py.

These tests assert two invariants flagged by Codex adversarial review
on 2026-05-07:

  1. A real secret value (any of the patterns in SECRET_PATTERNS) must
     never appear verbatim in `privacy_audit.json`, the markdown
     report, or the tool's stdout.

  2. The audit must fail closed (nonzero exit) whenever any portion of
     the input was not actually scanned — long-line skip, file
     truncation, or split-mode `incomplete_scans > 0`.

Run as:
    python3 tools/tests/test_audit_redaction.py

The script exits 0 on success and prints a one-line summary per case.
On failure it prints the assertion that broke and exits 1.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "audit_context_privacy.py"

# Synthetic credentials exercise each redaction path.
SECRETS = {
    "aws_access_key":          "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_key_assigned": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "github_classic_token":    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "openai_key":              "sk-abcdefghijklmnopqrstuvwxyz0123456789",
    "bearer_token":            "Bearer abcdefghijklmnopqrstuvwxyz0123",
    "password_assignment":     "password=hunter2hunter2hunter",
}

# Lines that exercise each pattern.
SAMPLE_LINES = [
    f"line 1: AWS key {SECRETS['aws_access_key']} found",
    f"line 2: aws_secret_access_key={SECRETS['aws_secret_key_assigned']}",
    f"line 3: token: {SECRETS['github_classic_token']}",
    f"line 4: openai sk var: {SECRETS['openai_key']}",
    f"line 5: Authorization: {SECRETS['bearer_token']}",
    f"line 6: db url with {SECRETS['password_assignment']}",
]


def run_raw_log(log_path: Path) -> tuple[int, str, str, dict]:
    """Run audit_context_privacy.py --raw-log; return (exit, stdout,
    stderr, parsed_json_or_empty)."""
    r = subprocess.run(
        ["python3", str(TOOL), "--raw-log", str(log_path)],
        capture_output=True, text=True, cwd=ROOT,
    )
    audit_path = log_path.parent / "privacy_audit.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    return r.returncode, r.stdout, r.stderr, audit


def assert_no_leak(text_blob: str, label: str) -> None:
    for kind, secret in SECRETS.items():
        if secret in text_blob:
            raise AssertionError(
                f"❌ {label} contains verbatim secret value for {kind!r}. "
                f"This is exactly the leak Codex flagged."
            )


def test_redaction_covers_all_patterns() -> None:
    """Real secret values must never appear in JSON or stdout, including
    `aws_secret_access_key=<value>` lines (the bug Codex flagged in
    review #2)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "synthetic.log"
        log.write_text("\n".join(SAMPLE_LINES) + "\n")
        ec, out, err, audit = run_raw_log(log)
        # Hits should be present (we put 6 secrets in the log).
        assert ec == 2, f"expected exit 2 (hits), got {ec}\nstderr={err}"
        assert audit.get("total_hits", 0) >= 5, (
            f"expected ≥5 hits, got {audit.get('total_hits')}"
        )
        # No secret may appear verbatim in any output channel.
        json_text = json.dumps(audit, ensure_ascii=False)
        assert_no_leak(json_text, "privacy_audit.json")
        assert_no_leak(out, "stdout")
        assert_no_leak(err, "stderr")
        print(f"  ✓ redaction-covers-all-patterns: "
              f"hits={audit['total_hits']}, exit={ec}, no leaks")


def test_long_line_fails_closed() -> None:
    """A long line (>MAX_LINE_LEN_FOR_SCAN) is skipped; exit must be 3."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "longline.log"
        log.write_text("normal\n" + ("A" * 9000) + "\nnormal end\n")
        ec, _, _, audit = run_raw_log(log)
        assert ec == 3, f"expected exit 3 (incomplete), got {ec}"
        assert audit["complete_scan"] is False
        assert audit["lines_skipped_long"] == 1
        print(f"  ✓ long-line-fails-closed: exit={ec}, "
              f"skipped={audit['lines_skipped_long']}")


def test_truncate_fails_closed() -> None:
    """A file >MAX_LINES_PER_FILE is truncated; exit must be 3."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "manylines.log"
        # Write 50_100 short lines.
        with log.open("w") as f:
            for i in range(50_100):
                f.write(f"line {i}\n")
        ec, _, _, audit = run_raw_log(log)
        assert ec == 3, f"expected exit 3 (incomplete), got {ec}"
        assert audit["complete_scan"] is False
        assert audit["truncated_after_line"] == 50_000
        print(f"  ✓ truncate-fails-closed: exit={ec}, "
              f"truncated_after={audit['truncated_after_line']}")


def test_clean_log_passes() -> None:
    """A short clean log must exit 0 and have no hits."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "clean.log"
        log.write_text("just\nnormal\nlines\n")
        ec, _, _, audit = run_raw_log(log)
        assert ec == 0, f"expected exit 0 (clean), got {ec}"
        assert audit["total_hits"] == 0
        assert audit["complete_scan"] is True
        print(f"  ✓ clean-log-passes: exit={ec}, hits=0")


def test_multiple_secrets_one_line_all_redacted() -> None:
    """Per Codex adversarial review #3: when a single line contains
    multiple secrets, EVERY secret value must be redacted in the
    snippet. The previous code only redacted the first matching span,
    leaving the second secret verbatim in `line_snippet_redacted`."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "multi.log"
        # One line with both an AWS key and a GitHub PAT.
        log.write_text(
            f"combined {SECRETS['aws_access_key']} and "
            f"{SECRETS['github_classic_token']} on one line\n"
        )
        ec, out, err, audit = run_raw_log(log)
        assert ec == 2, f"expected exit 2 (hits), got {ec}\nstderr={err}"
        assert audit.get("total_hits", 0) >= 2
        # Critical: NEITHER secret may appear verbatim anywhere in the
        # output — not in the snippet, not in stdout/stderr, not in
        # the JSON-as-a-blob.
        json_text = json.dumps(audit, ensure_ascii=False)
        assert_no_leak(json_text, "privacy_audit.json")
        assert_no_leak(out, "stdout")
        assert_no_leak(err, "stderr")
        # Snippets across all hits must contain only [REDACTED] in
        # place of both secrets.
        for h in audit.get("hits", []):
            snip = h.get("line_snippet_redacted", "")
            for sec in (SECRETS["aws_access_key"],
                        SECRETS["github_classic_token"]):
                assert sec not in snip, (
                    f"snippet still contains secret {sec!r}: {snip!r}"
                )
        print(f"  ✓ multi-secret-one-line-all-redacted: hits={audit['total_hits']}")


def run_split(results_dir: Path, split: str, method: str) -> tuple[int, str, str]:
    """Run the split-mode audit and return (exit, stdout, stderr)."""
    r = subprocess.run(
        ["python3", str(TOOL),
         "--split", split,
         "--context-method", method,
         "--results-dir", str(results_dir),
         "--reports-dir", str(results_dir / "reports")],
        capture_output=True, text=True, cwd=ROOT,
    )
    return r.returncode, r.stdout, r.stderr


def test_missing_method_dir_fails_closed() -> None:
    """Per Codex adversarial review #3: an explicit
    `--context-method missing-or-typo` used to exit 0 because the
    code silently appended a 'no context directory found' note and
    moved on. That let a typo-or-missing method dir silently
    authorize external sharing through the audit gate."""
    with tempfile.TemporaryDirectory() as td:
        results_dir = Path(td) / "results"
        split = "_test_missing"
        method_dir = results_dir / split
        method_dir.mkdir(parents=True)
        # No method/ subdir created.
        ec, out, err = run_split(results_dir, split, "typo_method")
        assert ec == 3, (
            f"expected exit 3 (missing dir, fail closed), got {ec}\n"
            f"stdout={out}\nstderr={err}"
        )
        print(f"  ✓ missing-method-dir-fails-closed: exit={ec}")


def test_empty_method_dir_fails_closed() -> None:
    """Method directory exists but contains zero *.txt context files —
    same fail-closed semantics as missing dir per Codex review #3."""
    with tempfile.TemporaryDirectory() as td:
        results_dir = Path(td) / "results"
        split = "_test_empty"
        method_dir = results_dir / split / "test_method"
        method_dir.mkdir(parents=True)
        # Provide manifest jsonl so discover_methods would still see it.
        (results_dir / split / "test_method.jsonl").write_text(
            '{"case_id":"placeholder"}\n'
        )
        ec, out, err = run_split(results_dir, split, "test_method")
        assert ec == 3, (
            f"expected exit 3 (empty dir, fail closed), got {ec}\n"
            f"stdout={out}\nstderr={err}"
        )
        print(f"  ✓ empty-method-dir-fails-closed: exit={ec}")


def main() -> int:
    print(f"Running audit redaction regression tests against {TOOL}…")
    tests = [
        test_clean_log_passes,
        test_redaction_covers_all_patterns,
        test_multiple_secrets_one_line_all_redacted,
        test_long_line_fails_closed,
        test_truncate_fails_closed,
        test_missing_method_dir_fails_closed,
        test_empty_method_dir_fails_closed,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {e}")
            failed += 1
    if failed:
        print(f"\n{failed} of {len(tests)} test(s) FAILED.")
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
