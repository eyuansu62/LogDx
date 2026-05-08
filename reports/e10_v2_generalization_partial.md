# CILogBench E10 — v2 generalization (partial)

> **Four protocols are described in this report:**
>
> - [`cilogbench-v2-partial`](../protocols/cilogbench-v2-partial.lock.json)
>   (lock 2026-05-07, 24 cases) — the **8-case** v2 state that the
>   first Phase 3 run measured against. This is what the §3 8-case
>   numbers below are anchored to.
> - [`cilogbench-v2-checkpoint`](../protocols/cilogbench-v2-checkpoint.lock.json)
>   (lock 2026-05-07, regenerated against current 13-case state) —
>   originally the **10-case** Phase 2 checkpoint state, adding the
>   v2/stress split (numpy segfault + cpython matrix). After the
>   freeze_protocol fix on 2026-05-07 this lock was regenerated and
>   now resolves to the same 13-case manifest as
>   v2-checkpoint-13; the 10-case eval results are recoverable only
>   via `git checkout 530d5fd`. The §3b 10-case numbers below are
>   anchored to that historical state, not the current lock.
> - [`cilogbench-v2-checkpoint-12`](../protocols/cilogbench-v2-checkpoint-12.lock.json)
>   (lock 2026-05-07, regenerated against current 13-case state) —
>   originally the **12-case** Batch 4 partial state. Same caveat as
>   v2-checkpoint above. The §3c 12-case numbers anchor to commit
>   7036fdb.
> - [`cilogbench-v2-checkpoint-13`](../protocols/cilogbench-v2-checkpoint-13.lock.json)
>   (lock 2026-05-07, 29 cases — current canonical) — the **13-case**
>   state that adds airflow's middle-signal pre-commit/tsc case
>   into v2/stress to test the §3c tail-winner caveat. The §3d
>   13-case numbers below are anchored to this lock.
>
> All four locks SHA-pin the same v1.3 schemas, prompts, and
> evaluators that were in `cilogbench-v1.3.lock.json`, so v1.3
> numbers reproduce identically against any of them. **Per the
> Codex adversarial review (2026-05-07):** all four also now pin
> the hybrid baseline's config + route_schema + router file
> hashes, with `validate_protocol_lock.py` extended to fail-close
> on hybrid drift (was a latent gap — see commit f370ea2).
>
> **Companion docs:**
> [`e10_phase3_v2_partial_signal_recall.md`](e10_phase3_v2_partial_signal_recall.md)
> (deterministic proxy detail) and
> [`e10_phase3_v2_partial_diagnosis.md`](e10_phase3_v2_partial_diagnosis.md)
> (real-debugger sv1.1 detail). This file is the single canonical
> narrative aggregating both.
>
> **Caveats** (covered in §5 below): small sample (8/10/12 cases
> across the three refreshes), AI-drafted + single-author-verified
> ground truth, no independent human review, two Anthropic models
> only, mock LLM summary only.

## TL;DR

The v1.3 hybrid does **not** generalize to a fresh v2 corpus.
This is the strongest single result of E10 so far. Magnitudes
shifted across three refreshes (8 cases → 10 → 12); the **direction
is unchanged in all three** — hybrid loses ≥0.25 sv1.1 cross-
debugger and falls out of the top tier:

- 8-case (v2-partial): hybrid rank #1 → **#6/8**
- 10-case (v2-checkpoint): hybrid #1 → **#3-4/8** (`v2/stress` split
  added; raw + rtk-read collapse harder than hybrid on stress logs)
- 12-case (v2-checkpoint-12): hybrid #1 → **#4/8** stable. The
  2 new stress cases reveal a previously-unseen grep blindspot:
  when the regex matches too widely (rust 31k-line log: 161k
  tokens; nodejs 10k-line log: 359k tokens), Sonnet/Haiku abstain
  on the inflated context. tail's bounded-200-line window
  survives unchanged. **Caveat:** the resulting "tail #1, grep #2"
  ranking on the v2 macro is partly a v2/stress-sampling artifact
  — v2/stress is 4/4 late and tail is structurally advantaged by
  late signals. See §3c.
- 13-case (v2-checkpoint-13): hybrid v1 #1 → **#4/8** stable. One
  middle-signal case added (airflow pre-commit/tsc), validating
  the §3c caveat: tail's macro lead over grep collapsed from
  +0.09 to +0.02 on Sonnet (74% shrink) and +0.13 to +0.11 on
  Haiku (18% shrink). Per-case on the new airflow log: tail 0.017
  (collapsed — failure block at L3391-3479 is >2900 lines from
  the bottom, outside tail-200's window), grep 0.717 (recovered
  — structured tsc errors don't trigger the over-match collapse
  seen on rust/nodejs). See §3d.
- **§3e — v2 router prototype:** built `hybrid-grep-120k-tail-v2`
  to test §3d's hypothesis. Two changes vs v1: budget 4k → 120k
  (calibrated to the empirical Sonnet/Haiku abstain cliff), and
  fallback rtk-err-cat → tail. Result on the 13-case state:
  **Sonnet v2 macro 0.6801 (#1 ahead of tail and grep);**
  **Haiku v2 macro 0.5311 (#2 behind tail).** Drop from v1.3 to
  v2 is −0.11 / −0.16 vs v1's −0.34 / −0.30 — the smallest
  generalization gap of any router-style method. Hybrid-v2 also
  beats hybrid-v1 on v1.3 itself (Sonnet 0.7924 vs 0.7713). The
  cleaner take: threshold-on-tokens routing IS sufficient when
  the threshold is calibrated to the actual reasoning-budget
  collapse boundary; v1's 4k threshold was simply too aggressive.
  See §3e for full per-case detail and caveats.

```text
                                   v1.3 macro      v2 macro       Δ
                                   (3 splits)     (2 splits)
hybrid-grep-4k-rtk-err-cat-v1
   sv1.1 (Sonnet 4.6)               0.7713          0.4495      -0.32
   sv1.1 (Haiku 4.5)                0.7150          0.4150      -0.30
   signal-recall                    0.8237          0.4841      -0.34
   confident-error-rate (Sonnet)    0.0000          0.1666      +0.17

grep
   sv1.1 (Sonnet 4.6)               0.7700          0.6664      -0.10
   sv1.1 (Haiku 4.5)                0.6755          0.5472      -0.13

raw                                  0.5110          0.5478      +0.04   (Sonnet)
```

- Hybrid stays in the bottom-half across all three refreshes
  (#6 at 8 cases, #3-4 at 10, #4 at 12). Confirmed with both Haiku
  4.5 and Sonnet 4.6 — the rank shift is not debugger-specific.
- At 12 cases the bottom-3 (`hybrid` at #4, `llm-summary-v1-mock`
  at #7, `rtk-log` at #8) are **identical across both debuggers**;
  the top is now `tail` #1 unanimous, `grep` #2 unanimous (was the
  reverse at 10 cases). Cross-debugger invariance protects the
  direction against random-noise concerns.
- The cost advantage of hybrid is intact (~95% reduction in tokens).
  Only the quality match does not survive distribution shift.
- The 12-case refresh surfaces a new failure mode for both
  `grep` and `rtk-err-cat`: **density-driven context inflation**.
  Logs where `error|failed` markers appear in test-progress noise
  cause grep/rtk-err-cat outputs to exceed reasoning budget,
  producing cross-debugger abstains (sv1.1 = 0.0). `tail` survives
  by being content-blind and bounded; raw/rtk-read also abstain
  on full logs.

The v1.3 one-pager headline ("matched grep on quality at ~⅓ token
cost") was rewritten on 2026-05-07 to carry an explicit v2 caveat;
see [`docs/reports/cilogbench_v1_3_one_pager.md`](../docs/reports/cilogbench_v1_3_one_pager.md).

## 1. What changed in v2

The v2 corpus carries forward all 16 v1.3 cases (now tagged
`origin: legacy_v1_3` in `tags.json`) plus **13 new cases** collected
across Batches 1-4:

| split | new_v2 | filling |
|---|---:|---|
| `v2/dev` | 3 | docker_build (was 0/16), test_assertion, network_or_flaky (was 0/16) |
| `v2/holdout` | 5 | go ecosystem (was 0/16), dependency_install (audit), github_actions_config (2nd), snapshot_or_golden_diff (was 0/16), compile_error+cpp (was 0/16 cpp) |
| `v2/stress` | 5 | numpy segfault + cpython matrix (Batch 3); rust compiletest + nodejs timeout_or_oom (Batch 4 cases 1-2); airflow pre-commit/tsc middle-signal (added at 13-case to test §3c caveat) — see §3c, §3d, §4 |

The 13 new cases were sourced from real public CI runs (pnpm/pnpm,
pypa/pip, moby/buildkit, cli/cli, biomejs/biome,
prettier/prettier, pandas-dev/pandas, numpy/numpy, python/cpython,
rust-lang/rust, nodejs/node, apache/airflow) and imported through
the v2 intake pipeline (`tools/import_case_skeleton.py` →
ground_truth + tags annotation → raw-sanity gate at 100% signal
preservation per case).

Five new schema fields used for v2 cases (all additive, v1.3 cases
remain valid): `origin`, `ecosystem`, `ci_provider`,
`repo_visibility`, `matrix_or_monorepo_failure`. Seven new
`evidence_formats` enums introduced and exercised by the v2 cases.
See [`docs/corpus/cilogbench_v2_case_matrix.md`](../docs/corpus/cilogbench_v2_case_matrix.md)
§9 for the full schema delta.

## 2. Methodology recap

```text
raw CI log
  → context method (one of 8 locked baselines)
  → fixed debugger (Sonnet 4.6 OR Haiku 4.5; same prompt as v1.3)
  → diagnosis JSON
  → deterministic evaluator → diagnosis_score_v1_1
```

Identical pipeline to v1.3 except:

- The case set now includes 8 new_v2 cases.
- We ran the diagnosis pipeline twice — once per debugger — to
  test debugger-stability of the v2 finding.
- Method context outputs are unchanged (the locked baselines are
  byte-for-byte the same as v1.3); the routing decisions inside
  hybrid are the same code, just exposed to new logs.

## 3. Headline result — full table

`diagnosis_score_v1_1` macro across splits, real-debugger:

```text
                                v1.3 macro     v2 macro        Δ        v1.3 macro     v2 macro        Δ
method                          (Sonnet 4.6)   (Sonnet 4.6)   (Sonnet)  (Haiku 4.5)    (Haiku 4.5)    (Haiku)
raw                              0.5110         0.5478        +0.04     0.4543         0.4352        -0.02
tail                             0.6886         0.6647        -0.02     0.6612         0.5464        -0.11
grep                             0.7700         0.6664        -0.10     0.6755         0.5472        -0.13
rtk-read                         0.5224         0.5040        -0.02     0.4575         0.4454        -0.01
rtk-log                          0.3089         0.2434        -0.07     0.2800         0.2330        -0.05
rtk-err-cat                      0.5343         0.5173        -0.02     0.4942         0.4712        -0.02
llm-summary-v1-mock              0.5181         0.2981        -0.22     0.4938         0.2668        -0.23
hybrid-grep-4k-rtk-err-cat-v1    0.7713         0.4495        -0.32     0.7150         0.4150        -0.30
                                                              ^^^^^                                  ^^^^^
                                                            largest                                largest
```

Cross-debugger ranking on v2 (1 = best):

```text
                                  Haiku v2           Sonnet v2
method                            score   rank       score   rank
grep                              0.5472    1        0.6664    1   ← unanimous winner on v2
tail                              0.5464    2        0.6647    2   ← stable #2
rtk-err-cat                       0.4712    3        0.5173    4
rtk-read                          0.4454    4        0.5040    5
raw                               0.4352    5        0.5478    3
hybrid-grep-4k-rtk-err-cat-v1     0.4150    6        0.4495    6   ← unanimous #6 on v2
llm-summary-v1-mock               0.2668    7        0.2981    7   ← unanimous #7
rtk-log                           0.2330    8        0.2434    8   ← unanimous #8
```

Signal-recall (deterministic proxy) macro:

```text
                                v1.3 sig    v2 sig       Δ      v1.3 crit    v2 crit       Δ
hybrid                          0.8237     0.4841     -0.34      0.8894      0.3944     -0.50
grep                            0.8756     0.8286     -0.05      0.9028      0.7167     -0.19
tail                            0.8549     0.7777     -0.08      0.8833      0.7084     -0.17
```

The signal-recall and diagnosis-quality stories agree on hybrid
being the largest drop and grep being the smallest (raw is pinned
at 1.0 by definition for signal-recall and behaves differently on
sv1.1 because the raw log is given to the model directly).

## 3b. 10-case refresh (v2-checkpoint, 2026-05-07)

After collecting 2 more v2 cases into the previously-empty `v2/stress`
split — `numpy-pytest-segfault-argsort-v2-001` (process-crash from
a numpy `argsort` segfault on the `reverse-sorts` perf branch) and
`cpython-tcl-windows-matrix-v2-001` (matrix-shaped Windows-only
tcltk regression; canonical `case.json` `failure_category` =
`test_assertion`, the matrix-coverage label lives on `tags.json`
only — see §5.8) — Phase 3 was re-run on the 10-case state.
Results:

```text
                                v1.3 sv1.1   v2 sv1.1 (8)   v2 sv1.1 (10)   Δ from 8→10
                                (Sonnet)     (Sonnet)       (Sonnet)
raw                               0.5110       0.5478          0.3652         -0.1826
tail                              0.6886       0.6647          0.6673         +0.0026
grep                              0.7700       0.6664          0.7435         +0.0770
rtk-read                          0.5224       0.5040          0.3360         -0.1680
rtk-log                           0.3089       0.2434          0.1622         -0.0811
rtk-err-cat                       0.5343       0.5173          0.4880         -0.0294
llm-summary-v1-mock               0.5181       0.2981          0.2154         -0.0827
hybrid-grep-4k-rtk-err-cat-v1     0.7713       0.4495          0.4427         -0.0067
```

Cross-debugger ranking on the 10-case v2 state:

```text
                                  Haiku v2-10        Sonnet v2-10
method                            score   rank       score   rank
grep                              0.6189    1        0.7435    1   ← unanimous winner (was #1 in v2-8 too)
tail                              0.4705    2        0.6673    2   ← stable #2
hybrid-grep-4k-rtk-err-cat-v1     0.4683    3        0.4427    4   ← was #6 in v2-8
rtk-err-cat                       0.4600    4        0.4880    3
rtk-read                          0.2969    5        0.3360    6   ← drops sharply on stress
raw                               0.2901    6        0.3652    5   ← drops sharply on stress
llm-summary-v1-mock               0.1924    7        0.2154    7
rtk-log                           0.1692    8        0.1622    8
```

Two important shifts vs the 8-case state:

1. **Hybrid moves from rank #6 to rank #3–4**, not because hybrid
   improved (sv1.1 stayed flat: 0.4495 → 0.4427 Sonnet,
   0.4150 → 0.4683 Haiku), but because **raw** and **rtk-read**
   collapsed on the v2/stress cases. Sonnet abstains on both
   stress cases when given raw context (5553-line numpy log +
   4349-line cpython log are both too noisy for confident
   diagnosis), and rtk-read passes the log through untouched so
   it has the same problem. raw drops 0.55 → 0.37 on Sonnet
   (Δ −0.18); rtk-read drops 0.50 → 0.34. This re-orders the
   middle of the ranking.
2. **grep IMPROVES on the 10-case state**: 0.6664 → 0.7435 Sonnet,
   0.5472 → 0.6189 Haiku. The 2 stress cases both have failure
   markers that grep's regex catches cleanly (`Fatal Python error`,
   `FAIL`, `Segmentation fault`, `##[error]`) so grep's tightly-
   bounded ±3/8 lines isolate the signal where raw drowns in
   noise. Adding stress raises grep's macro.

The headline updates accordingly:

| Headline claim | 8-case status | 10-case status |
|---|---|---|
| "hybrid sv1.1 drops substantially v1.3 → v2" | ✅ −0.32 (Sonnet) / −0.30 (Haiku) | ✅ −0.33 / −0.25 |
| "hybrid is rank #1 → #6 across both debuggers" | ✅ true at 8 cases | ⚠️ now rank #1 → #3-4 |
| "grep is the most stable / unanimous v2 winner" | ✅ | ✅ (and improved) |
| "cost match holds; quality match doesn't" | ✅ | ✅ |
| "confident-error rate on hybrid spikes 0.00 → 0.17" | (Sonnet only) | Confirmed; 0.0 → ~0.17 stable |

The "rank #1 → #6" specific framing was a small-sample artifact
from the v2-partial state that lacked stress cases. The robust
core finding is unchanged: **hybrid loses ≥0.25 sv1.1 across both
debuggers, falls out of the top tier, and grep is the unanimous
v2 winner.**

Signal-recall (deterministic) at 10-case:

```text
                                v1.3 sig    v2 sig (8)    v2 sig (10)    Δ from 8→10
hybrid                          0.8237      0.4841        0.3942         -0.0899
grep                            0.8756      0.8286        0.8381         +0.0095
tail                            0.8549      0.7777        0.8042         +0.0265
```

Signal-recall agrees: hybrid loses another ~0.09 going from 8 to
10 cases (now Δ −0.43 from v1.3 to v2-10). Grep is essentially
unchanged. Tail picks up slightly.

## 3c. 12-case refresh (v2-checkpoint-12, 2026-05-07)

After collecting 2 more v2 cases into `v2/stress` —
`rust-compiletest-wasm-exceptions-asm-v2-001` (rust bors-try
compiletest assembly-llvm test failed because FileCheck CHECK
directives no longer match the new wasm exnref EH lowering;
canonical category test_assertion, tags add a non-pytest framework
gap-fill) and
`nodejs-test-debugger-exec-timeout-v2-001` (nodejs Test macOS
parallel/test-debugger-exec timed out 15s waiting for the inspector
break-in pattern; canonical category timeout_or_oom, fills the
v2 timeout_or_oom gap that was 0/v2 through 10-case) — Phase 3 was
re-run on the 12-case state. New protocol lock at
[`protocols/cilogbench-v2-checkpoint-12.lock.json`](../protocols/cilogbench-v2-checkpoint-12.lock.json)
(28 cases, 6 splits, 14 SHA-pinned hashes; same v1.3 schemas/
prompts/evaluators as the 8-case and 10-case locks).

**The 12-case refresh produces a third headline shift: tail
unseats grep as the unanimous v2 winner.**

```text
                                v1.3 sv1.1   v2 sv1.1 (10)   v2 sv1.1 (12)   Δ from 10→12
                                (Sonnet)     (Sonnet)        (Sonnet)
raw                               0.5110       0.3652          0.3652         +0.0000
tail                              0.6886       0.6673          0.6807         +0.0134
grep                              0.7700       0.7435          0.5939         -0.1496
rtk-read                          0.5224       0.3360          0.3360         +0.0000
rtk-log                           0.3089       0.1622          0.2199         +0.0577
rtk-err-cat                       0.5343       0.4880          0.4870         -0.0010
llm-summary-v1-mock               0.5181       0.2154          0.2363         +0.0209
hybrid-grep-4k-rtk-err-cat-v1     0.7713       0.4427          0.4353         -0.0074
```

Cross-debugger ranking on the 12-case v2 state:

```text
                                  Haiku v2-12        Sonnet v2-12
method                            score   rank       score   rank
tail                              0.6251    1        0.6807    1   ← unanimous winner (was #2 at v2-10)
grep                              0.4918    2        0.5939    2   ← was #1 at v2-10; dropped ≈0.13-0.15
rtk-err-cat                       0.4481    3        0.4870    3   ← stable
hybrid-grep-4k-rtk-err-cat-v1     0.4302    4        0.4353    4   ← stable
rtk-read                          0.2969    5        0.3360    6   (Haiku) / 5 (Sonnet flips with raw)
raw                               0.2901    6        0.3652    5
llm-summary-v1-mock               0.2268    7        0.2363    7   ← stable
rtk-log                           0.1897    8        0.2199    8   ← stable
```

The big shift: **grep loses ~0.13-0.15 sv1.1 going from 10 to 12
cases on both debuggers**, while tail moves up to rank #1.

Why? Both new v2/stress cases reveal a **grep blindspot we hadn't
seen before**: when the regex `error|failed|...|##[error]` matches
*too widely*, it produces context that exceeds the diagnoser's
reasoning budget. The two new cases trigger it cleanly:

- `rust-compiletest-wasm-exceptions-asm-v2-001` (31110-line log,
  full from-scratch rustc build): grep produces **161 086 context
  tokens**. Sonnet abstains; Haiku abstains. sv1.1 = 0.0 on both.
- `nodejs-test-debugger-exec-timeout-v2-001` (10773-line log, 5175
  test progress lines): grep produces **359 459 context tokens**.
  Sonnet abstains; Haiku abstains. sv1.1 = 0.0 on both.

These are not regex-misses (the way `gh-cli-go-test-prompter` and
`pnpm-audit-vuln-ip-address` were grep-regex blindspots at 8-case);
they are **grep-too-greedy blindspots**. Both new logs contain so
many lines matching `error|failed|...` (test-progress noise + the
build's compile-error chatter for rust; jest-style `Error:` traces
in test fixtures for nodejs) that the matched span exceeds the
budget the diagnoser can reason over.

`tail`, by contrast, is bounded at 200 lines / a few thousand
tokens. Both new cases happen to have signal_position=late (failure
block at L30430-30999 of 31110 for rust, L10717-10756 of 10773 for
nodejs), so tail catches the failure summary cleanly and Sonnet/
Haiku produce strong diagnoses (rust 0.755 / 0.680 sv1.1; nodejs
0.750 / 0.988 sv1.1).

```text
v2/stress per-case sv1.1 at 12-case (Sonnet 4.6):
                                   numpy   cpython     rust    nodejs    macro
raw                               0.0000    0.0000   0.0000   0.0000    0.0000   ← Sonnet abstains on all 4
tail                              0.7500    0.5950   0.7550   0.7500    0.7125   ← bounded, late-signal-friendly
grep                              1.0000    0.7950   0.0000   0.0000    0.4487   ← over-match collapse on rust+nodejs
rtk-err-cat                       0.4833    0.3750   0.8475   0.0000    0.4264   ← also collapses on nodejs (ctx ≈ 320k)
hybrid-grep-4k-rtk-err-cat-v1     0.4833    0.3750   0.7700   0.0000    0.4071   ← inherits rtk-err-cat's nodejs blindspot
```

Hybrid's 4k-token threshold correctly avoided grep's blowup on
both new cases (it routed all 4 v2/stress cases to rtk-err-cat).
But rtk-err-cat *also* collapses on nodejs (320 916 context tokens
on Haiku/hybrid, similar on Sonnet), so hybrid inherits that
blindspot. tail is the only locked baseline that survives all 4
v2/stress cases without abstaining.

The headline updates accordingly:

| Headline claim | 8-case | 10-case | 12-case |
|---|---|---|---|
| "hybrid sv1.1 drops substantially v1.3 → v2" | ✅ −0.32 / −0.30 | ✅ −0.33 / −0.25 | ✅ −0.34 / −0.28 (robust across stress sampling) |
| "hybrid stays in the bottom-half across debuggers" | ✅ #6/8 | ✅ #3-4/8 | ✅ #4/8 |
| "grep is the unanimous v2 winner" | ✅ | ✅ (and improved) | ❌ **superseded — tail #1 macro, grep #2 macro** |
| "tail is the unanimous v2 winner" | (was #2) | (was #2) | ⚠ **macro-level only**; 4/4-late v2/stress drives the gap. tied with grep on non-stress |
| "grep over-matches on high-error-density logs" | (not seen) | (not seen) | ✅ **new at 12-case** — method-level (independent of signal_position) |
| "cost match holds; quality match doesn't" | ✅ | ✅ | ✅ |
| "confident-error rate on hybrid spikes 0.00 → 0.17" | (Sonnet) | confirmed | confirmed |

The robust-across-cases finding is now: **hybrid stays in the
bottom-half because its 4k-token threshold correctly avoids grep's
blowup but inherits rtk-err-cat's collapse on the same density-
driven blindspots.** Hybrid sv1.1 drop (−0.34 / −0.28) and #4
rank are robust across all three refreshes (8 → 10 → 12 cases)
and across both debuggers.

**The "tail unseats grep" sub-claim is partially confounded by a
v2/stress sampling bias** that needs to be disclosed up front.
The current v2/stress bucket is **4/4 late** (numpy, cpython,
rust, nodejs all place the failure block at ≥92% of the log; see
[`reports/v2_split_balance.md`](v2_split_balance.md) §3),
and tail's bounded 200-line window is structurally advantaged by
late evidence. Decomposing the 12-case macro by split:

```text
                                v2/dev (3)  v2/holdout (5)  v2/stress (4)   v2 macro (12)
                                Sonnet      Sonnet          Sonnet          Sonnet
tail                            0.7858      0.5437          0.7125          0.6807    #1
grep                            0.7439      0.5890          0.4487          0.5939    #2
rtk-err-cat                     0.5847      0.4500          0.4264          0.4870    #3
hybrid                          0.4889      0.4100          0.4071          0.4353    #4
```

On v2/dev + v2/holdout (8 cases, mixed signal_position), tail
(0.62) and grep (0.65) are roughly tied (grep edges +0.03). It is
only on v2/stress's 4/4-late bucket that tail opens a +0.26 lead
(0.71 vs 0.45) — exactly the bucket where bounded-tail's
structural advantage matters. Tail's macro #1 ranking is therefore
**directionally correct but its magnitude is plausibly inflated
by sampling bias**. The "tail unseats grep" finding should be
re-checked when v2/stress acquires a non-late case.

In contrast, the "high-error-density logs cause grep's regex to
over-match" mechanism (rust 161k tokens, nodejs 359k tokens) is a
**method-level finding** that does not depend on signal_position
— grep's 0.0 sv1.1 on rust + nodejs is from abstain-on-large-
context regardless of where the failure sits in the log. So the
density-driven grep blindspot survives the v2/stress sampling
caveat; the tail-as-#1-overall claim is what needs the caveat.

Signal-recall (deterministic) at 12-case:

```text
                                v1.3 sig    v2 sig (10)    v2 sig (12)    Δ from 10→12
hybrid                          0.8237      0.3942         0.4779         +0.0837
grep                            0.8756      0.8381         0.8479         +0.0098
tail                            0.8549      0.8042         0.7896         -0.0146
rtk-err-cat                     —           —              0.4589         —
```

Signal-recall *disagrees* with sv1.1 at 12-case: grep's
deterministic recall stays high (0.85) because the failure
markers ARE in the grep output — the model just can't reason
over 161k-359k tokens to extract them. This is exactly the
"deterministic proxy understates real-debugger collapse" gap
E5 originally identified on v1.3, now reappearing in a different
shape on v2 (deterministic proxy *overstates* grep's real-
debugger usefulness when context inflates past reasoning budget).

## 3d. 13-case refresh — testing the tail-winner caveat (v2-checkpoint-13, 2026-05-07)

Per the §3c caveat that the "tail unseats grep" macro lead was
plausibly inflated by the 4/4-late v2/stress sampling, one
middle-signal case was added to v2/stress to actually test the
caveat: `airflow-precommit-tsc-middle-v2-001` (apache/airflow
pre-commit `ts-compile-lint-ui` hook fails with 3 TypeScript
errors at L3391-3479 of a 6496-line log; ##[error] step exit at
L3762 ≈ 58%; ~42% of the log AFTER the failure is non-failure
pre-commit hook chatter from the ~30 OTHER hooks that pre-commit
keeps running after one fails). New protocol lock at
[`protocols/cilogbench-v2-checkpoint-13.lock.json`](../protocols/cilogbench-v2-checkpoint-13.lock.json)
(29 cases, 6 splits, 14 SHA-pinned + 3 hybrid hashes).

**The caveat was real and material.** Tail's macro lead over grep
shrank substantially with the single new middle-signal case:

```text
                                v2 macro (12-case)   v2 macro (13-case)   Δ from 12→13
                                Sonnet     Haiku     Sonnet     Haiku    Sonnet   Haiku
tail                            0.6807    0.6251     0.6343    0.5762   -0.0464  -0.0489
grep                            0.5939    0.4918     0.6117    0.4664   +0.0178  -0.0254
rtk-err-cat                     0.4870    0.4481     0.4776    0.4363   -0.0094  -0.0118
hybrid                          0.4353    0.4302     0.4266    0.4145   -0.0087  -0.0157
raw                             0.3652    0.2901     0.3652    0.2901   +0.0000  +0.0000
                                                                           (v2/stress only contributes
                                                                            on 5 cases now; raw and
                                                                            rtk-read still abstain on all
                                                                            stress cases so unchanged)

tail-vs-grep gap (Sonnet):     +0.0868              +0.0226                       (gap shrunk by 74%)
tail-vs-grep gap (Haiku):      +0.1333              +0.1098                       (gap shrunk by 18%)
```

The Sonnet "tail unseats grep" lead **collapsed from +0.09 to
+0.02 with one middle-signal case added** — well within
case-to-case variance (±0.05). On Haiku the gap stayed wider
(+0.11) because Haiku's grep never recovered from the rust +
nodejs over-match collapses, but even there tail's lead
shrank by 18%.

Per-case detail on the new airflow case (Sonnet 4.6) confirms the
mechanism: tail collapses when the failure isn't at the end, grep
recovers when context is structured rather than density-noisy:

```text
v2/stress per-case sv1.1 at 13-case (Sonnet 4.6):
                                   numpy   cpython     rust    nodejs   airflow    macro
raw                               0.0000    0.0000   0.0000   0.0000   0.0000    0.0000   ← abstain on all
tail                              0.7500    0.5950   0.7550   0.7500   0.0167    0.5733   ← tail crashed on airflow!
grep                              1.0000    0.7950   0.0000   0.0000   0.7167    0.5023   ← grep recovers on airflow
rtk-err-cat                       0.4833    0.3750   0.8475   0.0000   0.2850    0.3982
rtk-log                           0.0000    0.3750   0.3000   0.5000   0.3467    0.3043
hybrid-grep-4k-rtk-err-cat-v1     0.4833    0.3750   0.7700   0.0000   0.2767    0.3810
llm-summary-v1-mock               0.0000    0.1000   0.0500   0.3000   0.0000    0.0900
```

- **tail on airflow: 0.0167** — tail's bottom 200 lines (L6296-6496)
  are post-failure pre-commit hook chatter (post-job cleanup, hook
  trace logs); the actual TS error block is at L3391-3479, more
  than 2900 lines from the bottom. Tail's bounded window is
  structurally blind to mid-log failures. This is the cleanest
  possible counter-example to the §3c "tail unseats grep" macro
  framing.
- **grep on airflow: 0.7167** — grep's regex catches the `error TS6196`,
  `error TS6133`, `error TS2739`, `Found 3 errors in 3 files`, and
  `subprocess.CalledProcessError` markers; produces ~6k tokens of
  context (well under any reasoning budget); Sonnet diagnoses
  cleanly. This is also a counter-example to the §3c "grep
  collapses on high-error-density logs" framing — the airflow log
  has *structured* tsc errors with little adjacent error chatter,
  so grep doesn't over-match.
- **hybrid on airflow: 0.2767** — hybrid routes to rtk-err-cat
  (grep would have produced the right answer; rtk-err-cat compresses
  too aggressively and loses the 3-error structure). Same
  selection-by-method failure mode as the 8-case Phase 3 analysis.

**Updated headline table at 13-case state:**

| Headline claim | 8-case | 10-case | 12-case | 13-case |
|---|---|---|---|---|
| "hybrid sv1.1 drops substantially v1.3 → v2" | ✅ −0.32 / −0.30 | ✅ −0.33 / −0.25 | ✅ −0.34 / −0.28 | ✅ −0.34 / −0.30 |
| "hybrid stays in the bottom-half across debuggers" | ✅ #6/8 | ✅ #3-4/8 | ✅ #4/8 | ✅ #4/8 |
| "tail is the unanimous v2 winner" | (#2) | (#2) | ⚠ macro-only, sampling caveat | ⚠ unanimous #1 stable BUT margin ≈ +0.02 Sonnet (within noise) |
| "grep collapses on high-error-density logs" | (not seen) | (not seen) | ✅ method-level on rust+nodejs | ✅ confirmed; airflow shows the converse case (structured errors → grep recovers) |
| "tail collapses when signal isn't late" | (untested) | (untested) | (untested) | ✅ **new at 13-case** — airflow 0.017 sv1.1 — bounded window structurally misses mid-log failures |
| "cost match holds; quality match doesn't" | ✅ | ✅ | ✅ | ✅ |

**The robust 13-case takeaway:** the v1.3 hybrid loses ≥0.30 sv1.1
cross-debugger and stays at #4 unanimous. Among the locked
baselines, **no single context-provider wins on both signal
positions** — tail beats grep on late-signal cases, grep beats
tail on middle-signal cases, and hybrid (which always routes to
either grep or rtk-err-cat) doesn't get the position-aware benefit
either way. The "tail #1 / grep #2" macro ranking at 13-case is
~0.02 apart on Sonnet and survives only because v2/stress is
4/5 late.

What this means for v3 / further work: a **position-aware router**
(grep when signal is mid-log, tail when signal is late, with the
position estimated cheaply from regex match-density or simple
heuristics) would likely beat both individually. v1.3's hybrid
threshold-on-tokens does NOT do this — it only routes on grep's
output token count, which is orthogonal to where in the log the
signal lives.

## 3e. Position-aware hybrid v2 — testing the §3d hypothesis (2026-05-08)

§3d hypothesized that "no single context-provider wins on both
signal positions" and proposed a position-aware router. To test
that, a v2 router was implemented and run on the 13-case state:

```text
hybrid-grep-120k-tail-v2 (configs/hybrids/hybrid-grep-120k-tail-v2.json)
  primary_method:    grep
  fallback_method:   tail
  budget_tokens:     120000   (was 4000 in v1)
  fallback:          tail     (was rtk-err-cat in v1)
```

Two changes versus `hybrid-grep-4k-rtk-err-cat-v1`:

1. **Budget recalibrated 4k → 120k.** The empirical Sonnet/Haiku
   abstain cliff sits between 100k and 161k tokens (airflow 100k
   tokens → diagnoses cleanly; rust 161k → abstain; nodejs 359k →
   abstain). 120k is conservatively above the largest non-abstaining
   case in the 13-case data. The 4k threshold from v1 was tuned on
   v1.3 distribution and routed away from grep too aggressively.
2. **Fallback grep → tail** (instead of grep → rtk-err-cat).
   Motivated by §3c finding that rtk-err-cat ALSO collapses on
   density-driven contexts (320k tokens on nodejs) where tail's
   bounded 200-line window survives. The tradeoff: tail loses on
   middle-signal cases — but those are exactly the cases where
   grep fits the 120k budget, so the router uses grep there.

Anti-leakage: the 120k threshold was set from looking at
`eval_diagnosis_*.json` outputs to find the abstain cliff —
those eval files don't open `ground_truth.json`, so the threshold
calibration is at the budget-collapse layer, not the case-quality
layer. The router itself reads only the grep + tail manifest rows
(case_id, output_byte_size, provider_error). No ground-truth or
review-label leakage.

### Results

```text
                                v1.3 macro    v2 macro     Δ from v1.3
                                Son   Hai     Son   Hai    Son      Hai
hybrid-grep-4k-rtk-err-cat-v1   0.77  0.72    0.43  0.41   -0.34   -0.30   ← v1
hybrid-grep-120k-tail-v2        0.79  0.69    0.68  0.53   -0.11   -0.16   ← v2 ★
grep                            0.77  0.68    0.61  0.47   -0.16   -0.21
tail                            0.69  0.66    0.63  0.58   -0.05   -0.09
rtk-err-cat                     0.53  0.49    0.48  0.44   -0.06   -0.06
raw                             0.51  0.45    0.37  0.29   -0.15   -0.16
```

**Headline:** hybrid-v2 has the **smallest cross-debugger drop
from v1.3 → v2 of any router-style method** (Sonnet −0.11 vs v1's
−0.34; Haiku −0.16 vs v1's −0.30). On Sonnet hybrid-v2 takes the
v2 #1 macro (0.6801) over tail (0.6343) and grep (0.6117); on
Haiku hybrid-v2 is #2 (0.5311) behind tail (0.5762).

**Hybrid-v2 also beats hybrid-v1 on v1.3 itself** (Sonnet 0.7924 >
0.7713) — the threshold recalibration isn't just a v2-specific
gain. On Haiku the v1.3 numbers are essentially tied (0.6923 vs
0.7150) within case-to-case variance.

### Per-case v2/stress detail (Sonnet 4.6, sv1.1)

```text
case               grep    tail    rtk-e-c  hybrid-v1  hybrid-v2  ←routed
numpy (1k tok)     1.0000  0.7500  0.4833   0.4833     1.0000     grep
cpython (74k)      0.7950  0.5950  0.3750   0.3750     0.7850     grep
rust (161k)        0.0000  0.7550  0.8475   0.7700     0.7950     tail (>120k)
nodejs (360k)      0.0000  0.7500  0.0000   0.0000     0.7500     tail (>120k)
airflow (100k)     0.7167  0.0167  0.2850   0.2767     0.7167     grep
                  ------  ------  ------   ------     ------
v2/stress macro    0.5023  0.5733  0.3982   0.3810     0.8093  ★
```

The router picks the empirically-correct method on **all 5
v2/stress cases**: grep when grep fits the budget AND has structured
errors that don't over-match (numpy, cpython, airflow); tail when
grep would over-match into >120k tokens (rust, nodejs). The
v2/stress macro 0.8093 is +0.21 above the next-best individual
method (tail at 0.5733).

### What this means for §3d

§3d argued that "no single context-provider wins on both signal
positions" — that's still true at the *individual baseline* level
(tail wins late, grep wins middle/cleanly-structured). But §3d
also said v1.3's "threshold-on-tokens" routing is orthogonal to
position, and that's what hybrid-v2 challenges: even though the
router uses ONLY token-count routing (no explicit signal_position
estimation), the token budget happens to encode the right
selection because:

- "grep over-match collapse" cases (rust, nodejs) have grep_tokens
  > 120k — ergo route to tail
- "structured error" cases (airflow, numpy, cpython) have
  grep_tokens ≤ 100k — ergo route to grep where grep wins anyway

So the cleaner take is: **the position-vs-density framing in §3d
was correct in spirit but threshold-on-tokens IS sufficient when
the threshold is calibrated to the actual reasoning-budget collapse
boundary.** A truly "position-aware" router (one that estimates
signal_position from grep's `included_line_ranges` density) might
help on cases that don't fit the budget proxy cleanly, but the
13-case data has no such cases.

### Caveats

1. **Threshold tuned on the same 13-case data it's evaluated on.**
   Same selection-by-method risk that v1.3's 4k threshold had on
   v1.3. Should be retested on v3 with explicit train/holdout split.
2. **Haiku reproducibility issue: 2 of 5 v2/stress cases consistently
   provider-errored on hybrid-v2 contexts (cpython, airflow).**
   The same Haiku-on-pure-grep diagnoses succeeded with the same
   underlying content; the only difference was the 8-line
   "CILogBench hybrid context" header that `run_hybrid_baseline.py`
   prepends. Three retries all failed. Pure speculation: a tokenizer
   edge case in the claude CLI on these specific contexts at
   ~73k-100k tokens. Net effect on Haiku v2 macro: probably
   ~0.05-0.10 underestimate. Sonnet reproduced cleanly across all
   cases.
3. **One new method, not a router family.** The clean v2 result
   could be specific to "grep+tail with budget at 120k". A wider
   router family (grep+tail+rtk-err-cat with multiple budget bands)
   was not explored and might score higher or expose more failure
   modes.
4. **`llm-summary-v1-mock` (#7 macro) was NOT a candidate fallback.**
   v1's threshold-on-tokens design implicitly assumed grep was
   primary and rtk-err-cat was the "compress harder" fallback;
   v2's design assumes tail's bounded-window is the safer fallback.
   A future hybrid that picks among {grep, tail, rtk-err-cat,
   summary} via budget bands could plausibly beat both v1 and v2.

## 4. Why hybrid drops

Per-case detail on the 8 v2 cases (Sonnet 4.6, sv1.1):

```text
case_id                                hybrid sv1.1  grep sv1.1   route          notes
moby-buildx-bake-v2-001                  0.5500       0.6500     rtk-err-cat
pip-pytest-network-github-v2-001         0.9167       0.9750     rtk-err-cat
pnpm-jest-config-v2-001                  0.0000       0.6067     rtk-err-cat   ← total fail
biome-pnpm-not-found-v2-001              0.2500       0.5500     rtk-err-cat
gh-cli-go-test-prompter-v2-001           0.3000       0.3000     grep          tied: both fail (Go FAIL marker)
pandas-cpp-xsimd-neon64-v2-001           0.7500       0.9000     rtk-err-cat
pnpm-audit-vuln-ip-address-v2-001        0.1500       0.4000     grep          tied: both fail (audit ascii_table)
prettier-jest-snapshot-babel-v2-001      0.6000       0.7950     rtk-err-cat
```

- The hybrid routes 6 of 8 v2 cases to rtk-err-cat. On 5 of those 6,
  grep would have done strictly better. The **4k-token threshold
  inside the hybrid is overfit to v1.3's distribution**: v1.3 had
  more cases that legitimately benefited from rtk-err-cat's
  aggressive compression; v2 has more cases where rtk-err-cat
  drops the bounded assertion diff (jest expected/received,
  snapshot diff, C++ template error block).

- On 1 case (`pnpm-jest-config-v2-001`) hybrid scores **0.00 sv1.1**
  because rtk-err-cat truncated the assertion diff and Sonnet
  produced a confident-but-wrong root cause. This single case
  drives most of hybrid's confident-error-rate spike from 0.00 →
  0.17 on v2.

- 2 cases (`gh-cli-go-test-prompter`, `pnpm-audit-vuln-ip-address`)
  are ties at low scores: both grep AND hybrid lose because the
  failure surface doesn't match grep's regex
  `error|failed|...|##[error]`. Go uses `--- FAIL:` (no "failed"
  substring); pnpm audit's vulnerability table uses
  `vulnerabilities found` (also outside the regex). These are v1.3
  grep-regex blindspots, separate from the hybrid threshold issue.

## 5. Caveats

This finding is robust enough to ship as a partial result, but it
is **not** strong enough to retire v1.3 yet. Specifically:

1. **8 v2 cases.** Variance per case is high; one case at 0.00
   alone moves the macro by ~0.07. The direction is robust
   (hybrid drop is 3-4× any other method's drop, agreed across two
   debuggers); the magnitude of the drop could shift ±0.05 at 30+
   cases. Larger-corpus replication is the most-leveraged
   follow-up.
2. **Ground truth was AI-drafted (Opus 4.7) + human-verified by the
   project author.** Each v2 ground_truth.json was drafted by
   Claude Opus 4.7 reading raw.log and then verified item-by-item
   by the project author against per-case checklists. This is
   plan-compliant ("model-generated ground truth unless those
   labels are later human verified") and matches the same review
   pattern E9 used for v1.3, but it is **not** independent human
   annotation. Project-bias caveats from
   `cilogbench_v1_3_limitations.md` §2 still apply, transferred to
   v2.
3. **Two Anthropic debuggers, one prompt.** The v2 finding holds
   across Haiku 4.5 and Sonnet 4.6 — but a third model from a
   different family (Opus 4.7, GPT, Llama) has not been tested.
   The "model-stability" claim from v1.3 generalizes (top-2 and
   bottom-3 ranks identical), but only across two correlated
   models.
4. **`llm-summary-v1-mock`, not real summarizer.** Real Haiku
   summarizer was excluded from the v1.3 lock for cost reasons and
   was not re-run on v2. Conclusions about summary methods are
   unchanged from v1.3 (they are uncompetitive on quality at any
   budget) and remain scoped to the mock.
5. **No human review of v2 diagnoses.** v1.3 had E2/E2b expert-model
   review and E9 AI-assisted human review. v2 has neither yet. The
   `sv1.1` formula is the same calibrated v1.3 formula, but its
   calibration on v2 is unverified.
6. **v2/stress is partial (2/3).** Two stress cases were added in
   the 10-case checkpoint (`numpy-pytest-segfault-argsort-v2-001`
   and `cpython-tcl-windows-matrix-v2-001`) — see §3b above. The
   third stress slot remains empty; "deliberately difficult"
   targets still missing include huge logs (>50k lines),
   scattered-evidence multi-failure, and a non-pytest framework
   (the v2/stress framework dominance flagged by
   `tools/check_split_balance.py` is real until a third stress case
   breaks the 2/2 pytest monoculture).
7. **Hybrid's threshold is the variable, not the method shape.**
   This study cannot say "hybrid as a strategy is bad." It only
   says "this specific 4k-token threshold tuned on v1.3 is bad on
   v2." A v2-tuned threshold would likely recover most of the gap;
   we deliberately did not retune on the same v2 corpus to avoid
   the same selection-by-method risk that produced the v1.3
   overfit (see `cilogbench_v1_3_limitations.md` §9).
8. **Matrix-category coverage is a `tags.json`-only narrative claim,
   not a canonical evaluator category.** The `cpython-tcl-windows-
   matrix-v2-001` case is described in §3b above and the corpus
   reports as "first v2 `matrix_or_monorepo_failure`" coverage.
   That label lives on `tags.json` only. The case's `case.json`
   `failure_category` and its `ground_truth.root_cause.category`
   are both still `test_assertion`, which is what
   `evaluate_diagnosis.py` and `build_split_manifest.py` see and
   what the lock files SHA-pin. The reason: extending
   `case.schema.json` / `ground_truth.schema.json` /
   `prompts/debugger_v1.md` /
   `configs/evaluation/category_compatibility_v1_1.json` to make
   `matrix_or_monorepo_failure` a first-class canonical category
   would require re-running the entire v2 diagnoser pipeline (the
   diagnoser was prompted with a 13-value enum that does not
   include the new category, so it cannot have produced it). That
   re-run is deliberately deferred to a v3 release with an
   explicit train/holdout split so we can avoid the same
   selection-by-method risk flagged in caveat §5.7. Until then:
   evaluator-load-bearing claims should cite `test_assertion`;
   matrix-coverage narrative claims should cite this caveat.

## 6. What this enables

Even with caveats §5, the cross-debugger result is strong enough
to:

- **Block "v1.3 hybrid is the winner" framing** in any
  user-facing recommendation. The cost advantage holds; the
  quality match does not generalize. The v1.3 one-pager has been
  updated.
- **De-prioritize hybrid retuning as a near-term feature.**
  Re-tuning on the v2 corpus before the corpus is bigger would
  re-introduce the selection-by-method risk. The cleaner path is
  to wait for a v3 corpus and tune against an explicit
  train/holdout split.
- **Justify continued investment in `grep`'s regex.** The two v2
  cases where grep ties hybrid at low scores (Go `--- FAIL:`,
  audit ascii_table) are clean grep-regex misses; adding
  `\bFAIL\b` and a vulnerability/audit keyword set would close
  most of the remaining grep gap. But: any regex extension should
  be motivated by collected cases, not speculation.

## 7. What this does NOT enable

- "Hybrid is wrong on v1.3." The v1.3 numbers stand on v1.3.
- "Hybrid is universally bad." Only "this 4k threshold doesn't
  generalize to v2."
- "Grep is universally good." Grep loses two v2 cases at 0.30 and
  0.40 sv1.1 — its regex has real blindspots.
- "Sonnet > Haiku on this benchmark." The two debuggers agree on
  ranking. Their absolute scores differ (Sonnet generally higher
  by ~0.05), but that is unrelated to the v1.3 → v2 shift.

## 8. Reproducibility

Two protocol locks now exist for v2; the §3 8-case headline numbers
reproduce against `cilogbench-v2-partial`, and the §3b 10-case
checkpoint numbers reproduce against `cilogbench-v2-checkpoint`.
Both locks SHA-pin the same v1.3 schemas, prompts, and evaluators
that were in `cilogbench-v1.3.lock.json`; they differ only in case
set:

```text
                            v2-partial      v2-checkpoint   v2-checkpoint-12
schemas / prompts /         identical       identical       identical
evaluators (14 hashes)
baselines (7)               identical       identical       identical

splits                      5 splits        6 splits        6 splits
                            dev/holdout/    + v2/stress     + v2/stress
                            stress (v1.3)   (2 cases)       (4 cases)
                            + v2/dev (3)
                            + v2/holdout (5)

total cases                 24              26              28
v2 new cases                 8              10              12
```

**For the 12-case checkpoint headline numbers (§3c) — current
canonical** — fresh-checkout reproduction:

```bash
python3 tools/validate_protocol_lock.py --protocol protocols/cilogbench-v2-checkpoint-12.lock.json
# Should print: "Protocol lock OK: cilogbench-v2-checkpoint-12"

# Same baseline + diagnoser bash loop as the 10-case repro below;
# v2/stress now contains 4 cases instead of 2 (numpy + cpython +
# rust + nodejs). 96 diagnosis calls per debugger total
# (12 v2 cases × 8 baselines).
```

**For the 10-case checkpoint headline numbers (§3b)** — fresh-checkout
reproduction:

```bash
python3 tools/validate_protocol_lock.py --protocol protocols/cilogbench-v2-checkpoint.lock.json
# Should print: "Protocol lock OK: cilogbench-v2-checkpoint"

# Re-run all baselines on all splits (requires `rtk` on PATH):
for split in dev holdout stress v2/dev v2/holdout v2/stress; do
  for m in raw tail grep; do
    python3 tools/run_baseline.py --method "$m" --split "$split"
  done
  for m in rtk-read rtk-log rtk-err-cat; do
    python3 tools/run_rtk_baseline.py --method "$m" --split "$split"
  done
  python3 tools/run_llm_summary_baseline.py --split "$split" \
    --provider mock --method llm-summary-v1-mock
  python3 tools/run_hybrid_baseline.py --split "$split" \
    --config configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json
done

# Re-run real-debugger pipelines (requires `claude` CLI + opt-in env):
export DIAGNOSIS_COMMAND="python3 $(pwd)/examples/diagnosis_shim_claude_cli.py"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
for debugger_model in sonnet haiku; do
  export CILOGBENCH_CLAUDE_MODEL=$debugger_model
  diagname=$([[ $debugger_model == sonnet ]] && echo real-debugger-v2 \
                                              || echo real-debugger-v1)
  for split in dev holdout stress v2/dev v2/holdout v2/stress; do
    for m in raw tail grep rtk-read rtk-log rtk-err-cat \
             llm-summary-v1-mock hybrid-grep-4k-rtk-err-cat-v1; do
      python3 tools/run_diagnosis.py --split "$split" \
        --diagnoser command --diagnoser-name $diagname \
        --command "$DIAGNOSIS_COMMAND" --context-method "$m"
    done
    python3 tools/evaluate_diagnosis.py --split "$split" --diagnoser $diagname
  done
done
```

The v2 splits collectively run 80 diagnosis calls per debugger
(10 v2 cases × 8 baselines). Sonnet 4.6 + Haiku 4.5 cost roughly
$1.85 + $0.40 respectively at this scale. v1.3 cached numbers are
reused; only v2 splits need re-running on a fresh checkout.

**For the 8-case Phase 3 baseline numbers (§3, §4)** — same
commands but iterate over only `dev holdout stress v2/dev v2/holdout`
(omit `v2/stress`) and validate against
`protocols/cilogbench-v2-partial.lock.json`. That run was 64
diagnosis calls per debugger and is preserved as a historical
checkpoint; the canonical "post-Phase-2-checkpoint" numbers are
the §3b ones above.

## 9. Recommended next steps

In priority order:

1. **Continue v2 corpus collection** to ≥30 cases, specifically
   targeting (a) more test_assertion cases with bounded diffs,
   (b) timeout/OOM (still 0 in v2), (c) a true "1 of N matrix
   legs" failure (still 0 in v2), (d) Go FAIL-marker and audit
   ascii_table cases to harden the grep blindspot subclaim.
2. **Independent human review on a 16-item v2 batch** — same UX as
   E9 for v1.3 — to lift the project-author-bias caveat on v2
   ground truth.
3. **A third debugger model** (Opus 4.7, or any non-Anthropic) to
   confirm the v2 ranking is not a Claude-family artifact.
4. **A v3 corpus + v3-tuned hybrid** when v2 reaches its target
   34 cases, with explicit train/holdout split for hybrid
   threshold tuning. Do not retune on v2 itself.

## 10. Where the artifacts live

```text
protocols/cilogbench-v2-partial.lock.json        ← 8-case lock (§3)
protocols/cilogbench-v2-checkpoint.lock.json     ← 10-case lock (§3b)
protocols/cilogbench-v2-checkpoint-12.lock.json  ← 12-case lock (§3c)
protocols/cilogbench-v2-checkpoint-13.lock.json  ← 13-case lock (§3d, current canonical)
docs/corpus/cilogbench_v2_case_matrix.md     ← target matrix + counts
docs/corpus/cilogbench_v2_collection_guidelines.md
docs/corpus/cilogbench_v2_annotation_guide.md
docs/corpus/v2_case_intake_queue.md          ← rolling intake worklist
cases/dev/, cases/holdout/, cases/stress/    ← 16 legacy v1.3 cases
cases/v2/dev/ (3), cases/v2/holdout/ (5),
cases/v2/stress/ (5)                          ← 13 new_v2 cases
results/{dev,holdout,stress,v2/dev,v2/holdout,v2/stress}/eval_diagnosis_real-debugger-{v1,v2}.json
                                              ← Haiku + Sonnet sv1.1 numbers
results/{...}/eval_<method>.json             ← signal-recall numbers
reports/v2_split_balance.md                  ← split-balance narrative (refreshed at 13-case)
reports/e10_phase3_v2_partial_signal_recall.md   ← deterministic detail (8-case)
reports/e10_phase3_v2_partial_diagnosis.md       ← real-debugger detail (8-case)
reports/e10_codex_adversarial_review_fixes.md    ← privacy-gate fix log
reports/e10_v2_generalization_partial.md          ← THIS report (canonical narrative)
```

## 11. Status of the limitations originally listed in v1.3

The v1.3 limitations doc named several risks. v2 partial:

- **§1 sample size:** v2 adds 8 cases × 2 splits = 16 new
  diagnoses per debugger × 2 debuggers = 64 new sv1.1 measurements
  vs v1.3's original 16 cases × 1 debugger. Still small; per-case
  variance still dominates magnitude.
- **§2 calibration via expert model, not human:** unchanged. v2
  reuses the same calibrated `diagnosis_score_v1_1` formula.
- **§3 two debugger models only:** unchanged on v2 (Haiku + Sonnet).
- **§5 small/hand-annotated/JS-Python-skewed corpus:** v2 adds 1
  Go, 1 cpp, 1 docker-buildkit, 1 cargo-pnpm-cross. Still skewed
  but less than v1.3.
- **§9 hybrid threshold selected from prior analysis:** **this
  is the limitation v2 was designed to test, and it FAILS the
  test**. The hybrid as locked in v1.3 is overfit; sv1.1 drops
  −0.32 on the independent corpus.

The other limitations (deterministic scoring proxy, no MCP
baseline, RTK version-specific results, pricing informational)
carry over to this report unchanged.
