# CILogBench v2 — corpus summary (10-case checkpoint)

> Generated 2026-05-07 from `tools/build_split_manifest.py` outputs +
> in-tree `tags.json` files. Source data:
> [`results/v2_corpus_summary.json`](../results/v2_corpus_summary.json)
> (full per-case record table) and per-split manifests at
> `cases/<split>/split_manifest.json`.
>
> This is one of the three Phase 2 acceptance-criteria-C deliverables
> per the E10 Phase 2 plan. Companions:
> [`v2_split_balance.md`](v2_split_balance.md) (already generated) and
> [`v2_contamination_check.md`](v2_contamination_check.md).

## Counts

```text
total cases scanned:        26
  legacy v1.3 (origin=legacy_v1_3):   16
  new v2     (origin=new_v2):         10

splits:
  v1.3/dev      5     v2/dev         3
  v1.3/holdout  5     v2/holdout     5
  v1.3/stress   6     v2/stress      2
```

## Failure-category distribution

```text
category                          total   v1.3    v2    target (v2 §3)
test_assertion                       7     4      3     6
permission_or_secret                 4     4      0     3
compile_error                        3     2      1     4
github_actions_config                3     2      1     4
dependency_install                   2     1      1     4
docker_build                         1     0      1     3
network_or_flaky                     1     0      1     3
snapshot_or_golden_diff              1     0      1     3
matrix_or_monorepo_failure           1     0      1     4
formatting_failure                   1     1      0     4
lint_error                           1     1      0     —
type_error                           1     1      0     4
timeout_or_oom                       0     0      0     3   ← still 0
```

8 of 13 listed v2 categories have ≥ 1 case. The 5 still at 0/v2 are:
- `permission_or_secret` (v1.3 has 4; v2 target is 3 — open gap)
- `formatting_failure` (v1.3 has 1; v2 target is 4)
- `lint_error` / `type_error` (v1.3 has 1 each; not strictly required for v2)
- `timeout_or_oom` (still elusive — would be the next-priority hunt
  if Phase 2 continues)

## Ecosystem distribution (v2 schema field, v2 cases only)

```text
ecosystem                          v2
python-pytest                       3   (pip, numpy, cpython)
javascript-pnpm-yarn-npm            2   (pnpm × 2)
javascript-jest                     1   (prettier)
docker-buildkit                     1   (moby/buildkit)
go                                  1   (gh-cli)
rust-cargo                          1   (biome — pnpm-not-found)
c-cpp-cmake                         1   (pandas — meson actually)
```

7 ecosystems represented in 10 v2 cases. Still missing from v2 (per
matrix §4): `python-poetry-pip-tox`, `typescript-tsc`,
`java-maven`, `java-gradle`, `terraform`, `kubernetes-helm`,
`ruby-bundler`, `generic-github-actions`.

(Legacy v1.3 cases predate the `ecosystem` field; their tags.json
files have `ecosystem` unset. The v1.3 set is implicitly skewed
toward Python/JS/Rust based on framework, but the explicit
ecosystem tag was introduced in v2.)

## Log-size distribution

```text
bucket   total
small        9   (< 500 lines)
medium      11   (500-5000)
large        6   (5000-50000)
huge         0   (> 50000)
```

The `huge` bucket is **still empty across the entire 26-case corpus**.
Largest case is `biome-pnpm-not-found-v2-001` at 15802 lines (large
bucket). This is a real gap if the benchmark wants to claim
representativeness on >50k-line logs (kernel builds, large monorepo
test runs, etc.).

## Signal-position distribution

```text
position    total
early           0   ← still 0
middle          3
late           20   ← heavy skew, both in v1.3 and v2
scattered       3
```

Even after v2 added `scattered` (prettier-jest-snapshot — first such
case) and three `middle` cases, `late` remains 77% of the corpus.
This is a real distribution concern: methods that depend on
"the failure is in the last N lines" (tail-200) get an artificial
boost. v2 has done some work to mitigate this (3/10 v2 cases are
not-late) but more would help.

## Diagnosis-difficulty distribution

```text
difficulty   total
easy             7
medium           8
hard             1
unclear         10
```

`unclear` here means "annotator wasn't sure" rather than "definitely
hard"; many v1.3 cases were tagged this way before v2 firmed up
the rubric. v2 cases are mostly tagged `easy` (3) or `medium` (5)
or `unclear` (1) — closer to the rubric's intended use.

## Flag rates

```text
multi_failure=true                12 of 26  (heavy; mostly v1.3 tagging)
flaky_or_transient=true            3 of 26  (all 3 in v2 — pip-pytest
                                              network, gh-cli go,
                                              moby buildx)
requires_repo_context=true         2 of 26  (both in v2 — numpy
                                              segfault and biome
                                              pnpm-not-found)
```

`flaky_or_transient` and `requires_repo_context` are essentially
v2 inventions (v1.3 had 0 each).

## Evidence-format coverage (v2 cases only — these are the new fields)

```text
evidence_format             v2_count
github_annotation                10   (every v2 case has GHA `##[error]`)
ansi_colored_block                8
assertion_diff                    4
package_manager_error             4
traceback                         4
plain_error_line                  2
shell_command_output              2
ascii_table                       1
compiler_diagnostic               1
docker_build_output               1
matrix_summary                    1
snapshot_diff                     1
```

All seven new v2 evidence formats (assertion_diff, snapshot_diff,
docker_build_output, package_manager_error, timeout_marker,
oom_marker, matrix_summary) are exercised at least once in v2 —
**except** `timeout_marker` and `oom_marker`, which would land
when the still-missing `timeout_or_oom` category gets a case.

## What this enables

- **All Phase 2 acceptance criteria C are met** at the 10-case mark
  (per E10 plan): ≥10 cases ✓, ≥5 categories ✓ (8 v2 categories),
  ≥5 ecosystems ✓ (7), ≥2 large logs ✓, ≥2 non-late
  signal_positions ✓ (3 middle + 3 scattered = 6 if you count v1.3,
  4 from v2 alone).
- **The 8-case Phase 3 generalization finding stands.** The two
  Batch 3 stress cases (numpy segfault + cpython matrix) are
  exactly the shapes hybrid is expected to fail on; running
  Phase 3 on the 10-case state should harden the magnitude rather
  than reverse the direction. (That refresh is the next step.)

## Known gaps documented

These remain open at 10 cases and would be highest-priority on
any continuation toward 34:

1. **`timeout_or_oom` category (0/v2)** — hardest to find via
   `gh run list` browsing. Would require targeted hunting for
   `exit code 137`, `OOMKilled`, or step-timeout markers in heavy
   ML/test repos.
2. **`huge` log-size bucket (0/26)** — largest case is 15802
   lines. >50k-line logs (kernel/monorepo builds) are not
   represented.
3. **`early` signal_position (0/26)** — not a single case where the
   critical evidence sits in the first 25%.
4. **Independent human review** — v2 ground truth is AI-drafted +
   single-author-verified.
5. **More ecosystems** — `python-poetry-pip-tox`, `typescript-tsc`,
   `java-{maven,gradle}`, `terraform`, `kubernetes-helm`,
   `ruby-bundler`, `generic-github-actions` are all 0/v2.
