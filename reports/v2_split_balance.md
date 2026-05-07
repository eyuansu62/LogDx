# CILogBench v2 — split balance check (12-case checkpoint)

> Refreshed 2026-05-07 from `tools/check_split_balance.py
> --splits dev,holdout,stress,v2/dev,v2/holdout,v2/stress`. The full
> machine-readable output is at
> [`results/split_balance.json`](../results/split_balance.json) and a
> richer flag-by-flag dump is at
> [`reports/split_balance.md`](split_balance.md). This file is the
> short narrative companion to those raw artifacts, summarizing the
> 22 flags the tool produced **at the 12-case state**.
>
> Earlier states for this corpus (8-case 2026-05-07 and 10-case
> 2026-05-07) raised 22 flags too but with different decomposition;
> see git history for `reports/v2_split_balance.md` if you need the
> historical state.

## At a glance

```text
split        cases    flaws (matrix-vs-target)
v1.3/dev         5    no flags worth raising
v1.3/holdout     5    signal_position monoculture (5/5 late)
v1.3/stress      6    no flags worth raising
v2/dev           3    pnpm/yarn/npm not represented yet (v2/holdout has it)
v2/holdout       5    cargo + pnpm + jest distinct frameworks; clean
v2/stress        4    signal_position monoculture (4/4 late) — see §3
                      framework_dominance NO LONGER flagged
                      (was 2/2 pytest at 10-case; now 2 pytest +
                      1 cargo + 1 generic = 50% pytest, under the
                      70% threshold)
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

### 3. The two real concerns (2 of 22)

```text
signal_position_monoculture:
  v1.3/holdout: 5 of 5 cases are 'late'.
  v2/stress:    4 of 4 cases are 'late' ← worsened from 2/2 at 10-case
```

These are accurate diagnoses:

- **v1.3/holdout signal_position monoculture** has been carried
  over from v1.3 since the protocol freeze; not actionable here.
- **v2/stress signal_position monoculture is now 4/4 late** (was
  2/2 at 10-case). All four current v2/stress cases place the
  failure block at ≥92% of the log:
  - numpy segfault: L5462/5553 ≈ 99%
  - cpython tcl matrix: L4022/4349 ≈ 92%
  - rust compiletest assembly: L30430/31110 ≈ 98% (Batch 4 case 1)
  - nodejs debugger timeout: L10717/10773 ≈ 99% (Batch 4 case 2)

  This is a **genuine sampling bias of the current v2/stress
  bucket**. Future v2/stress collection MUST target middle/
  scattered/early signal_position to break the monoculture before
  any "tail wins on stress" claim can be promoted as a method
  property rather than a corpus artifact. See §4 below.

## What this means for the headline finding

This is where the 12-case story diverges from the 10-case story.

### Hybrid drop is robust to the imbalances

The hybrid-vs-grep finding (`hybrid sv1.1 −0.34/−0.28
cross-debugger, rank #1 → #4 unanimous`) does not rest on
v2/stress alone — it is driven by `v2/dev` (3 cases) and
`v2/holdout` (5 cases) where both signal_position and framework
distributions are diverse. The 12-case refresh §3c hybrid drop
holds even if v2/stress is excluded.

### Tail-winner sub-claim IS exposed to the v2/stress monoculture

The 12-case refresh produced a **second** headline shift: tail
unseats grep as the unanimous v2 winner. That sub-claim is
**partially confounded** by the 4/4-late v2/stress bucket because
tail's 200-line bottom window is structurally advantaged when
signals concentrate at the end of the log. Specifically:

- On v2/stress (4/4 late) Sonnet sees: tail 0.71, grep 0.45,
  rtk-err-cat 0.43, hybrid 0.41 — tail has a **+0.26 lead** over
  grep. This is the bucket where tail's bounded-late strength
  matters most.
- On v2/dev + v2/holdout (8 cases, mixed positions) Sonnet sees:
  tail 0.67, grep 0.66, rtk-err-cat 0.51 — tail and grep are
  **statistically tied** with a +0.01 gap.

In other words: at 12-case state, grep and tail are roughly tied
on the non-stress portion of v2; tail wins the overall macro only
because v2/stress is currently a bounded-tail-friendly bucket.
The "tail unseats grep as v2 winner" claim should therefore carry
a **caveat-after-decimal** treatment in the canonical narrative —
it's directionally correct but its magnitude is plausibly
inflated by sampling bias.

The "hybrid loses ≥0.25 sv1.1 cross-debugger and falls out of
the top tier" claim is robust; the "tail #1 unanimous on v2"
claim needs the late-bucket caveat.

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

Per §3 above, next v2/stress slot should be a case with
`signal_position` of **middle / scattered / early** — even if it
means the framework or category is repeated. Suggested targets:

1. A scattered-signal case (e.g., a matrix run where the failing
   leg's evidence is interleaved with passing-leg output).
2. A middle-signal case where the failure is followed by 30%+ of
   post-mortem output (test cleanup, coverage upload, etc.).
3. An early-signal case where the build fails at compile-time and
   the rest of the log is just summary chatter.

Adding even one such case would let us re-test the tail-winner
sub-claim against an axis where tail's structural advantage
disappears.
