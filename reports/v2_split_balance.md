# CILogBench v2 — split balance check (10-case checkpoint)

> Generated 2026-05-07 from `tools/check_split_balance.py`. The full
> machine-readable output is at
> [`results/split_balance.json`](../results/split_balance.json) and a
> richer flag-by-flag dump is at
> [`reports/split_balance.md`](split_balance.md). This file is the
> short narrative companion to those raw artifacts, summarizing the
> 22 flags the tool produced.

## At a glance

```text
split        cases    flaws (matrix-vs-target)
v1.3/dev         5    no flags worth raising
v1.3/holdout     5    signal_position monoculture (5/5 late)
v1.3/stress      6    no flags worth raising
v2/dev           3    pnpm/yarn/npm not represented yet (v2/holdout has it)
v2/holdout       5    cargo + pnpm + jest distinct frameworks; clean
v2/stress        2    framework_dominance (2/2 pytest); signal_position
                      monoculture (2/2 late)
```

## Flag-by-flag interpretation

The tool emits 22 flags total. They fall into three classes:

### 1. Per-category split-mismatch flags (11 of 22)

```text
failure_category_split_mismatch:  category present in some splits but not others
```

These are mostly noise on a 26-case corpus: when a category has only
1-2 cases total, it can't be present in all 6 splits. Notable
exceptions:

- `permission_or_secret` is present in dev, holdout, stress (v1.3
  only) but missing from all v2 splits. Real gap; v2 has 0 cases
  in this category vs target 3.
- `compile_error`, `dependency_install`, `github_actions_config`
  are reasonably distributed across both v1.3 and v2.
- `matrix_or_monorepo_failure`, `network_or_flaky`,
  `snapshot_or_golden_diff`, `docker_build` are v2-only — that's
  expected, the category enum extension was introduced in v2.

### 2. Per-framework split-mismatch flags (8 of 22)

Same shape as category mismatches; same interpretation. Flags for
`pnpm`, `tsc`, `prettier`, etc. existing in only one split are not
defects; they reflect the natural distribution at small N.

### 3. The two real concerns (3 of 22)

```text
framework_dominance:
  v2/stress is 100% pytest (2 of 2 cases).

signal_position_monoculture:
  v1.3/holdout: 5 of 5 cases are 'late'.
  v2/stress:    2 of 2 cases are 'late'.
```

These are accurate diagnoses:

- **v2/stress framework dominance** is expected at 2/3 — both
  current stress cases happen to be pytest. The third v2/stress
  slot should be a different framework (e.g. cargo / docker /
  jest with a stress-bucket-fitting failure shape) to break the
  monoculture.
- **v1.3/holdout signal_position monoculture** has been carried
  over from v1.3 since the protocol freeze; not actionable here.
- **v2/stress signal_position monoculture** is more surprising
  given v2 has been deliberately seeking variety. Both stress
  cases (numpy segfault at L5462/5553 ≈ 99%, cpython tcl at
  L4022/4349 ≈ 92%) are late. Future stress additions should
  target middle/scattered/early.

## What this means for the headline finding

None of the flagged imbalances threaten the v2-generalization
result. The headline (hybrid sv1.1 −0.32, rank #1 → #6, confirmed
across both debuggers) holds because:

- The shifts that matter for that finding are *category coverage*
  and *log-size distribution*, both of which v2 has materially
  improved over v1.3.
- The remaining monocultures (holdout-late, stress-late) are
  inherited from v1.3 and v2 respectively; neither is responsible
  for the cost/quality gap.

But: the v2/stress framework dominance and signal-position
monoculture are real follow-ups for any v3 corpus or for
continued v2 collection past 10 cases.

## What this report does NOT mean

- It does not gate the protocol. Per
  `docs/corpus/cilogbench_v2_collection_guidelines.md` §3
  ("anti-bias rules during collection"), we are not adjusting
  cases to fix the matrix; the matrix is descriptive of what we
  found, not prescriptive of what must exist.
- It does not say "v2/stress is broken." 2/3 cases is a
  small-N artifact; the third case will likely break the
  framework dominance naturally.
