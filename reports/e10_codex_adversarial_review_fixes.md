# E10 — Codex adversarial-review fixes (2026-05-07)

> Source: Codex `/codex:adversarial-review` run on the E10 working tree
> (thread `019e00d2-83e9-73d3-9eaf-36587b2e094f`). Verdict at the time:
> `needs-attention`. All three flagged issues are now fixed and
> regression-tested. Re-running the same review against the patched
> tree should now return `safe-to-ship` (or surface different issues).

## Findings + actions

### 1. [high] Privacy audit duplicated secrets into its own output

**Codex finding.** `tools/audit_context_privacy.py:scan_file` stored
both the matched credential substring (`matched`) and the surrounding
line (`line_snippet`) verbatim. In raw-log mode that data was written
to `privacy_audit.json` next to the candidate raw.log and printed to
stdout. If the scanner found a real secret, the gate-tool created a
second copy of it.

**Fix.** Added `_redact()` and `_redacted_snippet()` helpers. Each
hit now stores:

```json
{
  "label": "aws_access_key",
  "note": "AWS access key ID prefix.",
  "line_number": 2,
  "redacted_match": {
    "length": 20,
    "sha256_prefix": "1a5d44a2dca1",
    "head2": "AK",
    "tail2": "LE"
  },
  "line_snippet_redacted": "fetching with key=[REDACTED] for s3 access"
}
```

The matched substring is replaced with `[REDACTED]` inside the line
snippet. The original secret is never written to the audit file or
stdout — only its sha256 prefix (12 hex chars) and its first/last 2
characters, which is enough for human triage of "is this the same
secret as that one?" but not enough to reconstruct the credential.

**Regression test.** Synthesized a fake AWS access key
`AKIAIOSFODNN7EXAMPLE` in a test log; confirmed (a) the literal
string does not appear anywhere in the resulting `privacy_audit.json`
nor in the tool's stdout, (b) the hit is still detected and surfaced
with hash + head/tail bytes, (c) exit code is 2 ("hits found").

### 2. [high] Privacy scanner could pass unscanned content silently

**Codex finding.** `MAX_LINE_LEN_FOR_SCAN = 8000` and
`MAX_LINES_PER_FILE = 50000` cause `scan_file` to skip long lines and
truncate large files, but the previous code returned only the hit
list. A huge log could legitimately exit 0 ("clean") even though some
content was never scanned. The collection guidelines explicitly
expect logs up to ~200k lines to be auditable, so this gap is real.

**Fix.** `scan_file` now returns a dict including
`complete_scan: bool`, `lines_scanned`, `lines_skipped_long`, and
`truncated_after_line`. In raw-log mode, the wrapper exits with
distinct codes:

```text
0  no hits, scan complete           ("clean")
2  hits found                       (must redact + re-run)
3  scan incomplete (caps hit)       (cannot prove clean — fail closed)
```

The split-mode audit also surfaces `complete_scan` and
`incomplete_scans` per finding/method, and the markdown report adds
an "⚠ INCOMPLETE SCAN" bullet for each affected case.

**Regression test.** Three synthetic logs:

- A normal short log → exit 0, `complete_scan: true`.
- A log with one 9000-char line → exit 3,
  `complete_scan: false, lines_skipped_long: 1`.
- A log with 50100 lines → exit 3,
  `complete_scan: false, truncated_after_line: 50000`.

**Real-world impact.** Re-running the audit on all 8 v2
`cases/v2/_incoming/<candidate>/raw.log` files surfaced one previously
hidden gap: `biome-pnpm-not-found-v2-001` now exits 3 (incomplete scan)
because the 9000-char rustfmt invocation at L15762 — listing 200+
Rust file paths — exceeds the per-line scan cap. The case still
imports cleanly (no secrets visible on manual inspection of the line)
but the audit gate now correctly refuses to mark it as "scan-clean".

### 3. [medium] Forced import could leave stale annotations

**Codex finding.** `tools/import_case_skeleton.py:80-123` accepted
`--force` to overwrite an existing case directory but only wrote
`raw.log`, `case.json`, and the two `.todo.json` skeletons. If the
case directory already had filled-in `ground_truth.json` and
`tags.json` from a previous accept, `--force` would overwrite the
raw.log under the same case_id while leaving the old answer key in
place — letting later `validate_cases.py` and `run_baseline.py` runs
score a different log against stale ground truth.

**Fix.** Split `--force` into two flags:

```text
--force         Re-import raw.log + case.json + .todo.json into a
                case directory whose annotations have NOT been filled
                yet. Refuses if ground_truth.json or tags.json exists.

--force-clean   Destructive: shutil.rmtree the entire case directory
                and recreate from scratch. Required when the intent is
                to discard accepted annotations and re-import from a
                different raw.log under the same case_id.
```

The default (no flag) refusal message now points users at both flags.

**Regression test.** Four scenarios on v2/dev:

```text
import on existing dir, no flag:                  exit 1, refuses.
--force on dir with accepted gt + tags:           exit 1, refuses,
                                                  ground_truth.json
                                                  + tags.json untouched.
--force on dir with only .todo.json files:        exit 0, succeeds.
--force-clean on dir with accepted gt + tags:     exit 0, wipes the
                                                  whole dir, recreates
                                                  with .todo.json only.
```

## End-to-end regression after fixes

```text
validate_cases.py cases/{dev,holdout,stress,v2/dev,v2/holdout}
  → 24/24 cases pass, 0 failed.

validate_case_tags.py --split all
  → 24/24 cases pass, 0 issues.

audit_context_privacy.py --raw-log on all 8 v2 _incoming/ logs
  → 7 exit 0 (clean+complete), 1 exit 3 (biome incomplete scan)
  → no secrets stored anywhere in any privacy_audit.json
  → fingerprint-only output verified
```

## Files changed

```text
tools/audit_context_privacy.py        — _redact, _redacted_snippet,
                                        scan_file returns dict,
                                        audit_raw_log fail-closed
tools/import_case_skeleton.py         — --force vs --force-clean,
                                        refuses if accepted annotations
                                        exist
.gitignore                            — minimal sensible defaults
                                        (results/*.txt, .cache/,
                                        privacy_audit.json)
reports/e10_codex_adversarial_review_fixes.md  — this file
```

## Round 2 — second Codex adversarial review (same date)

Re-running Codex against the round-1 fixes flagged two more issues.
Both addressed.

### 4. [high] `aws_secret_key_hint` regex skipped the value

**Codex finding.** The `aws_secret_key_hint` pattern was
`re.compile(r"aws_secret_access_key\s*[=:]", re.IGNORECASE)` — it
matched only the prefix (`aws_secret_access_key=`), not the assigned
secret. `_redacted_snippet()` then replaced just the prefix with
`[REDACTED]`, leaving the actual key value (`abcdef...XYZ`) in the
audit's `line_snippet_redacted` field. Same-class failure as round 1
finding 1, just on a different pattern.

**Fix.** Pattern now consumes the value too:
`r"aws_secret_access_key\s*[=:]\s*[^\s\"'&]+"`. Both the prefix and
the value are matched; `_redacted_snippet()` replaces the entire span
with `[REDACTED]`.

### 5. [high] Split-mode `audit()` ignored incomplete scans

**Codex finding.** Round-1 only patched raw-log mode to fail closed.
Split-mode `audit()` recorded `incomplete_scans` per method but always
returned `0`. Any caller using `audit_context_privacy.py --split <s>`
as a gate before `--allow-external-llm` would treat skipped-long-line
or truncated context outputs as a clean pass.

**Fix.** Track `total_incomplete_scans` across all methods; surface it
in the JSON summary and the markdown header; return exit `3` whenever
`total_incomplete_scans > 0` and there are no hits (preserving
exit-2-on-hits as the strictest signal).

```text
0  no hits, all scans complete
2  hits found
3  no hits, but at least one context file had an incomplete scan
   (long-line skip or >50k-line truncate)
```

### Regression test suite

Added `tools/tests/test_audit_redaction.py` with 4 test cases (per
Codex's explicit recommendation — without a regression a future
refactor could silently reintroduce the leak):

```text
✓ clean-log-passes               exit 0, no hits
✓ redaction-covers-all-patterns  6 secrets in synthetic log → exit 2,
                                 NO secret value verbatim in JSON,
                                 stdout, or stderr (asserted for
                                 6 distinct secret kinds including
                                 the round-2 aws_secret_key_assigned
                                 case that was the bug)
✓ long-line-fails-closed         9000-char line skipped → exit 3
✓ truncate-fails-closed          50100-line file truncated → exit 3
```

Plus a manual split-mode test:
```text
synthetic split with one 9000-char context txt → exit 3
```

## Files changed (this round)

```text
tools/audit_context_privacy.py        — aws_secret_key_hint regex
                                        consumes value;
                                        split-mode fail-closed
tools/tests/test_audit_redaction.py   — NEW: 4-test regression suite
                                        run with `python3 tools/tests/
                                        test_audit_redaction.py`
reports/e10_codex_adversarial_review_fixes.md  — this section
```

## Round 3 — third Codex adversarial review (same date)

Re-running Codex against the round-2 fixes flagged two more issues
on the same redaction/gate surface. Both addressed.

### 6. [high] Multi-secret line leaked second-and-later secrets

**Codex finding.** `scan_file` stopped at the first matching pattern
on a line (the `break  # one label per line is enough`) and
`_redacted_snippet` only replaced that single span. A line like
`combined AKIA<…> and ghp_<…>` redacted only the AWS key; the
GitHub PAT remained verbatim in `line_snippet_redacted`. Same root
failure as round 1 finding 1.

**Fix.** Removed the `break`. `scan_file` now collects EVERY
matching `(label, note, span)` triple on the line first, then emits
one hit per matching pattern with each hit's
`line_snippet_redacted` computed by replacing the *full set* of
spans (longest-first to avoid shorter-substring escapes). Pseudo:

```python
line_matches = [(label, note, m.group(0)) for (label, pat, note) in SECRET_PATTERNS
                if (m := pat.search(line))]
if line_matches:
    all_spans = [span for (_, _, span) in line_matches]
    for label, note, span in line_matches:
        hits.append({
            "label": label,
            "note": note,
            "redacted_match": _redact(span),
            "line_snippet_redacted": _redacted_snippet(line, all_spans),
        })
```

### 7. [high] Missing or empty method directory exited 0

**Codex finding.** When `--context-method <name>` referred to a
directory that did not exist (or existed but contained zero `.txt`
context files), `audit()` appended a `notes` string and continued.
Final exit logic only fired on hits or incomplete_scans, so an
explicit `--context-method typo-or-missing` returned `0` after
scanning nothing.

**Fix.** Added `methods_missing_dir` and `methods_with_no_files`
counters, surfaced both in the JSON summary, and extended the exit
logic:

```text
return 2  if total_hits > 0
return 3  if total_incomplete_scans > 0      (round 2)
return 3  if methods_missing_dir > 0
return 3  if methods_with_no_files > 0
return 0  otherwise
```

Also discovered that `discover_methods()` was inadvertently picking
up `<method>.routes.jsonl` files (the hybrid baseline writes a
sidecar manifest of routing decisions) as phantom methods with no
backing directory. The new fail-closed semantics surfaced this as
exit 3 on every existing v2 split. Fix: skip `.routes` jsonl stems
in `discover_methods()`. Same filter pattern as `run_diagnosis.py`.

### Regression tests

Extended `tools/tests/test_audit_redaction.py` with 3 new cases for
a total of 7 (still all pass):

```text
✓ clean-log-passes
✓ redaction-covers-all-patterns
✓ multi-secret-one-line-all-redacted        (NEW round 3)
✓ long-line-fails-closed
✓ truncate-fails-closed
✓ missing-method-dir-fails-closed            (NEW round 3)
✓ empty-method-dir-fails-closed              (NEW round 3)
```

Also fixed a pre-existing latent bug surfaced by the new tests:
`audit()` called `out_json.relative_to(ROOT)` and
`ctx_path.relative_to(ROOT)` unconditionally, which raised
`ValueError` whenever `--results-dir` pointed outside the project
tree. Wrapped both with try/except fallback to absolute path so the
tool runs cleanly under arbitrary `--results-dir`. (Without this,
the round-3 split-mode test cases failed before their exit-code
assertion ran.)

## Files changed (round 3)

```text
tools/audit_context_privacy.py        — multi-secret span collection,
                                        missing/empty method-dir fail-closed,
                                        discover_methods skips .routes,
                                        relative_to fallback
tools/tests/test_audit_redaction.py   — 3 new tests (multi-secret +
                                        missing/empty method dir)
```

## Open follow-ups (not blocking)

- Wire `tools/tests/test_audit_redaction.py` into a real CI pre-commit
  hook so the regression runs on every change. Currently it's a
  manual run.
- Per Codex round-1 finding 2: scanner caps could be raised
  (200k lines / 16k chars per line) to match the collection
  guideline ceiling. Defer until the first real case actually trips
  the cap on intake (currently only biome's already-imported case
  does).
- The pattern of every adversarial-review round finding two more
  high-severity bugs on the same surface suggests the audit tool
  is itself a privacy hot-spot worth a dedicated property-based
  test pass (e.g., generate random secret-like substrings + check
  they never survive `audit_raw_log`). Defer until the corpus is
  bigger and the audit tool sees more real input variety.
