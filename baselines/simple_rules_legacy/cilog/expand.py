"""
Expand-on-demand: retrieve the original untouched content of a compressed section.

Why this exists
---------------
`compress_log` emits a `section_id` anchor (e.g. `s_26ac7100`) for every
section it produces. CLAUDE.md names this the safety net that makes
aggressive compression safe: an Agent reading a compressed log that finds
the summary insufficient can ask for the original section back.

Until this module existed, `section_id` was dead code — the anchors were
emitted but no consumer could resolve them. This closes that loop.

Usage
-----
    python -m cilog.expand path/to/raw.log s_26ac7100
    python -m cilog.expand path/to/raw.log s_26ac7100 --context 5

The lookup is deterministic: we normalise and re-split the raw log exactly
as `compress_log` does, recompute each section's id, and return the one
that matches. No state is stored anywhere — the raw log is the source of
truth, the id is a pure function of `(section_name, start_line)`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compressor import _section_id, normalize_line, split_sections


def find_section(raw: str, section_id: str):
    """Locate a section by id. Returns (section, index) or (None, -1)."""
    lines = [normalize_line(l) for l in raw.splitlines()]
    sections = split_sections(lines)
    for i, sec in enumerate(sections):
        if _section_id(sec.name, sec.start_line) == section_id:
            return sec, i
    return None, -1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expand a compressed section back to its original content."
    )
    parser.add_argument("log", type=Path, help="Raw log file (as cached under results/raw/).")
    parser.add_argument("section_id", nargs="?",
                        help="Section id such as s_26ac7100. Omit when using --list.")
    parser.add_argument(
        "--context", type=int, default=0, metavar="N",
        help="Also include N lines from the section before and N from the section after.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Ignore section_id; list every section (name, id, line count) and exit.",
    )
    args = parser.parse_args()

    if not args.log.exists():
        print(f"ERROR: log not found: {args.log}", file=sys.stderr)
        return 1

    raw = args.log.read_text(encoding="utf-8", errors="replace")
    lines = [normalize_line(l) for l in raw.splitlines()]
    sections = split_sections(lines)

    if args.list:
        print(f"# {len(sections)} sections in {args.log}")
        for sec in sections:
            sid = _section_id(sec.name, sec.start_line)
            print(f"  {sid}  line {sec.start_line:>6}  ({len(sec.lines):>5} lines)  {sec.name}")
        return 0

    if not args.section_id:
        print("ERROR: section_id is required (or use --list).", file=sys.stderr)
        return 1

    match_idx = -1
    for i, sec in enumerate(sections):
        if _section_id(sec.name, sec.start_line) == args.section_id:
            match_idx = i
            break

    if match_idx < 0:
        print(f"ERROR: section_id {args.section_id!r} not found in {args.log}.", file=sys.stderr)
        print(f"       Try --list to see all section ids.", file=sys.stderr)
        return 1

    target = sections[match_idx]
    sid = _section_id(target.name, target.start_line)
    print(f"# section {sid}  name={target.name!r}  start_line={target.start_line}  "
          f"lines={len(target.lines)}")
    print()

    if args.context > 0 and match_idx > 0:
        prev = sections[match_idx - 1]
        tail = prev.lines[-args.context:]
        if tail:
            print(f"# --- {args.context} lines of context from previous section "
                  f"({prev.name!r}) ---")
            for line in tail:
                print(line)
            print("# --- /context ---")
            print()

    for line in target.lines:
        print(line)

    if args.context > 0 and match_idx < len(sections) - 1:
        nxt = sections[match_idx + 1]
        head = nxt.lines[:args.context]
        if head:
            print()
            print(f"# --- {args.context} lines of context from next section "
                  f"({nxt.name!r}) ---")
            for line in head:
                print(line)
            print("# --- /context ---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
