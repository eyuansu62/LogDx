# CILogBench v2 — Collection Guidelines

> Companion to [`cilogbench_v2_case_matrix.md`](cilogbench_v2_case_matrix.md)
> (what shape we are aiming for) and
> [`cilogbench_v2_annotation_guide.md`](cilogbench_v2_annotation_guide.md)
> (how to fill `ground_truth.json` after a case is imported).
>
> This document is the rules for **collecting** cases — i.e. finding,
> intaking, and importing CI failure logs into `cases/v2/*`. It is
> deliberately strict about anti-leakage and provenance because the
> v1.3 limitations doc already calls out small-corpus annotation bias
> as the largest threat to the benchmark's claims, and v2 is supposed
> to harden, not amplify, that.

---

## 1. What a valid v2 case is

A valid case is a single CI failure whose log gives a real-world
debugger enough information to diagnose, in principle, the true root
cause from the log alone.

Required:

```text
1. Real CI run.            Logs from an actual run, not synthetic
                           reproductions or hand-edited examples.
2. Single root cause.      Exactly one job (or matrix leg) failing
                           that we can confidently annotate. Cases
                           with multiple genuine failures get
                           multi_failure=true; do not collect cases
                           where the root cause is genuinely
                           ambiguous to the collector.
3. Public source preferred. github.com/<owner>/<repo>/actions/runs/...
                           is preferred so the failure is reproducible
                           by readers. Private logs are allowed only
                           if the collector has explicit permission
                           to publish them and they pass §6 redaction.
4. Self-contained log.     The diagnosis must be derivable from the
                           raw log we publish. Cases where you'd need
                           PR diff or repo state outside the log are
                           tagged requires_repo_context=true; we
                           accept ≤ 5 such cases in v2 to keep the
                           benchmark log-grounded.
5. Stable.                 Re-running the workflow should produce a
                           similar log and the same failure (within
                           normal CI noise). Genuinely flaky cases
                           are valid (and tagged flaky_or_transient)
                           but the collector must mark which run
                           they grabbed.
```

Reject:

```text
- Synthetic logs assembled by hand or by another model.
- Logs already memorized inside a debugger model's training set
  with high probability (e.g. the canonical pytest README failure).
- Logs where the failure is "the runner exploded" with no diagnostic
  surface; nothing to learn from these.
- Anything where you have already looked at hybrid/grep/RTK output on
  the case before deciding to import it. See §3.
```

## 2. Source rules

```text
preferred:    public GitHub Actions runs the collector encountered
              in the wild (own work, OSS contributions, dependency
              upgrades, dependabot rollouts).
acceptable:   public GitHub Actions runs found via search if the
              search query was about the failure mode, not about
              method performance (see §3).
acceptable:   public GitLab CI / CircleCI / Buildkite / Jenkins runs,
              tagged with the correct ci_provider. v2 should include
              a small number of non-GHA cases to start closing the
              CI-provider gap from v1.3 §5; treat these as bonus
              coverage, not required.
unacceptable: any log obtained from a private system without explicit
              publication permission, regardless of redaction effort.
unacceptable: logs that exist only because someone reproduced a
              failure manually. CI integrity is the point.
```

Record source provenance in `case.json`:

```json
{
  "source": "github_actions",
  "repo": "owner/repo",
  "workflow_name": "CI",
  "job_name": "test (3.11, ubuntu-latest)",
  "run_url_redacted": "https://github.com/owner/repo/actions/runs/<run_id>",
  "collected_at": "2026-05-06"
}
```

`run_url_redacted` is informational; we don't fetch from it at eval
time. If the run is later deleted upstream, the local `raw.log`
remains the canonical artifact.

## 3. Anti-leakage rules

The single biggest threat to v2's value is **selection-by-method**.
If cases are chosen because they make hybrid look good (or bad), the
benchmark stops measuring methods and starts measuring corpus design.

Rules:

1. **Decide-before-evaluate.** Decide a candidate case is in scope
   *before* running any context method on it. Once a method has been
   run, the case is committed to v2 (or rejected on §1 grounds, not
   on score grounds).
2. **No method-conditioned reverts.** Do not delete a case from v2
   because hybrid scored low on it. The corpus is what we found, not
   what we curated.
3. **No annotation-while-method-output-visible.** When writing
   `ground_truth.json`, do not have any method's output (raw, tail,
   grep, rtk-*, hybrid, summary, search) for that case open in
   another window. Annotate from `raw.log` only. This is the rule
   from `docs/annotation_guide.md` §rule-2 and it is stricter for v2
   than for v1.3.
4. **No leaderboard search.** Do not search for failures with queries
   like "where does grep miss" — those queries select for a method's
   weakness and produce a corpus that exaggerates that weakness.
   Search for failures by ecosystem, framework, or category, never
   by method.
5. **Holdout discipline.** Once a case enters `v2/holdout` or
   `v2/stress`, it does not move to `v2/dev` and it does not get
   re-annotated based on what methods produced. Movement is
   one-directional only when fixing real annotation bugs (see §10).
6. **No method-aware threshold tuning during collection.** If, while
   collecting, you discover a category where the 4k hybrid threshold
   "obviously" fails, **do not** tune the threshold. Record the
   observation as a future-experiment note (E11 candidate). v2 is a
   generalization test of v1.3's locked methods, not a re-tuning.

## 4. Pre-flight: before you import

Before running `tools/import_case_skeleton.py`:

```text
1. Confirm the source is allowed (§2).
2. Confirm anti-leakage rules (§3) — in particular, that you have
   not run any method on the log yet.
3. Check rough size: < 50 MB raw, < 200k lines.
   Larger logs are usually pathologically noisy and rarely add new
   information; flag them in #cilogbench-collection before importing.
4. Check rough category: does the failure fit one of the categories
   in cilogbench_v2_case_matrix.md §3 ?  If not, either it is "other"
   (rare and fine) or the category list itself needs an update before
   importing — discuss before adding new categories silently.
5. Check rough ecosystem: same idea against §4 of the matrix.
```

## 5. Import workflow

Use `tools/import_case_skeleton.py`:

```bash
python tools/import_case_skeleton.py \
  --split v2/holdout \
  --case-id java-gradle-compile-v2-001 \
  --raw-log /tmp/raw_java_gradle.log \
  --repo owner/repo \
  --framework gradle \
  --workflow-name CI \
  --job-name test
```

If `import_case_skeleton.py` does not yet support nested splits like
`v2/holdout`, add support before importing — do not work around it by
flat-ing the split path. The split layout is part of the protocol.

After import, the case directory should look like:

```text
cases/v2/holdout/java-gradle-compile-v2-001/
  raw.log                     # exactly the bytes you fetched
  case.json                   # filled by the importer
  ground_truth.todo.json      # placeholder, needs §6 of annotation guide
  tags.todo.json              # placeholder, needs §7 of annotation guide
```

`ground_truth.json` and `tags.json` are the renamed-after-fill
versions, written by the annotator (next document).

## 6. Privacy, secrets, and redaction

Treat every imported log as if it might contain secrets. CI logs
routinely include:

```text
- access tokens (especially in `set-output` and `actions/checkout`)
- internal hostnames
- user emails
- private package names
- internal repository paths
- signing keys / cert fingerprints
```

Required steps before committing a case:

```text
1. Run a literal grep for the standard secret prefixes:
     ghp_ ghs_ ghu_ ghr_ gho_       (GitHub PATs)
     AKIA AGPA AIDA ANPA            (AWS access keys)
     -----BEGIN                     (PEM headers)
     password=  passwd=  token=     (free-form fields)
     "Bearer "                      (auth headers)
2. Inspect the last ~200 lines manually — secrets often land in the
   "Post" cleanup steps GHA emits at the very end.
3. If a secret is found:
     - replace with the marker `[REDACTED:<kind>]`
     - record the redaction in case.json under
         "redactions": [{"line": 1234, "kind": "github_token"}]
     - re-run the validator
4. Internal hostnames / URLs that are not security-sensitive but
   identify a private system: also redact. Use [REDACTED:hostname].
5. If you cannot redact without changing the meaning of the log
   (e.g. the failure is *about* a secret being leaked), the case is
   not collectible. Reject it.
```

Cases with `repo_visibility: redacted` are allowed in v2 but flagged
in the report so readers know we are not running on the raw upstream
artifact byte-for-byte.

## 7. Naming conventions

Case IDs follow `case.schema.json`'s pattern
`^[a-z0-9][a-z0-9-]*[a-z0-9]$` and use the form:

```text
<framework-or-ecosystem>-<repo-or-tool>-<short-tag>-v2-<NNN>

examples:
  java-gradle-compile-v2-001
  go-test-flaky-v2-002
  docker-buildkit-cache-v2-001
  pytest-poetry-install-v2-003
  matrix-nx-monorepo-v2-001
```

`-v2-` in the case ID is a signal of provenance and is **not** the
authoritative tag — `tags.json: origin = new_v2` is. Two reasons to
keep `-v2-` in the ID anyway:

1. Browsing the case tree without opening tags is useful.
2. If we ever rename or re-split, the original origin is preserved
   in the ID.

Legacy v1.3 case IDs do **not** get renamed. They keep their
existing IDs (e.g. `cargo-tokio-001`) and gain only the
`origin: legacy_v1_3` tag.

## 8. Sanity checks before annotating

After import, run:

```bash
python tools/validate_cases.py cases/v2/<split>
```

Expected: only `ground_truth.todo.json` / `tags.todo.json` warnings.
No structural errors on `raw.log` size, `case.json` schema, or
`case_id` shape.

If the validator fails on schema, fix the import (do not edit the
schema at this stage).

After annotation but before any method runs:

```bash
python tools/validate_cases.py cases/v2/<split>
python tools/validate_case_tags.py --split v2/<split>
python tools/run_baseline.py --method raw --split v2/<split>
python tools/evaluate_signal_recall.py --method raw --split v2/<split>
```

Hard gate: `raw signal recall = 100%` on every case. If raw fails,
the annotation is wrong (or the schema is too strict) — fix
annotation first; do not relax the gate.

## 9. Common rejection reasons (record these)

When you reject a candidate, log it. We want to know whether v2 is
biased by what we threw away as much as by what we kept.

```text
rejection_reason ∈ {
  duplicate_of_existing_case,
  insufficient_evidence_in_log,
  cannot_be_safely_redacted,
  not_a_real_failure (e.g. cancelled),
  category_outside_target_matrix,
  ecosystem_already_at_target,
  source_unauthorized,
  flaky_unreproducible_signal
}
```

A rolling rejection log lives at
`docs/corpus/cilogbench_v2_rejections.md` (create on first rejection;
one line per rejection, no PII, no log content).

## 10. Post-freeze edits (rare and explicit)

After v2 is frozen via `tools/freeze_protocol.py`, edits to a case
are allowed only for:

```text
1. Fixing an annotation that is provably wrong (raw signal recall
   regression on a previously-passing case).
2. Redacting a missed secret.
3. Fixing a typo in case_id (extremely discouraged; prefer to
   document the typo).
```

Every post-freeze edit must:

```text
- bump the lock to a v2.0.x version (not v2.1)
- document the edit in protocols/CHANGES.md
- be re-validated end-to-end before any new method runs
- never tune a method to the edited case
```

Edits that change a method's score are not allowed unless the score
change is purely a consequence of fixing a real annotation bug. If
fixing the bug improves hybrid by 0.05 sv1.1, that is fine and is
disclosed in the report; if the bug only improves hybrid and nothing
else, that is suspicious and the fix should be reviewed by a second
reader.

## 11. Stop conditions for collection

Stop collecting when **either** of these is true:

```text
- Total v2 case count = 50, with the §9 schema extension applied
  and all rows in cilogbench_v2_case_matrix.md §3 within ±2 of
  target. Then proceed to Phase 4 (validation) of the E10 plan.

- Total v2 case count = 30 and further collection is blocked
  (time, secrets, ecosystem unavailability). Then proceed under
  the E10-partial label, with explicit per-row deficits documented
  in the E10 report.
```

Do not stop early because a particular method "is winning enough."
The point of v2 is the corpus, not the result.
