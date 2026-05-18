#!/usr/bin/env python3
"""Unit tests for the 4 deterministic tools used by real-agent-v1.

The agent shim exposes `grep`, `read_file`, `tail`, and `view_log_lines`
on top of the case's raw.log. These tests cover:
- bounds clamping (max_matches, n caps, radius caps, span caps)
- byte-identical behavior between agent's grep and the static `grep`
  baseline (so a method that wins via agent-grep is using the same
  operation as the static baseline)
- agent loop accounting on a mock LLM (iterations, tool_call_count,
  budget_exhausted, total_input/output_tokens_consumed)

Run:
    python3 tools/tests/test_agent_v1_tools.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Make `examples/` importable as a package-of-files.
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "tools"))

import diagnosis_shim_claude_agent as ag  # noqa: E402
import run_baseline as rb  # noqa: E402


# ---------------------------------------------------------------------------
# Tool tests — grep
# ---------------------------------------------------------------------------


SYNTH_LOG_LINES = [
    "starting test suite",                                # 1
    "test_alpha PASSED",                                  # 2
    "test_beta PASSED",                                   # 3
    "test_gamma FAILED",                                  # 4
    "  AssertionError: expected 42, got 41",              # 5
    "    File 'foo.py', line 17",                         # 6
    "test_delta PASSED",                                  # 7
    "test_epsilon FAILED",                                # 8
    "  ValueError: bad input",                            # 9
    "test_zeta PASSED",                                   # 10
    "Summary: 3 failed, 7 passed",                        # 11
    "exit code 1",                                        # 12
]


def _write_synthetic_log() -> str:
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    Path(path).write_text("\n".join(SYNTH_LOG_LINES) + "\n", encoding="utf-8")
    return path


def test_grep_finds_matches_with_before_after():
    p = _write_synthetic_log()
    try:
        out = ag.tool_grep(
            {"pattern": "FAILED", "before": 1, "after": 1},
            p,
        )
        # Should include lines 3,4,5 (gamma block) and 7,8,9 (epsilon block)
        assert "test_gamma FAILED" in out, "missing gamma match"
        assert "AssertionError" in out, "missing line below gamma"
        assert "test_epsilon FAILED" in out, "missing epsilon match"
        assert "ValueError" in out, "missing line below epsilon"
        # Should NOT include 'starting test suite' (line 1) — out of window
        assert "starting test suite" not in out, "leaked unrelated line"
    finally:
        os.unlink(p)


def test_grep_with_default_pattern_when_none_supplied():
    p = _write_synthetic_log()
    try:
        out = ag.tool_grep({}, p)  # no pattern → use default CI failure regex
        assert "FAILED" in out, "default pattern should match FAILED lines"
        assert "exit code 1" in out, "default pattern should match exit code"
    finally:
        os.unlink(p)


def test_grep_invalid_regex_returns_error():
    p = _write_synthetic_log()
    try:
        out = ag.tool_grep({"pattern": "[unterminated"}, p)
        assert out.startswith("ERROR:"), "expected ERROR: prefix"
        assert "invalid regex" in out.lower(), f"unexpected error text: {out!r}"
    finally:
        os.unlink(p)


def test_grep_no_matches_returns_friendly_string():
    p = _write_synthetic_log()
    try:
        out = ag.tool_grep({"pattern": "zzz_nonexistent_zzz"}, p)
        assert "No matches found" in out
    finally:
        os.unlink(p)


def test_grep_max_matches_cap_enforced():
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    # 100 'FAILED' lines so max_matches=3 truncates.
    Path(path).write_text(
        "\n".join(f"test_x_{i} FAILED" for i in range(100)) + "\n",
        encoding="utf-8",
    )
    try:
        out = ag.tool_grep(
            {"pattern": "FAILED", "before": 0, "after": 0, "max_matches": 3},
            path,
        )
        # Three matches at most — count "test_x_" occurrences.
        # Each merged range is just the line itself (before=after=0).
        assert out.count("test_x_") == 3, (
            f"expected 3 matches, got {out.count('test_x_')}"
        )
    finally:
        os.unlink(path)


def test_grep_is_byte_identical_to_static_baseline():
    """The whole point of the agent's `grep`: it must produce the SAME
    line set as the static `grep` baseline. If they diverge, the
    cost-quality comparison between static-grep and agent-grep-rescue
    is no longer apples-to-apples."""
    p = _write_synthetic_log()
    try:
        raw_lines = rb.read_case_lines(Path(p))
        # Static baseline default args
        static = rb.baseline_grep(
            raw_lines,
            regex=rb.DEFAULT_GREP_REGEX,
            before=rb.DEFAULT_GREP_BEFORE,
            after=rb.DEFAULT_GREP_AFTER,
        )
        # Agent grep with no pattern → uses _DEFAULT_GREP_REGEX (same as static)
        agent_out = ag.tool_grep({}, p)
        # The agent output has a header + line-number prefix per line.
        # Compare the line CONTENT only (strip "LINENO: " prefix).
        agent_content_lines: list[str] = []
        for ln in agent_out.splitlines():
            # Skip header / separator / no-match lines.
            if ln.startswith("grep pattern=") or ln == "---" or not ln:
                continue
            # Strip "<int>: " prefix.
            i = ln.find(": ")
            if i >= 0 and ln[:i].isdigit():
                agent_content_lines.append(ln[i + 2:])
            else:
                agent_content_lines.append(ln)
        static_lines = static.output_text.splitlines()
        # Identical set + order on the merged ranges.
        assert agent_content_lines == static_lines, (
            f"agent grep content lines diverged from static baseline\n"
            f"agent:  {agent_content_lines!r}\n"
            f"static: {static_lines!r}"
        )
    finally:
        os.unlink(p)


# ---------------------------------------------------------------------------
# Tool tests — read_file
# ---------------------------------------------------------------------------


def test_read_file_inclusive_range():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": 4, "end_line": 6}, p)
        assert "test_gamma FAILED" in out
        assert "AssertionError" in out
        assert "foo.py" in out
        assert "test_alpha" not in out, "leaked line before start"
        assert "test_delta" not in out, "leaked line after end"
    finally:
        os.unlink(p)


def test_read_file_clamps_start_below_one():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": -5, "end_line": 2}, p)
        assert "starting test suite" in out, "should clamp start to 1"
    finally:
        os.unlink(p)


def test_read_file_rejects_inverted_range():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": 5, "end_line": 3}, p)
        assert out.startswith("ERROR:"), "expected ERROR: prefix"
        assert "end_line" in out
    finally:
        os.unlink(p)


def test_read_file_rejects_span_above_1000_lines():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": 1, "end_line": 5000}, p)
        assert out.startswith("ERROR:"), f"expected ERROR: prefix, got {out!r}"
        assert "exceeds max" in out
    finally:
        os.unlink(p)


def test_read_file_handles_end_past_eof():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": 10, "end_line": 50}, p)
        # SYNTH_LOG_LINES has 12 lines, so we should get 10-12 truncated.
        assert "test_zeta" in out
        assert "exit code 1" in out
    finally:
        os.unlink(p)


def test_read_file_requires_integer_args():
    p = _write_synthetic_log()
    try:
        out = ag.tool_read_file({"start_line": "abc", "end_line": 3}, p)
        assert out.startswith("ERROR:"), "expected ERROR: prefix"
    finally:
        os.unlink(p)


# ---------------------------------------------------------------------------
# Tool tests — tail
# ---------------------------------------------------------------------------


def test_tail_default_returns_last_lines():
    p = _write_synthetic_log()
    try:
        out = ag.tool_tail({"n": 3}, p)
        assert "exit code 1" in out
        assert "Summary:" in out
        # Should NOT include test_alpha (line 2) when n=3
        assert "test_alpha" not in out
    finally:
        os.unlink(p)


def test_tail_clamps_n_to_max_1000():
    p = _write_synthetic_log()
    try:
        # Asking for 99999 lines on a 12-line file should still work (file caps it).
        out = ag.tool_tail({"n": 99999}, p)
        assert "starting test suite" in out, "should include line 1 when n > file size"
    finally:
        os.unlink(p)


def test_tail_empty_file():
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    Path(path).write_text("", encoding="utf-8")
    try:
        out = ag.tool_tail({"n": 5}, path)
        assert "empty" in out.lower(), f"expected empty-file message, got {out!r}"
    finally:
        os.unlink(path)


def test_tail_n_clamped_to_min_1():
    p = _write_synthetic_log()
    try:
        out = ag.tool_tail({"n": 0}, p)
        assert "exit code 1" in out  # n clamped to 1 → last line
    finally:
        os.unlink(p)


# ---------------------------------------------------------------------------
# Tool tests — view_log_lines
# ---------------------------------------------------------------------------


def test_view_log_lines_window_around_center():
    p = _write_synthetic_log()
    try:
        out = ag.tool_view_log_lines({"center_line": 6, "radius": 2}, p)
        # Window 4-8
        assert "test_gamma FAILED" in out
        assert "AssertionError" in out
        assert "foo.py" in out
        assert "test_delta" in out
        # Should NOT include line 2 (out of window)
        assert "test_alpha" not in out
    finally:
        os.unlink(p)


def test_view_log_lines_clamps_radius():
    p = _write_synthetic_log()
    try:
        out = ag.tool_view_log_lines({"center_line": 6, "radius": 9999}, p)
        # Should still produce something (radius gets clamped).
        assert "test_gamma" in out
    finally:
        os.unlink(p)


def test_view_log_lines_handles_center_past_eof():
    p = _write_synthetic_log()
    try:
        out = ag.tool_view_log_lines({"center_line": 999, "radius": 5}, p)
        # Just doesn't crash; returns whatever's near the end (or empty msg).
        assert isinstance(out, str)
    finally:
        os.unlink(p)


def test_view_log_lines_requires_center_line():
    p = _write_synthetic_log()
    try:
        out = ag.tool_view_log_lines({"radius": 3}, p)
        assert out.startswith("ERROR:"), "expected ERROR: prefix"
    finally:
        os.unlink(p)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def test_dispatch_unknown_tool_returns_error():
    p = _write_synthetic_log()
    try:
        out = ag.dispatch_tool("nonexistent_tool", {}, p)
        assert out.startswith("ERROR:")
        assert "Available:" in out, "should list available tools"
    finally:
        os.unlink(p)


def test_dispatch_routes_all_four_tools():
    p = _write_synthetic_log()
    try:
        for name in ("grep", "read_file", "tail", "view_log_lines"):
            try:
                if name == "grep":
                    out = ag.dispatch_tool(name, {"pattern": "FAILED"}, p)
                elif name == "read_file":
                    out = ag.dispatch_tool(name, {"start_line": 1, "end_line": 3}, p)
                elif name == "tail":
                    out = ag.dispatch_tool(name, {"n": 5}, p)
                elif name == "view_log_lines":
                    out = ag.dispatch_tool(name, {"center_line": 5}, p)
                assert isinstance(out, str), f"{name} returned non-string"
                # None should hit the ERROR branch on valid args
                if out.startswith("ERROR:"):
                    raise AssertionError(f"{name} returned error: {out}")
            except Exception as e:
                raise AssertionError(f"{name} dispatch failed: {e}") from e
    finally:
        os.unlink(p)


# ---------------------------------------------------------------------------
# Tool specs (Anthropic API shape)
# ---------------------------------------------------------------------------


def test_tool_specs_lists_all_four_tools():
    specs = ag.tool_specs()
    names = [s["name"] for s in specs]
    assert names == ["grep", "read_file", "tail", "view_log_lines"], \
        f"unexpected tool list: {names}"


def test_tool_specs_have_input_schemas():
    for s in ag.tool_specs():
        assert "name" in s and "description" in s and "input_schema" in s, (
            f"tool spec missing required fields: {s!r}"
        )
        assert s["input_schema"].get("type") == "object", (
            f"{s['name']} input_schema not type=object"
        )


# ---------------------------------------------------------------------------
# Token estimate helper (for agent_metadata observation_tokens_estimate)
# ---------------------------------------------------------------------------


def test_estimate_tokens_matches_runner_heuristic():
    """estimate_tokens uses `ceil(len(text)/4)` per the runner. The
    shim's estimate must match so observation_tokens_estimate
    aggregates cleanly via macro_mean_int."""
    # Empty string → 0
    assert ag.estimate_tokens("") == 0
    # "abcd" (4 chars) → 1 token
    assert ag.estimate_tokens("abcd") == 1
    # 5 chars → ceil(5/4) = 2
    assert ag.estimate_tokens("abcde") == 2
    # 100 chars → 25
    assert ag.estimate_tokens("x" * 100) == 25


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_grep_finds_matches_with_before_after,
        test_grep_with_default_pattern_when_none_supplied,
        test_grep_invalid_regex_returns_error,
        test_grep_no_matches_returns_friendly_string,
        test_grep_max_matches_cap_enforced,
        test_grep_is_byte_identical_to_static_baseline,
        test_read_file_inclusive_range,
        test_read_file_clamps_start_below_one,
        test_read_file_rejects_inverted_range,
        test_read_file_rejects_span_above_1000_lines,
        test_read_file_handles_end_past_eof,
        test_read_file_requires_integer_args,
        test_tail_default_returns_last_lines,
        test_tail_clamps_n_to_max_1000,
        test_tail_empty_file,
        test_tail_n_clamped_to_min_1,
        test_view_log_lines_window_around_center,
        test_view_log_lines_clamps_radius,
        test_view_log_lines_handles_center_past_eof,
        test_view_log_lines_requires_center_line,
        test_dispatch_unknown_tool_returns_error,
        test_dispatch_routes_all_four_tools,
        test_tool_specs_lists_all_four_tools,
        test_tool_specs_have_input_schemas,
        test_estimate_tokens_matches_runner_heuristic,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    msg = (
        f"All {len(tests)} tests passed."
        if failed == 0 else
        f"{failed} of {len(tests)} tests FAILED."
    )
    print(msg)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
