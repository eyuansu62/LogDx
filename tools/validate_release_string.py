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

# Files that must carry the current release version. Each entry is a
# (path, regex) pair; the regex must have ONE capture group that produces
# the version token. The expected form is the latest git tag — e.g. `v1.2`.
# CITATION.cff uses a bare "1.2.0" (no leading v); the validator strips the
# leading 'v' from the tag when comparing against bare-version files.
RELEASE_STRING_FILES = (
    # path, regex, strip-leading-v-from-tag-when-comparing?
    ("docs/index.md",         r"Current release\W+`?(v\d+\.\d+(?:\.\d+)?)`?", False),
    ("README.md",             r"Current release:\s*`?(v\d+\.\d+(?:\.\d+)?)`?", False),
    ("huggingface/README.md", r"Current release\*\*:\s*`?(v\d+\.\d+(?:\.\d+)?)`?", False),
    ("CITATION.cff",          r"^version:\s*\"(\d+\.\d+(?:\.\d+)?)\"", True),
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


def doc_release_strings(
    file_path: pathlib.Path, pattern: re.Pattern
) -> list[tuple[int, str]]:
    """Return [(line_number, matched_version), ...] for every line in
    the file whose content matches `pattern` (one capture group)."""
    matches = []
    if not file_path.exists():
        return matches
    for i, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        for m in pattern.finditer(line):
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
    for rel_path, regex_str, strip_v in RELEASE_STRING_FILES:
        fp = ROOT / rel_path
        pattern = re.compile(regex_str, re.MULTILINE)
        expected_for_file = expected.lstrip("v") if strip_v else expected
        if not fp.exists():
            sys.stderr.write(
                f"FAIL: {rel_path} listed in RELEASE_STRING_FILES but does not exist.\n"
            )
            fail = True
            continue
        matches = doc_release_strings(fp, pattern)
        if not matches:
            sys.stderr.write(
                f"FAIL: {rel_path} has no line matching r'{regex_str}'. "
                f"Either add a release-version line referencing the latest "
                f"tag ({expected_for_file}) or remove this file from "
                f"RELEASE_STRING_FILES.\n"
            )
            fail = True
            continue
        # Normalize: `v1.2` and `1.2.0` are equivalent — pad missing
        # patch component to 0 before comparing. CITATION.cff uses the
        # semver-strict `1.2.0` form while git tags use `v1.2` (no .Z
        # for major minor releases); both should round-trip equal.
        def _normalize(v: str) -> tuple[int, int, int]:
            parts = v.lstrip("v").split(".")
            while len(parts) < 3:
                parts.append("0")
            return tuple(int(p) for p in parts[:3])

        for line_no, found in matches:
            if _normalize(found) != _normalize(expected_for_file):
                sys.stderr.write(
                    f"FAIL: {rel_path}:{line_no} contains version {found} "
                    f"but the latest git tag is {expected_for_file}.\n"
                    f"  Edit to match, then commit.\n"
                )
                fail = True
            else:
                print(f"OK: {rel_path}:{line_no} matches latest tag ({expected_for_file})")

    if fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
