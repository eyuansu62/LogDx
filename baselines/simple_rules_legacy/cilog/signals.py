"""
Signal-preservation metric.

Compression ratio alone is meaningless — 100% compression to an empty string
is "great". We also measure what fraction of DECISION-CRITICAL signals are
preserved.

We extract signals from the ORIGINAL log using conservative rules (these are
things an engineer debugging CI failure would definitely want to see), then
check how many of them appear in the compressed output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Patterns that extract identifiable "signals" from a raw log.
# Each pattern returns a set of distinctive strings we expect to see preserved.

SIGNAL_EXTRACTORS = [
    # pytest failed test names
    ("pytest_failed", re.compile(r"^FAILED (\S+)", re.M)),
    # pytest assertion markers (just the test id from the separator line)
    ("pytest_block", re.compile(r"^_{5,}\s+(\S+)\s+_{5,}$", re.M)),
    # jest/mocha failure bullets ("  ● test name")
    ("jest_bullet", re.compile(r"●\s+(.+?)$", re.M)),
    # jest FAIL file lines
    ("jest_fail_file", re.compile(r"^FAIL\s+(\S+)", re.M)),
    # Python tracebacks — extract the exception line (last line of a traceback)
    ("py_exception", re.compile(r"^(\w+(?:Error|Exception|Warning)): (.+?)$", re.M)),
    # cargo/rustc errors with code
    ("rust_error", re.compile(r"error(?:\[E\d+\])?: (.+?)$", re.M)),
    # Go test failures
    ("go_fail", re.compile(r"^--- FAIL: (\S+)", re.M)),
    # Generic exit code reports
    ("exit_code", re.compile(r"(?:exited with|exit code|Process completed with exit code)\s+(\d+)", re.M)),
    # GHA error markers
    ("gha_error", re.compile(r"##\[error\](.+?)$", re.M)),
    # Stack trace file references: path:line:col
    ("stack_location", re.compile(r"(?<!\w)([\w./\-]+\.(?:py|js|ts|rs|go|java)):(\d+)(?::\d+)?", re.M)),
]


@dataclass
class SignalReport:
    total_signals: int
    preserved_signals: int
    missing_by_type: dict[str, list[str]]
    preserved_by_type: dict[str, list[str]]

    @property
    def preservation_rate(self) -> float:
        if self.total_signals == 0:
            return 1.0
        return self.preserved_signals / self.total_signals


def extract_signals(text: str) -> dict[str, set[str]]:
    """Return a map of signal_type -> set of distinctive strings."""
    signals: dict[str, set[str]] = {}
    for name, pattern in SIGNAL_EXTRACTORS:
        matches = pattern.findall(text)
        if matches:
            # findall returns tuples for multi-group patterns, else strings
            flat = set()
            for m in matches:
                if isinstance(m, tuple):
                    # stack_location captures (filepath, line[, col]) — collapse
                    # to filepath only. The preservation probe already checks
                    # filepath-only containment; counting each (file, line) as
                    # a separate signal inflates the denominator when a single
                    # traceback hits one file 100× on different lines.
                    if name == "stack_location":
                        flat.add(m[0])
                    else:
                        flat.add(" | ".join(p for p in m if p))
                else:
                    flat.add(m)
            signals[name] = flat
    return signals


def measure_preservation(raw: str, compressed: str) -> SignalReport:
    original = extract_signals(raw)

    preserved_by_type: dict[str, list[str]] = {}
    missing_by_type: dict[str, list[str]] = {}
    total = 0
    kept = 0

    for sig_type, sig_set in original.items():
        for sig in sig_set:
            total += 1
            # For signal preservation, we check a distinctive substring is in compressed output.
            # Use the signal string directly (may be multi-part joined by " | ").
            # Split on " | " and check the first component (the most distinctive).
            probe = sig.split(" | ")[0].strip()
            if not probe:
                continue
            if probe in compressed:
                kept += 1
                preserved_by_type.setdefault(sig_type, []).append(probe)
            else:
                missing_by_type.setdefault(sig_type, []).append(probe)

    return SignalReport(
        total_signals=total,
        preserved_signals=kept,
        missing_by_type=missing_by_type,
        preserved_by_type=preserved_by_type,
    )
