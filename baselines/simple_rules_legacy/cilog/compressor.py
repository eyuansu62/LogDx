"""
cilog compressor - core compression engine.

Design philosophy:
- Rule-based, zero ML. Verifiable and fast.
- Preserve failures in full with surrounding context.
- Collapse known-noise patterns (progress bars, dependency lists, ANSI, timestamps).
- Every section keeps a line-number anchor so Agent can request expansion if needed.
"""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass, field
from typing import Iterable


# -----------------------------------------------------------------------------
# Low-level cleanup
# -----------------------------------------------------------------------------

# ANSI color/style escape codes
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

# GitHub Actions timestamp prefix: "2024-03-15T10:23:45.1234567Z "
GHA_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s?")

# Carriage-return overwrites (progress bars reuse the same line).
# We keep only the final state after the last \r on any line.
def collapse_cr(line: str) -> str:
    if "\r" in line:
        return line.rsplit("\r", 1)[-1]
    return line


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def strip_gha_timestamp(s: str) -> str:
    return GHA_TIMESTAMP_RE.sub("", s)


# Max line length we'll keep untouched — longer lines get either replaced with
# a marker (if they look like binary blobs) or truncated with a length hint.
MAX_REASONABLE_LINE = 500


def is_binary_blob(line: str, min_len: int = 200) -> bool:
    """
    Detect base64 / hex / binary-encoded blobs.

    Heuristic: a line ≥ min_len chars with very high alphanumeric density and
    few spaces is almost certainly encoded binary data (base64 screenshots,
    hex dumps, embedded certs, etc.), not useful debug info.
    """
    s = line.strip()
    if len(s) < min_len:
        return False
    valid_chars = sum(1 for c in s if c.isalnum() or c in "+/=_-")
    spaces = sum(1 for c in s if c == " ")
    if spaces > 3:
        return False
    return valid_chars / len(s) > 0.92


def shrink_long_line(line: str) -> str:
    """Replace overly long lines. Binary blobs → marker. Others → truncated with length hint."""
    if is_binary_blob(line):
        return f"[binary/base64 blob, {len(line)} chars elided]"
    if len(line) > MAX_REASONABLE_LINE:
        return line[:200] + f" ... [+{len(line) - 200} chars elided]"
    return line


def normalize_line(line: str) -> str:
    line = collapse_cr(line)
    line = strip_ansi(line)
    line = strip_gha_timestamp(line)
    line = line.rstrip("\r\n")
    # Any line longer than ~500 chars is either a base64 blob or wrapped JSON.
    # Either way, keep the identifying prefix and drop the rest.
    if len(line) > MAX_REASONABLE_LINE:
        line = shrink_long_line(line)
    return line


# -----------------------------------------------------------------------------
# Section splitter: use GitHub Actions ##[group] markers
# -----------------------------------------------------------------------------

# GHA emits "##[group]Name" and "##[endgroup]". Some use "::group::".
GROUP_START_RE = re.compile(r"^##\[group\](.*)$|^::group::(.*)$")
GROUP_END_RE = re.compile(r"^##\[endgroup\]$|^::endgroup::$")
ERROR_MARKER_RE = re.compile(r"^##\[error\](.*)$|^::error::(.*)$")
WARNING_MARKER_RE = re.compile(r"^##\[warning\](.*)$|^::warning::(.*)$")


@dataclass
class Section:
    name: str
    lines: list[str] = field(default_factory=list)
    start_line: int = 0  # 1-indexed position in original log
    has_error_marker: bool = False


def split_sections(lines: list[str]) -> list[Section]:
    """Split normalized log into GHA sections. Lines outside any group go to '_preamble'."""
    sections: list[Section] = []
    current = Section(name="_preamble", start_line=1)

    for idx, line in enumerate(lines, start=1):
        m_start = GROUP_START_RE.match(line)
        m_end = GROUP_END_RE.match(line)
        m_err = ERROR_MARKER_RE.match(line)

        if m_start:
            if current.lines:
                sections.append(current)
            name = (m_start.group(1) or m_start.group(2) or "").strip()
            current = Section(name=name or "unnamed", start_line=idx)
            continue

        if m_end:
            if current.lines:
                sections.append(current)
            current = Section(name="_between_groups", start_line=idx + 1)
            continue

        if m_err:
            current.has_error_marker = True

        current.lines.append(line)

    if current.lines:
        sections.append(current)

    return sections


# -----------------------------------------------------------------------------
# Framework detection + compressors
# -----------------------------------------------------------------------------

# Signals of failure anywhere in a block
FAILURE_SIGNALS = [
    re.compile(r"^FAIL\s", re.I),
    re.compile(r"^FAILED\b", re.I),
    re.compile(r"^FAIL\s+tests?/"),  # jest/vitest
    re.compile(r"^\s*(?:✗|×|✖)\s", re.UNICODE),
    re.compile(r"\bError:"),
    re.compile(r"\bTraceback \(most recent call last\)"),
    re.compile(r"^E\s{2,}", re.M),  # pytest short-summary
    re.compile(r"panicked at"),
    re.compile(r"^error(?:\[E\d+\])?:", re.I),  # cargo / rustc
    re.compile(r"AssertionError"),
    re.compile(r"^\s*at .*:\d+:\d+\)?$"),  # JS stack frame
    re.compile(r"##\[error\]"),
    # Narrowed: require "status " or "code " so bare `exit 1` inside an
    # echoed shell-script body (a common GHA step-preamble pattern) doesn't
    # get flagged as a failure. The explicit "Process completed with exit
    # code N" pattern below still catches the real GHA termination report.
    re.compile(r"exit(ed|) (?:status|code) [1-9]"),
    re.compile(r"Process completed with exit code [1-9]"),
    # mypy / pyright / tsc-style diagnostics: "path/file.ext:N[:C]: error: ..."
    # The "error:" token is in the middle of the line, not at start, so the
    # bare `^error:` pattern above doesn't fire. Matches one error per line.
    re.compile(r"^\S+:\d+(?::\d+)?:\s*error:", re.I),
    # Indented rustc diagnostics (trybuild wraps every line with 4 spaces).
    # Allowing `\s*` also covers jest/vitest etc. indenting their own errors.
    re.compile(r"^\s+error(?:\[E\d+\])?:", re.I),
    # Tool-level fatals: git/docker/mount/fsck all use "fatal:" at line start.
    re.compile(r"^fatal:\s"),
]


def line_has_failure_signal(line: str) -> bool:
    return any(p.search(line) for p in FAILURE_SIGNALS)


# Noise patterns: lines that carry ~no decision-relevant info
NOISE_PATTERNS = [
    re.compile(r"^\s*$"),  # empty
    re.compile(r"^\s*[-=]{3,}\s*$"),  # separator lines
    re.compile(r"^\s*\d+%\s"),  # progress percentages
    re.compile(r"^\s*\[\s*\d+/\d+\s*\]"),  # "[3/10] Building..."
    re.compile(r"^\s*(Downloading|Fetching|Resolving|Extracting)\b.*\.{3}\s*$"),
    re.compile(r"^\s*(added|removed|changed|audited)\s+\d+\s+packages?"),
    re.compile(r"^npm (notice|warn deprecated)"),
    re.compile(r"^\s*\.{3,}\s*$"),
]


def is_noise(line: str) -> bool:
    return any(p.match(line) for p in NOISE_PATTERNS)


# -----------------------------------------------------------------------------
# Per-framework compressors
# -----------------------------------------------------------------------------

PYTEST_SUMMARY_RE = re.compile(
    r"=+ (.*?) (?:passed|failed|error|skipped|xfailed|xpassed).*=+"
)
PYTEST_FAIL_LINE_RE = re.compile(r"^FAILED (\S+)")

JEST_SUITE_RE = re.compile(r"^(?:PASS|FAIL)\s+(.+?)(?:\s|$)")

CARGO_TEST_RUN_RE = re.compile(
    r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed"
)

GO_TEST_RESULT_RE = re.compile(r"^(--- FAIL|--- PASS|FAIL|ok|PASS)\b")


def detect_framework(section_text: str) -> str:
    """Heuristic framework detection based on content."""
    head = section_text[:8000]
    if "pytest" in head.lower() or PYTEST_SUMMARY_RE.search(head):
        return "pytest"
    if re.search(r"Jest|jest --|PASS\s+\S+\.test\.", head):
        return "jest"
    if "cargo test" in head or re.search(r"running \d+ test", head) or CARGO_TEST_RUN_RE.search(head):
        return "cargo"
    if re.search(r"^go test\b|=== RUN\s+Test", head, re.M):
        return "go-test"
    if re.search(r"npm install|pnpm install|yarn install", head):
        return "npm-install"
    if re.search(r"docker (build|buildx)", head):
        return "docker-build"
    if re.search(r"webpack|vite build|tsc\b", head):
        return "js-build"
    return "generic"


# -----------------------------------------------------------------------------
# Compression strategies
# -----------------------------------------------------------------------------

@dataclass
class CompressedSection:
    name: str
    framework: str
    original_lines: int
    compressed_text: str
    has_failure: bool
    section_id: str  # for expand-on-demand


def _section_id(name: str, start: int) -> str:
    h = hashlib.md5(f"{name}:{start}".encode()).hexdigest()[:8]
    return f"s_{h}"


def compress_pytest(lines: list[str]) -> tuple[str, bool]:
    """Keep pytest failures + short summary. Drop PASSED lines."""
    has_failure = False
    kept: list[str] = []
    in_failure_block = False
    failure_depth = 0

    # pytest prints blocks like "_______ test_foo ________" for failures
    FAILURE_HEADER = re.compile(r"^_{5,}\s+\S+.*\s+_{5,}$")
    SECTION_SEP = re.compile(r"^=+\s.*\s=+$")

    for line in lines:
        if FAILURE_HEADER.match(line):
            in_failure_block = True
            has_failure = True
            kept.append(line)
            continue
        if SECTION_SEP.match(line):
            # End of failure block
            if in_failure_block:
                in_failure_block = False
            kept.append(line)
            continue
        if in_failure_block:
            kept.append(line)
            continue
        # Outside failure blocks: keep only summary-ish lines
        if PYTEST_FAIL_LINE_RE.match(line):
            has_failure = True
            kept.append(line)
        elif line.startswith("ERROR") or line.startswith("E   "):
            has_failure = True
            kept.append(line)
        elif PYTEST_SUMMARY_RE.search(line):
            kept.append(line)
        elif re.match(r"^(platform|rootdir|collected|plugins:)", line):
            kept.append(line)
        elif line_has_failure_signal(line):
            # Catches GHA `##[error]` markers and other tool-level failures
            # that happen within the same section as pytest output but
            # aren't pytest-native lines.
            has_failure = True
            kept.append(line)

    return "\n".join(kept), has_failure


def compress_jest(lines: list[str]) -> tuple[str, bool]:
    """Keep FAIL suites and their error output, drop PASS noise."""
    has_failure = False
    kept: list[str] = []
    keeping = False
    fail_indent_reset = re.compile(r"^(?:PASS|FAIL)\s")

    for line in lines:
        if line.startswith("FAIL "):
            keeping = True
            has_failure = True
            kept.append(line)
        elif line.startswith("PASS "):
            keeping = False
            # We don't emit PASS lines individually — we'll summarize at the end
        elif fail_indent_reset.match(line):
            keeping = False
        elif keeping:
            kept.append(line)
        elif re.match(r"^(Test Suites:|Tests:|Snapshots:|Time:)", line):
            kept.append(line)
        elif "●" in line or line_has_failure_signal(line):
            has_failure = True
            kept.append(line)

    # Summarize PASS count
    pass_count = sum(1 for l in lines if l.startswith("PASS "))
    if pass_count:
        kept.append(f"[+ {pass_count} test suites passed]")

    return "\n".join(kept), has_failure


def compress_cargo(lines: list[str]) -> tuple[str, bool]:
    """Cargo has compact output. Keep errors + summary + any 'error[E...]' diagnostics."""
    has_failure = False
    kept: list[str] = []
    in_error = False
    for line in lines:
        # Accept leading whitespace: trybuild prints rustc diagnostics inside
        # EXPECTED:/ACTUAL: blocks, indented by 4 spaces; without \s* these
        # error lines were invisible to the cargo compressor.
        if re.match(r"^\s*error(?:\[E\d+\])?:", line):
            has_failure = True
            in_error = True
            kept.append(line)
        elif in_error and (line.startswith("  ") or line.startswith(" -->") or not line.strip()):
            kept.append(line)
            if not line.strip():
                in_error = False
        elif "panicked at" in line or line.startswith("thread '") and "panicked" in line:
            has_failure = True
            kept.append(line)
        elif CARGO_TEST_RUN_RE.search(line):
            kept.append(line)
            if "FAILED" in line:
                has_failure = True
        elif line.startswith("failures:") or line.startswith("---- ") and "stdout" in line:
            kept.append(line)
        elif re.match(r"^\s+Compiling\s", line):
            pass  # drop "Compiling foo v1.0.0"
        elif re.match(r"^\s+Finished\s", line):
            kept.append(line)
        elif line_has_failure_signal(line):
            has_failure = True
            kept.append(line)

    return "\n".join(kept), has_failure


def compress_npm_install(lines: list[str]) -> tuple[str, bool]:
    """Replace a wall of 'added N packages' output with a 1-line summary."""
    total_lines = len(lines)
    failure_lines = [l for l in lines if line_has_failure_signal(l) or "npm ERR!" in l]
    summary_lines = [
        l for l in lines
        if re.match(r"^(added|removed|changed|audited)\s+\d+", l)
        or "vulnerabilities" in l
        or "npm warn deprecated" in l.lower()
    ]

    has_failure = len(failure_lines) > 0
    kept = failure_lines[:50]  # cap at 50 failure lines
    if summary_lines:
        kept.append(summary_lines[-1])  # keep the last "added N packages" summary
    kept.append(f"[npm install output: {total_lines} lines → compressed]")
    return "\n".join(kept), has_failure


def compress_docker_build(lines: list[str]) -> tuple[str, bool]:
    """Keep step headers + errors; drop layer caching noise."""
    has_failure = False
    kept: list[str] = []
    for line in lines:
        if re.match(r"^#\d+\s+\[", line) or re.match(r"^Step \d+/\d+", line):
            kept.append(line)
        elif "CACHED" in line and "DONE" in line:
            pass  # drop cached steps
        elif line_has_failure_signal(line) or "ERROR:" in line:
            has_failure = True
            kept.append(line)
        elif "exporting to image" in line or "writing image" in line:
            pass
        elif re.match(r"^#\d+ DONE ", line):
            pass
    return "\n".join(kept), has_failure


def compress_generic(lines: list[str], context_lines: int = 15) -> tuple[str, bool]:
    """
    Generic strategy: keep N lines of context around each failure signal,
    drop everything else, dedupe consecutive repeated lines.
    """
    has_failure = False
    failure_indices = set()
    for i, line in enumerate(lines):
        if line_has_failure_signal(line):
            has_failure = True
            for j in range(max(0, i - context_lines), min(len(lines), i + context_lines + 1)):
                failure_indices.add(j)

    if not failure_indices:
        # No failure — just dedupe noise and keep last portion
        deduped = dedupe_consecutive(lines)
        filtered = [l for l in deduped if not is_noise(l)]
        # Return tail only — start of a passing build rarely matters
        if len(filtered) > 40:
            kept = filtered[:10] + [f"[... {len(filtered) - 30} lines elided ...]"] + filtered[-20:]
        else:
            kept = filtered
        return "\n".join(kept), has_failure

    # Build output with gaps marked
    out: list[str] = []
    prev_idx = -1
    for i in sorted(failure_indices):
        if prev_idx >= 0 and i > prev_idx + 1:
            gap = i - prev_idx - 1
            if gap > 2:
                out.append(f"[... {gap} lines elided ...]")
        out.append(lines[i])
        prev_idx = i
    return "\n".join(out), has_failure


def dedupe_consecutive(lines: list[str], threshold: int = 3) -> list[str]:
    """Collapse N consecutive identical lines into '<line> [×N]'."""
    if not lines:
        return lines
    out: list[str] = []
    i = 0
    while i < len(lines):
        j = i + 1
        while j < len(lines) and lines[j] == lines[i]:
            j += 1
        count = j - i
        if count >= threshold:
            out.append(f"{lines[i]}  [×{count}]")
        else:
            out.extend(lines[i:j])
        i = j
    return out


# -----------------------------------------------------------------------------
# Top-level compress() entrypoint
# -----------------------------------------------------------------------------

FRAMEWORK_COMPRESSORS = {
    "pytest": compress_pytest,
    "jest": compress_jest,
    "cargo": compress_cargo,
    "npm-install": compress_npm_install,
    "docker-build": compress_docker_build,
}


def compress_log(raw: str) -> tuple[str, list[CompressedSection]]:
    """
    Main entry. Returns (compressed_markdown, section_metadata).
    """
    # Step 1: normalize every line
    raw_lines = raw.splitlines()
    norm_lines = [normalize_line(l) for l in raw_lines]

    # Step 2: split into GHA sections
    sections = split_sections(norm_lines)

    compressed_sections: list[CompressedSection] = []
    for sec in sections:
        section_text = "\n".join(sec.lines)
        framework = detect_framework(section_text)

        compressor = FRAMEWORK_COMPRESSORS.get(framework)
        if compressor:
            text, has_fail = compressor(sec.lines)
        else:
            text, has_fail = compress_generic(sec.lines)

        # Either way, dedupe repeated lines in the output
        deduped_lines = dedupe_consecutive(text.splitlines())
        text = "\n".join(l for l in deduped_lines if not is_noise(l))

        sid = _section_id(sec.name, sec.start_line)
        compressed_sections.append(CompressedSection(
            name=sec.name,
            framework=framework,
            original_lines=len(sec.lines),
            compressed_text=text,
            has_failure=has_fail or sec.has_error_marker,
            section_id=sid,
        ))

    # Step 3: emit final markdown
    out_parts: list[str] = []

    failures = [s for s in compressed_sections if s.has_failure]
    passing = [s for s in compressed_sections if not s.has_failure]

    out_parts.append("# CI Log (compressed)")
    out_parts.append("")
    out_parts.append(f"**Sections:** {len(compressed_sections)} total, "
                     f"{len(failures)} with failures")
    out_parts.append("")

    if failures:
        out_parts.append("## Failures")
        out_parts.append("")
        for s in failures:
            out_parts.append(f"### ❌ {s.name} `[{s.framework}]` "
                           f"(orig {s.original_lines} lines, id={s.section_id})")
            out_parts.append("```")
            out_parts.append(s.compressed_text.strip() or "(no lines retained)")
            out_parts.append("```")
            out_parts.append("")

    if passing:
        out_parts.append("## Passing sections (summarized)")
        out_parts.append("")
        for s in passing:
            body = s.compressed_text.strip()
            if body:
                out_parts.append(f"- **{s.name}** `[{s.framework}]` "
                               f"({s.original_lines} lines → {len(body.splitlines())} kept, id={s.section_id})")
            else:
                out_parts.append(f"- **{s.name}** `[{s.framework}]` ({s.original_lines} lines, elided)")

    return "\n".join(out_parts), compressed_sections
