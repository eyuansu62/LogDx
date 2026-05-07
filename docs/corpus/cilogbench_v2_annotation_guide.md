# CILogBench v2 — Annotation Guide

> Companion to [`cilogbench_v2_case_matrix.md`](cilogbench_v2_case_matrix.md)
> and [`cilogbench_v2_collection_guidelines.md`](cilogbench_v2_collection_guidelines.md).
>
> The authoritative annotation rules are in
> [`docs/annotation_guide.md`](../annotation_guide.md). That document
> applies to v2 cases unchanged. This file is a **thin overlay** that
> records v2-specific additions: the new `tags.json` fields introduced
> in §9 of the case-matrix, the new evidence-format and category
> values, and the per-category annotation tips that v1.3 collection
> never had reason to write down.
>
> Read `docs/annotation_guide.md` first. Then read this. If the two
> ever conflict, fix this overlay — `docs/annotation_guide.md` is
> protocol-stable across versions.

---

## 1. What v2 changes for the annotator

For an annotator working on a v2 case, the differences from v1.3 are:

```text
1. tags.json gets new fields (see §2 of this guide).
2. ground_truth.json is unchanged in structure but accepts a few new
   `failure_category` values and a few new `required_signal.type`
   values (see §3).
3. evidence_formats may use new tags listed in §4.
4. The hard rules from docs/annotation_guide.md (no method outputs
   visible while annotating, raw-only evidence, narrow spans, etc.)
   apply identically and are stricter for v2 — see §5.
5. New per-category annotation patterns are documented in §6.
```

There is no change to the `ground_truth.json` schema beyond the
new enum values. The line-numbering, importance levels, and
must_mention / must_not_claim fields work exactly as in v1.3.

## 2. New `tags.json` fields

After the schema bump in `cilogbench_v2_case_matrix.md` §9, every
v2 `tags.json` must include the following fields. Legacy v1.3 cases
get only `origin` filled in by migration; the other fields stay null.

```json
{
  "case_id": "java-gradle-compile-v2-001",
  "split": "v2/holdout",
  "origin": "new_v2",
  "ecosystem": "java-gradle",
  "primary_language": "java",
  "ci_provider": "github_actions",
  "repo_visibility": "public",

  "failure_category": "compile_error",
  "framework": "generic",
  "log_size_bucket": "medium",
  "signal_position": "late",
  "evidence_formats": ["compiler_diagnostic", "github_annotation"],
  "noise_profile": ["verbose_build_noise"],
  "diagnosis_difficulty": "medium",

  "multi_failure": false,
  "flaky_or_transient": false,
  "requires_repo_context": false
}
```

Field-by-field:

```text
origin
  legacy_v1_3:  case carried over from v1.3 corpus
  new_v2:       new case collected for v2

ecosystem
  See cilogbench_v2_case_matrix.md §4 for the enum. Pick the most
  specific one that fits. If a case spans multiple (e.g. a JS-Python
  monorepo), pick the ecosystem of the failing job, not the repo.
  Only use `other` if no entry in the enum is even close — and
  raise the gap on the next matrix update.

primary_language
  Free-text, lower case. Common values:
    python, javascript, typescript, rust, go, java, kotlin,
    c, cpp, ruby, scala, hcl (terraform), yaml, dockerfile,
    shell, none.
  "none" for cases where the failure is a runner/config issue with
  no source language involved (e.g. github_actions_config).

ci_provider
  github_actions (default for all v1.3 + most of v2),
  gitlab_ci, circleci, buildkite, jenkins, other.

repo_visibility
  public:   upstream run is publicly viewable
  private:  collector has permission and we keep the log
  redacted: log was lightly modified to remove secrets
            (see collection guidelines §6)
```

`framework`, `log_size_bucket`, `signal_position`,
`evidence_formats`, `noise_profile`, and `diagnosis_difficulty`
are unchanged from v1.3. Annotation tips for them live in
`docs/corpus/tagging_guide.md` and remain valid.

## 3. New `failure_category` and `required_signal.type` values

### 3.1. New `failure_category`

```text
matrix_or_monorepo_failure
  Use when:
    - The failing job is one leg of a matrix (e.g. one OS / one
      Node version / one Python version) and the other legs pass.
    - The failure is in a single project of a monorepo (nx,
      turbo, lerna, pnpm workspaces, cargo workspace) and the
      other projects build clean.
  Do NOT use:
    - When the failure happens to also be a test_assertion or
      compile_error inside a matrix leg. Use the more-specific
      category and only set matrix_or_monorepo_failure if the
      matrix structure is the *interesting* thing about the case.
  Multi_failure interaction:
    - If two matrix legs fail for unrelated reasons, set
      matrix_or_monorepo_failure AND multi_failure: true.
```

All other category values are unchanged from v1.3.

### 3.2. New `required_signal.type` values

(These are not yet locked into `ground_truth.schema.json`. Until the
schema bump, use the closest existing type and put the v2-specific
type in the signal's `notes` field.)

```text
matrix_leg
  evidence_lines point to the line that identifies which matrix
  leg is the failing one. value = the leg key.
  example: value = "node-18 / ubuntu-latest", aliases = ["18.x"]

timeout_marker
  evidence_lines point to the line where the runner emits its
  timeout / step-cancellation notice. value = the timeout reason.

oom_marker
  evidence_lines point to the OOM-killer or process-killed
  notice. value = a literal substring (e.g. "Killed" or
  "exit code 137").

package_resolver_failure
  evidence_lines point to the resolver's "no compatible version
  found" / "could not resolve" line. value = the failing package.
```

Use these only when the existing v1.3 types
(`failed_test`, `compile_error`, `exit_code`, `command`, etc.)
genuinely don't capture the signal. When in doubt, use the closest
v1.3 type — over-using new types reduces cross-version comparability.

## 4. New `evidence_formats` values

Definitions for the new entries listed in
`cilogbench_v2_case_matrix.md` §7:

```text
assertion_diff
  A test framework prints expected-vs-actual side by side.
  Examples: pytest's `-v` diff, Jest's expect diff, Go's
  go-cmp diff. Distinct from snapshot_diff in that the
  expected value is in test source, not on disk.

snapshot_diff
  A snapshot/golden test prints expected file contents vs
  actual. Examples: jest --ci --update-snapshot output, Rust's
  insta diff, txtar diffs. Annotation tip: include enough lines
  to make the snapshot identifiable; one line of "+expected" and
  "-actual" is rarely enough.

docker_build_output
  A docker / buildkit step that prints layer cache hits/misses,
  step numbers ("[6/12] RUN ..."), or BuildKit's `=> ERROR`
  markers.

package_manager_error
  pip / npm / pnpm / yarn / cargo / gradle / maven / bundler
  printing a resolver, install, or audit error. Use this even
  if the underlying cause is a network failure, because the
  *evidence shape* is package-manager-flavored.

timeout_marker
  Any line where the runner or test framework declares a
  timeout (`Error: The action 'X' has timed out after`,
  `pytest --timeout`, `go test -timeout`, etc.).

oom_marker
  Any line indicating an out-of-memory kill: `Killed`,
  `OOMKilled`, `exit code 137`, `137`, `out of memory`.

matrix_summary
  GitHub Actions-style matrix summary block at the end of a
  workflow log. Often the only place you can identify which
  matrix leg failed without scrolling.
```

A single case can carry multiple evidence_formats. Most cases will
have at least two (e.g. `traceback` + `ansi_colored_block`).

## 5. Anti-leakage during annotation (v2-stricter)

These are the same rules as `docs/annotation_guide.md` §rule-2,
emphasized for v2:

```text
1. Annotate from raw.log only. Do NOT have grep / hybrid / rtk-* /
   summary / search outputs visible while writing ground truth. If
   you have already glanced at any method's output, hand the case
   to a second annotator if possible; if not, document this in the
   case's `notes` field.
2. Do NOT use a model to draft ground_truth.json. Models trained on
   public CI logs are exactly the population the benchmark is
   measuring; using one to write the answer key leaks the answer.
3. Do NOT add aliases to required_signals to "make grep find it" or
   "make hybrid find it." Aliases are legal only when the literal
   value in raw.log differs from the natural debugger paraphrase
   (e.g. value = "tests-build::macros compile_fail_full",
   alias = "compile_fail_full").
4. Do NOT widen evidence_spans to "be safe." Narrow spans are
   correct. The evaluator computes recall over the narrow span;
   widening artificially raises every method's score.
5. Do NOT change the answer because grep happens to win. The matrix
   is descriptive of cases we collected, not curated to make a
   particular method look good or bad.
```

## 6. Per-category annotation tips

Tips are organized by `failure_category` because that's the field
the annotator chooses earliest, and where most v1.3 ambiguity lived.

### 6.1. test_assertion

```text
required signals:
  - failed_test (critical) with the canonical test name as value
  - assertion or stack_location showing the expected vs actual
  - exit_code (important)
must_mention examples:
  - test name
  - file:line of the assertion
  - one literal substring of the expected/actual diff
must_not_claim examples:
  - "compile error", "lint error", "permission denied", "timeout"
common alias use:
  - pytest: alias short test name to fully-qualified name
  - jest: alias `describe > it` form to flat test name
```

### 6.2. snapshot_or_golden_diff

```text
required signals:
  - failed_test (critical)
  - diff (critical) — type=diff, evidence_lines covers a contiguous
    + / - block from the snapshot diff
  - file (important) — pointing at the snapshot file
must_mention:
  - snapshot framework (jest / insta / txtar)
  - "snapshot" or "golden"
  - filename or file:line
must_not_claim:
  - the test logic is wrong (when it's only the snapshot that drifted)
```

### 6.3. compile_error

```text
required signals:
  - compile_error (critical) with the rustc/javac/tsc-as-compiler
    diagnostic header as value
  - file (important), line (important) — file:line of the error
must_mention:
  - error code if present (E0308, TS2322, etc.)
  - "expected ... found ..." or equivalent
  - file:line
must_not_claim:
  - runtime test failure
  - "syntax error" if it's actually a type/borrow/lifetime error
common pitfall:
  - rustc and tsc both print *many* errors per file; pick the first
    one and the directly-causing one. Do not list 12 cascading errors
    as 12 critical signals.
```

### 6.4. type_error

```text
required signals:
  - compile_error (critical) with type mismatch detail
  - file:line (important)
must_mention:
  - the two types involved (expected vs actual)
must_not_claim:
  - "the test failed" (no test ran if compilation never succeeded
    upstream)
notes:
  - mypy / tsc cases are tagged type_error if the failing step is
    type-checking only. If they're tagged as part of a build that
    also runs tests, prefer compile_error.
```

### 6.5. lint_failure

```text
required signals:
  - command (critical) — the lint command that failed
  - file:line (important) for at least one lint violation
must_mention:
  - linter (eslint, ruff, golangci-lint, ...)
  - rule id of the failing rule
must_not_claim:
  - tests failed
common alias use:
  - rule ids often appear with and without prefix; alias both
    forms (e.g. "no-unused-vars" and "@typescript-eslint/no-unused-vars")
```

### 6.6. formatting_failure

```text
required signals:
  - command (critical)
  - diff (important) — the patch the formatter would apply
must_mention:
  - formatter (prettier, black, gofmt, rustfmt)
  - "needs reformatting" or equivalent
must_not_claim:
  - lint or test failure
```

### 6.7. dependency_install

```text
required signals:
  - package (critical)
  - exit_code (important)
  - command (important) — the failing install command
must_mention:
  - package manager (pip, npm, pnpm, cargo, gradle, ...)
  - failing package name(s)
  - failing version constraint when applicable
evidence_format:
  - usually package_manager_error + ansi_colored_block
common pitfall:
  - dependency installs that fail because of a network blip should
    be tagged network_or_flaky, not dependency_install.
```

### 6.8. docker_build

```text
required signals:
  - exit_code (critical)
  - the failing build step number (use `value` field)
must_mention:
  - "Dockerfile" or "buildkit" or "docker build"
  - the failing step's RUN/COPY/ADD command (verbatim or close)
evidence_format:
  - docker_build_output
common pitfall:
  - cache-miss vs real failure. If the build only fails because the
    cache mount is unavailable, that's network_or_flaky.
```

### 6.9. github_actions_config

```text
required signals:
  - command (critical) or step_name (critical) — the misconfigured step
  - the GHA error message verbatim (value = literal substring)
must_mention:
  - "uses:" or "with:" or "run:" — which YAML key was misconfigured
  - the action name if applicable
must_not_claim:
  - the user's code is broken
notes:
  - YAML schema errors and missing-secret refs both fall here. Tag
    `permission_or_secret` only if the *runtime* permission was the
    issue, not a missing reference.
```

### 6.10. permission_or_secret

```text
required signals:
  - exception (critical) — the 401/403/permission denied line
  - command (important) — the command that needed the perm
must_mention:
  - "permission denied" or "403" or "unauthorized"
  - the resource that was denied
must_not_claim:
  - "the secret is wrong" if the log only proves the secret is missing
```

### 6.11. timeout_or_oom

```text
required signals:
  - exit_code (critical)
  - timeout_marker OR oom_marker (critical) — see §3.2
must_mention:
  - "timeout" / "timed out" / "killed" / "OOMKilled" / "exit 137"
  - the duration if printed
evidence_format:
  - timeout_marker or oom_marker
common pitfall:
  - tests that exit with non-zero but no timeout/OOM marker are
    test_assertion failures, not timeout_or_oom.
```

### 6.12. network_or_flaky

```text
required signals:
  - exception (critical) — the network error verbatim
must_mention:
  - "network", "DNS", "connection refused", "ECONNRESET", or
    "registry" — whichever is in the log
must_not_claim:
  - the user's code is broken
notes:
  - tag flaky_or_transient: true.
  - record which run was used if multiple retries exist.
```

### 6.13. matrix_or_monorepo_failure

```text
required signals:
  - matrix_leg (critical) per §3.2 — value = the failing leg key
  - one of {failed_test, compile_error, exit_code} (critical) —
    the underlying failure inside the leg
  - job_name (important)
must_mention:
  - the leg key (Node version, OS, Python version, project name)
  - the underlying failure
evidence_format:
  - matrix_summary if a matrix summary block is present
common pitfall:
  - if all matrix legs fail for the same reason, this is just the
    underlying category, not matrix_or_monorepo_failure.
```

### 6.14. multi_failure

```text
required signals:
  - one critical signal per genuine failure
  - if two failures are *causally linked* (one caused the other),
    that's a single failure with extra signals, not multi_failure.
must_mention:
  - all genuine failures
must_not_claim:
  - that one of the failures didn't happen
notes:
  - keep multi_failure cases rare. Two is plenty for v2.
```

## 7. Sanity checks before declaring a case annotated

Before renaming `ground_truth.todo.json` → `ground_truth.json`:

```text
1. Re-read root_cause.summary against raw.log. Does the log alone
   support each clause of the summary? If not, weaken the summary.
2. Walk through must_mention. For each phrase, can a reader find
   the supporting line in raw.log within 10 seconds? If not, the
   phrase is too specific.
3. Walk through must_not_claim. For each phrase, is it something a
   reasonable reader of the log might wrongly conclude? If you
   added it because "no method ever says this", remove it — that
   is method-conditioned annotation.
4. Check evidence_lines. Every (start, end) is valid against
   line_count, no overlap with another span unless intentional,
   spans are as narrow as possible.
5. Run validate_cases.py and validate_case_tags.py. Both pass.
6. Run raw signal recall. Equals 100%. If less than 100%, the
   evidence_lines or aliases are wrong.
```

Then rename the `.todo.json` files and the case is in.

## 8. When in doubt, ask

For genuinely ambiguous cases:

```text
1. Annotate as best you can.
2. Mark `diagnosis_difficulty: unclear`.
3. Add a `notes` field on tags.json explaining the ambiguity.
4. Raise it on a corpus-review thread before freezing v2.
```

The benchmark is allowed to contain ambiguous cases. It is not
allowed to contain wrongly-annotated cases that pretend to be
unambiguous.
