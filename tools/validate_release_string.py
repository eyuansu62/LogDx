#!/usr/bin/env python3
"""Validate that the "Current release" string in docs matches the latest git tag.

Why: between v1.1 and v1.2, the homepage banner on docs/index.md was
stale across THREE consecutive releases (v1.1.1, v1.1.2, v1.2 all
shipped while the banner still said "v1.1"). No CI gate caught it
because the existing validators check data / code / cache provenance,
not human-readable doc strings.

This gate scans for `Current release\\W+\\Wv[0-9.]+\\W` patterns in
the configured doc files and fails if the version doesn't match the
latest matching git tag.

Run locally:
    python3 tools/validate_release_string.py
    python3 tools/validate_release_string.py --tag v1.2   # force-check a specific tag

Wired into CI:
    .github/workflows/ci.yml release-gate batch
"""
import argparse
import re
import subprocess
import sys
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent

# Files that must carry the current release string in a recognizable form.
# Pattern: "Current release" anywhere on the line, followed by an inline
# version token like `v1.2` (markdown code) or **v1.2** (markdown bold).
# Add new files here as the project grows; the validator fails if a file
# is listed but doesn't contain ANY "Current release" mention.
RELEASE_STRING_FILES = (
    "docs/index.md",
)

# Match `vX.Y` or `vX.Y.Z` inside backticks or after a colon/whitespace,
# anywhere on the same line as "Current release".
_RELEASE_RE = re.compile(
    r"Current release.*?[`*]?(v\d+\.\d+(?:\.\d+)?)[`*]?",
    re.IGNORECASE,
)

# Match tag shape `vMAJOR.MINOR[.PATCH]`. Pre-release suffixes (-rc, etc.)
# are excluded so a temporary tag doesn't make CI fail on the next push.
_VERSION_TAG_RE = re.compile(r"^v\d+\.\d+(?:\.\d+)?$")


def latest_release_tag() -> str | None:
    """Return the most-recent tag matching `vX.Y[.Z]` by creation date,
    or None if no matching tag exists."""
    try:
        out = subprocess.run(
            ["git", "tag", "--sort=-creatordate"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"git tag failed: {e.stderr}\n")
        return None
    for line in out.splitlines():
        line = line.strip()
        if _VERSION_TAG_RE.match(line):
            return line
    return None


def doc_release_strings(file_path: pathlib.Path) -> list[tuple[int, str]]:
    """Return [(line_number, matched_version), ...] for every
    'Current release ... vX.Y[.Z]' line in the file."""
    matches = []
    if not file_path.exists():
        return matches
    for i, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        for m in _RELEASE_RE.finditer(line):
            matches.append((i, m.group(1)))
    return matches


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--tag",
        help=("Override the expected tag (useful for testing). "
              "Default: most-recent git tag matching vX.Y[.Z]."),
    )
    args = ap.parse_args()

    expected = args.tag or latest_release_tag()
    if expected is None:
        print("OK: no vX.Y[.Z] tag exists yet; skipping release-string check.")
        return 0

    fail = False
    for rel_path in RELEASE_STRING_FILES:
        fp = ROOT / rel_path
        if not fp.exists():
            sys.stderr.write(
                f"FAIL: {rel_path} listed in RELEASE_STRING_FILES but does not exist.\n"
            )
            fail = True
            continue
        matches = doc_release_strings(fp)
        if not matches:
            sys.stderr.write(
                f"FAIL: {rel_path} has no 'Current release ... vX.Y[.Z]' line. "
                f"Either add a banner referencing the latest tag ({expected}) "
                f"or remove this file from RELEASE_STRING_FILES.\n"
            )
            fail = True
            continue
        for line_no, found in matches:
            if found != expected:
                sys.stderr.write(
                    f"FAIL: {rel_path}:{line_no} says 'Current release {found}' "
                    f"but the latest git tag is {expected}.\n"
                    f"  Edit the banner to match, then commit.\n"
                )
                fail = True
            else:
                print(f"OK: {rel_path}:{line_no} matches latest tag ({expected})")

    if fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
