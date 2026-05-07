# CILogBench v2 — split balance check (13-case checkpoint)

> Refreshed 2026-05-07 from `tools/check_split_balance.py
> --splits dev,holdout,stress,v2/dev,v2/holdout,v2/stress`. The full
> machine-readable output is at
> [`results/split_balance.json`](../results/split_balance.json) and a
> richer flag-by-flag dump is at
> [`reports/split_balance.md`](split_balance.md). This file is the
> short narrative companion to those raw artifacts, summarizing the
> 21 flags the tool produced **at the 13-case state**.
>
> The signal_position monoculture flag for v2/stress was raised at
> the 12-case state (4/4 late) and was specifically the trigger for
> Codex adversarial-review Finding 2. It has now been **closed**
> at the 13-case state by adding `airflow-precommit-tsc-middle-v2-001`
> (signal_position=middle), and the §3d 13-case Phase 3 refresh
> validated that the prior tail-winner macro lead was indeed
> sampling-inflated — see
> [`reports/e10_v2_generalization_partial.md`](e10_v2_generalization_partial.md)
> §3d.
>
> Earlier states (8-case, 10-case, 12-case) — see git history for
> this file if you need the historical decomposition.

## At a glance

```text
split        cases    flaws (matrix-vs-target)
v1.3/dev         5    no flags worth raising
v1.3/holdout     5    signal_position monoculture (5/5 late)
v1.3/stress      6    no flags worth raising
v2/dev           3    pnpm/yarn/npm not represented yet (v2/holdout has it)
v2/holdout       5    cargo + pnpm + jest distinct frameworks; clean
v2/stress        5    no monoculture flags at 13-case state
                      (was 4/4 late at 12-case; now 4 late + 1 middle
                      via airflow-precommit-tsc); framework_dominance
                      also clean (2 pytest + 1 cargo + 1 generic +
                      1 tsc = 40% pytest, under the 70% threshold)
```

## Flag-by-flag interpretation

The tool emits 22 flags total. They fall into three classes:

### 1. Per-category split-mismatch flags (12 of 22)

```text
failure_category_split_mismatch:  category present in some splits but not others
```

These are mostly noise on a 28-case corpus: when a category has only
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
- `timeout_or_oom` is now v2-only (1 case in v2/stress, 0 in v1.3
  and 0 in the other v2 splits) — added in Batch 4.

### 2. Per-framework split-mismatch flags (8 of 22)

Same shape as category mismatches; same interpretation. Flags for
`pnpm`, `tsc`, `prettier`, `cargo`, `generic` (nodejs's
tools/test.py runner — first appearance in v2/stress at 12-case),
etc., existing in only one split are not defects; they reflect the
natural distribution at small N.

### 3. The one remaining real concern (1 of 21)

```text
signal_position_monoculture:
  v1.3/holdout: 5 of 5 cases are 'late'.   ← carried over from v1.3 freeze
```

The v2/stress monoculture flag (4/4 late at 12-case) is gone at
13-case state because `airflow-precommit-tsc-middle-v2-001` was
added with signal_position=middle. The 5 v2/stress cases are now:

  - numpy segfault: L5462/5553 ≈ 99%   late
  - cpython tcl matrix: L4022/4349 ≈ 92%   late
  - rust compiletest assembly: L30430/31110 ≈ 98%   late
  - nodejs debugger timeout: L10717/10773 ≈ 99%   late
  - airflow pre-commit/tsc: L3391-3479/6496 ≈ 53%   **middle**

Phase 3 13-case refresh against this 4-late + 1-middle bucket
showed the tail-vs-grep gap shrunk substantially (Sonnet:
+0.087 → +0.023; Haiku: +0.133 → +0.110), validating the §3c
caveat that the tail-winner macro lead was sampling-inflated. The
robust 13-case takeaway is that **no single context-provider wins
across both signal positions** — see
[`reports/e10_v2_generalization_partial.md`](e10_v2_generalization_partial.md)
§3d for the full analysis.

The remaining v1.3/holdout signal_position monoculture has been
carried over from the v1.3 protocol freeze; not actionable in v2.

## What this means for the headline finding

This is where the 12-case story diverges from the 10-case story.

### Hybrid drop is robust to the imbalances

The hybrid-vs-grep finding (`hybrid sv1.1 −0.34/−0.28
cross-debugger, rank #1 → #4 unanimous`) does not rest on
v2/stress alone — it is driven by `v2/dev` (3 cases) and
`v2/holdout` (5 cases) where both signal_position and framework
distributions are diverse. The 12-case refresh §3c hybrid drop
holds even if v2/stress is excluded.

### Tail-winner sub-claim — RESOLVED at 13-case (was confounded at 12-case)

At 12-case the v2/stress 4/4-late state inflated tail's macro lead
over grep. At 13-case (airflow middle-signal added), the
hypothesis was tested directly:

- On v2/stress (4 late + 1 middle) Sonnet sees: tail 0.57, grep
  0.50, rtk-err-cat 0.40, hybrid 0.38. Tail's lead shrank from
  +0.26 (4/4-late) to +0.07 with one middle-signal case added.
- On the new airflow case alone (Sonnet): tail 0.017 (near-total
  collapse — the failure block is at L3391-3479, more than 2900
  lines from the bottom; tail-200 is structurally blind to it),
  grep 0.717 (recovers — the airflow log has structured tsc
  errors with little adjacent error chatter, so grep doesn't
  trigger the over-match collapse seen on rust+nodejs).
- v2 macro at 13-case (3 splits, Sonnet): tail 0.6343 #1, grep
  0.6117 #2 — tail still leads but only by +0.023, well within
  case-to-case variance (±0.05). On Haiku tail 0.5762 #1, grep
  0.4664 #2 — still +0.110 lead because Haiku's grep never
  recovered from rust+nodejs.

The 13-case takeaway is that **no single context-provider wins
on both signal positions** — tail beats grep on late, grep
beats tail on middle, and hybrid (which always routes to grep
or rtk-err-cat by token-count threshold) doesn't capture the
position trade-off either way. The "tail #1 / grep #2" macro
ranking survives at 13-case but the margin is now tight enough
that future stress additions could flip it.

## What this report does NOT mean

- It does not gate the protocol. Per
  `docs/corpus/cilogbench_v2_collection_guidelines.md` §3
  ("anti-bias rules during collection"), we are not adjusting
  cases to fix the matrix; the matrix is descriptive of what we
  found, not prescriptive of what must exist.
- It does not say "tail-winner is wrong." It says "tail-winner is
  partially driven by v2/stress's late-monoculture and should
  carry that caveat."

## Recommended next stress-collection priority

The 13-case middle-signal addition closed the most-leveraged
sampling gap. Remaining v2/stress collection priorities now (in
no particular order):

1. **Scattered-signal case** — matrix run where one leg's
   evidence is interleaved with passing-leg output. None present
   in v2/stress yet.
2. **Early-signal case** — build fails at compile-time and the
   rest of the log is summary chatter. None present in any
   v2 split yet (corpus-wide gap).
3. **Huge log_size_bucket (>50k lines)** — none present anywhere
   in the 28-case corpus. Currently blocked by gh CLI's stream-
   cancel ceiling (~50k lines per fetch); needs raw-archive
   download approach.
4. **`permission_or_secret` failure_category** — still 0/v2.
