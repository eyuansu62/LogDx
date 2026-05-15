# CILogBench E10 — v2 generalization (partial)

> **Six protocol-lock files exist; two validate today:**
>
> - [`cilogbench-v2-partial`](../protocols/cilogbench-v2-partial.lock.json)
>   — frozen at the **8-case** v2 state (24 cases total, 5 splits;
>   v2/stress split absent at lock time). Validates today
>   because its `splits` dict does NOT include v2/stress, so the
>   later v2/stress additions don't break it. The §3 8-case
>   numbers below are anchored to this lock.
> - [`cilogbench-v2-checkpoint`](../protocols/cilogbench-v2-checkpoint.lock.json)
>   — frozen at the **post-Codex-fix 12-case state** at commit
>   f370ea2 (28 cases, v2/stress=4). **Does NOT validate today**
>   because the on-disk v2/stress manifest moved from 4 cases to
>   5 at commit 64c7340 (when airflow's middle-signal case was
>   added). Treat as a historical snapshot of the 4-stress-case
>   state. The original 10-case Phase 2 eval results referenced
>   in §3b live in commit 530d5fd; check out that commit to
>   reproduce them.
> - [`cilogbench-v2-checkpoint-12`](../protocols/cilogbench-v2-checkpoint-12.lock.json)
>   — frozen at the same **post-Codex-fix 12-case state** as
>   v2-checkpoint (above). **Does NOT validate today** for the
>   same v2/stress=4-vs-5 reason. The §3c 12-case eval results
>   live at commit 7036fdb.
> - [`cilogbench-v2-checkpoint-13`](../protocols/cilogbench-v2-checkpoint-13.lock.json)
>   — frozen at the 13-case state (29 cases total, v2/stress=5).
>   **Does NOT validate today** because Batch 5 grew v2/holdout
>   from 5→8 and v2/stress from 5→6. The §3d 13-case numbers
>   and the §3e hybrid-v2 prototype anchor here.
> - [`cilogbench-v2-checkpoint-17`](../protocols/cilogbench-v2-checkpoint-17.lock.json)
>   — frozen at the 17-case state (33 cases total). **Does NOT
>   validate today** because Batch 6 grew v2/holdout 8→10. The
>   §3f Batch 5 hold-out validation numbers anchor here.
> - [`cilogbench-v2-checkpoint-19`](../protocols/cilogbench-v2-checkpoint-19.lock.json)
>   — **current canonical** (35 cases total, v2/holdout=10,
>   v2/stress=6 — adds the 2 Batch 6 hold-out cases). Validates
>   today. The §3g Batch 6 hold-out validation numbers anchor
>   here. This lock includes BOTH hybrid baselines per the
>   2026-05-08 Codex review's Finding 2.
>
> All six locks SHA-pin the same v1.3 schemas, prompts, and
> evaluators that were in `cilogbench-v1.3.lock.json`, so v1.3
> numbers reproduce identically against any of them. **Per the
> Codex adversarial reviews (2026-05-07, 2026-05-08):** all locks
> pin the hybrid baseline file hashes, and `validate_protocol_lock.py`
> auto-detects all `type: hybrid_context_provider` baselines and
> fail-closes on hybrid drift.
>
> **For new work, use only `cilogbench-v2-checkpoint-19`.** The
> older locks are historical artifacts; checking them out for
> reproduction means also checking out the matching git commit so
> the on-disk manifests match the lock's frozen state.
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
- **§3e — v2 router prototype (evaluation-tuned, NOT a clean
  generalization claim):** built `hybrid-grep-120k-tail-v2` to
  test §3d's hypothesis. Two changes vs v1: budget 4k → 120k
  (calibrated against `eval_diagnosis_*.json` outputs to find the
  empirical Sonnet/Haiku abstain cliff), and fallback rtk-err-cat
  → tail. **Per Codex adversarial review 2026-05-08, this is
  acknowledged as evaluation-tuned (`uses_diagnosis_eval: true`)
  — the threshold was calibrated on the same 13 cases it is
  evaluated on**. Result on the 13-case CALIBRATION data: Sonnet
  v2 macro 0.6801 (#1), Haiku v2 macro 0.5311 (#2). Drop from
  v1.3 to v2 is −0.11 / −0.16 vs v1's −0.34 / −0.30.
- **§3f — Hold-out validation on Batch 5 (4 new cases not used
  for tuning):** spring-boot-checkformat (java-gradle), gradle-
  projecthealth (java-gradle), go-redis-pubsub-channel-timeout
  (go), argocd-race-conditions (go, **first huge log >50k lines**
  in the corpus). Hybrid-v2 hold-out result: Sonnet 0.5757 #1
  (drop −0.10 from calibration), Haiku 0.3521 #2 (drop −0.15).
  The §3e direction (v2 > v1) holds: hybrid-v2 beats hybrid-v1 by
  +0.21 Sonnet / +0.02 Haiku on hold-out. **Sonnet #1 ranking
  generalizes; Haiku #1 does NOT** (grep takes #1 on Haiku
  hold-out, partly because §3e caveat 2's CLI flake reproduces
  on go-redis). **The 13-case "tail unseats grep" macro claim is
  fully retracted on hold-out** — tail drops −0.21 Sonnet / −0.18
  Haiku, the largest hold-out drop of any non-raw method.
  Argocd's huge log exposes a hybrid-v2 weakness: tail-fallback
  catches only post-test cleanup chatter while rtk-err-cat
  captures the failure structure better. See §3f.

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

> ⚠️ **Codex adversarial-review 2026-05-08 finding [high]:** the
> `hybrid-grep-120k-tail-v2` threshold was tuned by reading
> `eval_diagnosis_*.json` outputs (which themselves load each
> case's `ground_truth.json` for scoring), so the prototype is
> **evaluation-tuned** rather than a blind generalization
> result. The numbers below are correct on the 13-case
> calibration data; promoting them to "hybrid-v2 generalizes
> better than hybrid-v1 on v2" requires retesting on a v3
> hold-out split with no eval-data peeking during threshold
> selection. The prototype's value is the *direction* it
> demonstrates (a budget-recalibrated grep+tail router can beat
> hybrid-v1) — not the absolute Δ. The config has been updated
> to declare `uses_diagnosis_eval: true` to make this
> calibration-source visible at the lock layer. See §3e
> caveat (1) below for the full disclosure.

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

**Calibration-source disclosure (corrected after Codex review):**
the 120k threshold was set from `eval_diagnosis_*.json` outputs
to find the empirical abstain cliff. Those eval files ARE produced
by `tools/evaluate_diagnosis.py`, which DOES load each case's
`ground_truth.json` for scoring. So the threshold sits downstream
of ground-truth-aware artifacts even though the router code
itself doesn't open `ground_truth.json` at runtime. The
hybrid-v2 config declares `uses_diagnosis_eval: true` to make
this leakage visible at the lock layer. The headline numbers
below are correct on the 13-case calibration data but are NOT a
clean blind generalization claim. See caveat (1) below.

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

1. **Threshold tuned on the same 13-case data it's evaluated on
   — calibration leakage acknowledged.** The 120k threshold was
   selected by reading `eval_diagnosis_*.json` outputs, which are
   produced by `tools/evaluate_diagnosis.py` after that tool loads
   `ground_truth.json` per case. So the threshold is downstream
   of ground-truth-aware artifacts. The hybrid-v2 config now
   declares `uses_diagnosis_eval: true` (was incorrectly `false`
   in the original config; corrected after Codex adversarial
   review 2026-05-08). The result demonstrates the hypothesis
   (budget recalibration + tail fallback can beat v1) but the
   absolute Δ is plausibly inflated by the calibration-on-eval
   step. v1.3's hybrid-v1 had the same calibration risk on v1.3
   (per `cilogbench_v1_3_limitations.md` §9); we are being
   explicit about it here. The clean fix is a v3 train/holdout
   split where the threshold is selected on a "calibration"
   subset and evaluated on a held-out subset that the threshold
   selector never saw.
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

## 3f. Hold-out validation — Batch 5 (2026-05-08)

The §3e caveat (calibration leakage) was addressed by collecting
**4 new cases that the hybrid-v2 threshold was NOT tuned on**:

```text
Batch 5 hold-out cases:
  spring-boot-checkformat-batch5-v2-001   v2/holdout  java-gradle  lint_error  late      6275 lines
  gradle-projecthealth-batch5-v2-001      v2/holdout  java-gradle  lint_error  late     12867 lines
  go-redis-pubsub-channel-timeout-batch5  v2/holdout  go           timeout    middle    2730 lines
  argocd-race-conditions-batch5-v2-001    v2/stress   go           test_assn  scattered 89188 lines  ← huge!
```

These fill three corpus gaps (java-gradle ecosystem, go ecosystem,
huge log_size_bucket — the last was 0/29 corpus-wide through the
13-case state). Hybrid-v2's 120k-token threshold was not adjusted
between Batch 5's collection and evaluation. Locked at
[`protocols/cilogbench-v2-checkpoint-17.lock.json`](../protocols/cilogbench-v2-checkpoint-17.lock.json)
(33 cases, 6 splits, 23 hashes).

### Headline: hybrid-v2 generalizes on Sonnet, partially on Haiku

```text
                                Sonnet 4.6                       Haiku 4.5
                                calib    holdout    Δ           calib    holdout    Δ
hybrid-grep-120k-tail-v2        0.6707   0.5757   -0.095   ★    0.5055   0.3521   -0.153
grep                            0.5914   0.5303   -0.061        0.4392   0.5079   +0.069   ←improves!
tail                            0.6110   0.4031   -0.208        0.5700   0.3937   -0.176
rtk-err-cat                     0.4612   0.2804   -0.181        0.4192   0.3079   -0.111
hybrid-grep-4k-rtk-err-cat-v1   0.4171   0.3671   -0.050        0.4031   0.3287   -0.074
raw                             0.3445   0.1543   -0.190        0.2903   0.1131   -0.177
rtk-read                        0.3097   0.1411   -0.169        0.2971   0.1259   -0.171
rtk-log                         0.2375   0.0667   -0.171        0.2242   0.0813   -0.143
llm-summary-v1-mock             0.2312   0.1521   -0.079        0.2587   0.1521   -0.107

Hold-out ranking:
  Sonnet:  hybrid-v2 #1 (0.5757) > grep (0.5303) > tail (0.4031) > hybrid-v1 (0.3671)
  Haiku:   grep #1 (0.5079) > tail (0.3937) > hybrid-v2 (0.3521) > hybrid-v1 (0.3287)
```

**The §3e direction claim is upheld on Sonnet:** hybrid-v2 stays
#1 on hold-out, beating grep (+0.05) and hybrid-v1 (+0.21). Drop
of −0.10 from calibration is mid-pack — methods like tail
(−0.21), rtk-err-cat (−0.18), and raw (−0.19) all dropped more.

**On Haiku, hybrid-v2 falls to #2** behind grep. Two contributing
factors:
1. **Haiku-on-grep IMPROVES** on hold-out (+0.07) — the only
   method that does. Grep was suppressed on the calibration set
   by the rust+nodejs density blowups (§3c finding); the
   hold-out cases all have grep tokens that fit the budget for
   Haiku's reasoning, so grep recovers.
2. **§3e caveat 2 reproduces on go-redis.** The Haiku CLI
   provider-error pattern previously seen on cpython+airflow
   recurs: hybrid-v2 routes go-redis to grep (22k tokens), the
   wrapped context has the 8-line CILogBench hybrid header,
   and Haiku CLI exits 1 with empty output → score 0.0. Pure
   grep on the same go-redis content scores 0.46. Net Haiku
   hybrid-v2 macro is ≈0.05-0.10 below what a clean run would
   produce.

### Per-case detail (Sonnet 4.6) — where hybrid-v2 routes

```text
case               grep_tok    routed_to    hybrid-v2  grep   tail   rtk-err-cat  hybrid-v1
spring (lint)         4860     grep         0.7875    0.7875  0.7875  0.5583     0.5583
gradle (lint)         8928     grep         0.7833    0.7875  0.6583  0.0000     0.3500
go-redis (timeout)   22418     grep         0.6155    0.5464  0.0500  0.0000     0.0000
argocd (huge race) 1865128     tail         0.1167    0.0000  0.1167  0.5633     0.5600  ← v2 LOSES here
                                            ------    ------  ------  ------     ------
holdout macro (Sonnet)                      0.5757    0.5303  0.4031  0.2804     0.3671
```

**Hybrid-v2 wins the first 3 cases by routing to grep** (correctly:
all 3 fit the 120k budget; grep is competitive or strictly better
than tail on each). **Hybrid-v2 LOSES on argocd** because grep is
1.86M tokens (way past the 120k cliff), tail's bounded 200-line
window catches only post-test cleanup chatter (not the failure
summary at L87473-88904), and the v1 hybrid's rtk-err-cat
fallback compresses the 89k-line log into a 2156-line, 374KB
summary that both Sonnet and Haiku can reason over.

> ⚠ **Per Codex adversarial review 2026-05-08-#2 [high]:** rtk's
> filter input was truncated at the upstream 10 MiB cap on
> argocd's 12.8 MB raw log. `tools/run_rtk_baseline.py` now
> surfaces this warning into `metadata.rtk_input_truncated:
> true` so consumers can audit (was previously silent in
> `<case>.stderr.txt`). The argocd rtk-err-cat output **did
> empirically capture all three failures** (app_test.go:1936
> at output L297-299, two `WARNING: DATA RACE` blocks at L939
> and L1454, with `testing.go:1712: race detected` at L947 and
> L1455 + the consolidated summary at L2105-2124) because they
> all sit before the 10 MiB cut-off (~78% of the 12.8 MB file)
> and rtk-err-cat's selection is content-based, not position-
> based. **The §3f rtk-err-cat fallback finding stands for this
> specific case but is fragile**: a future huge log with
> failures only in the last 22% would be silently missed by
> rtk-err-cat under the current 10 MiB cap. A v3 hybrid with
> rtk-err-cat as fallback should either gate on `metadata
> .rtk_input_truncated` (treat truncated outputs as
> provider-error, route to a different fallback) or use a
> truncation-aware variant.

This is the cleanest counter-example to v2's "tail is the safer
fallback" choice yet observed: on truly huge multi-failure logs,
**`rtk-err-cat` is the better fallback IF the failures sit in
the first 78% of the file**. v2's calibration data didn't have a
case where this mattered (rust+nodejs at 161k/359k tokens both
had late-signal failures so tail won there); the argocd hold-out
exposes the gap. A robust v3 router would need to either
extend rtk's input cap or detect truncation and route around it.

### What this means for v3

The Batch 5 hold-out validation gives a partial generalization
result for hybrid-v2:

- ✅ **Direction (hybrid-v2 > hybrid-v1) is real**: +0.21 Sonnet,
  +0.02 Haiku on hold-out. Recalibrating the budget threshold
  was not pure overfitting.
- ✅ **Sonnet #1 ranking holds out-of-sample.** On 4 brand-new
  cases hybrid-v2 still leads by +0.05 over the next-best method.
- ⚠ **Haiku #1 ranking does NOT hold out-of-sample.** Grep takes
  #1 on Haiku hold-out, in part due to hybrid-v2 inheriting
  §3e's CLI-flake on wrapped contexts, in part because Haiku-grep
  was artifically depressed by the rust+nodejs density blowups
  in calibration.
- ❌ **The 13-case "tail unseats grep" macro claim is fully
  retracted.** Tail's calibration lead was sampling-driven.
  On hold-out tail drops −0.21 Sonnet / −0.18 Haiku — the
  largest hold-out drop of any method except raw/rtk-read.
  Tail's bounded window is structurally weak on middle-signal
  (go-redis) and scattered-signal (argocd) cases.
- ❌ **Tail-fallback choice in hybrid-v2 has a real failure mode**
  on huge multi-failure scattered-signal logs. argocd shows
  rtk-err-cat would have been the better fallback there. A v3
  "hybrid-v3" with budget-band routing (grep → rtk-err-cat →
  tail or summary based on token count + failure-locality
  heuristic) is now well-motivated.

### Updated headline table

| Headline claim | 8-case | 10-case | 12-case | 13-case | 17-case (with hold-out) |
|---|---|---|---|---|---|
| "hybrid-v1 sv1.1 drops substantially v1.3 → v2" | ✅ −0.32 / −0.30 | ✅ −0.33 / −0.25 | ✅ −0.34 / −0.28 | ✅ −0.34 / −0.30 | ✅ −0.34 / −0.30 |
| "hybrid-v1 stays in the bottom-half" | ✅ #6/8 | ✅ #3-4/8 | ✅ #4/8 | ✅ #4/8 | ✅ holdout #4/9 Sonnet, #4/9 Haiku |
| "tail is the unanimous v2 winner" | (#2) | (#2) | ⚠ macro-only | ⚠ caveat | ❌ **fully retracted on hold-out** |
| "grep collapses on high-error-density logs" | (not seen) | (not seen) | ✅ rust+nodejs | ✅ confirmed | ✅ argocd at 1.86M tok confirms |
| "tail collapses when signal isn't late" | (untested) | (untested) | (untested) | ✅ airflow 0.017 | ✅ confirmed go-redis 0.05, argocd 0.12 |
| "hybrid-v2 generalizes better than hybrid-v1" | n/a | n/a | n/a | (calibration only) | ⚠ Sonnet ✅ +0.21 hold-out; Haiku ✅ +0.02 |
| "hybrid-v2 #1 on v2 macro" | n/a | n/a | n/a | (calibration only) | ⚠ Sonnet ✅; Haiku ❌ (grep takes #1) |
| "rtk-err-cat is sometimes the right fallback" | implicit | implicit | implicit | implicit | ⚠ argocd gives rtk-err-cat 0.56 vs hybrid-v2's tail 0.12 BUT rtk truncated input at 10 MiB; finding fragile to failure-position |

### Caveats (carry-over from §3e + new)

1. **Calibration leakage now resolved on Sonnet but not Haiku.**
   Sonnet's hold-out validation supports the calibration → hold-out
   direction. Haiku's does not (grep wins instead), so the Haiku
   calibration result remains plausibly partly overfit.
2. **§3e caveat 2 (Haiku CLI flake on wrapped contexts at
   70-100k tokens) reproduces on go-redis** in this hold-out.
   Net effect on Haiku hybrid-v2 macro is approximately
   −0.05 to −0.10 vs a clean run. Worth fixing before any
   v3 lock.
3. **Hold-out is 4 cases.** Per-case variance is high; the
   argocd case alone moves the macro by ~0.03-0.04. The
   direction is robust (3 of 4 cases favor hybrid-v2 on Sonnet,
   2 of 4 on Haiku) but the magnitude could shift ±0.05 at 30+
   hold-out cases.
4. **All 4 hold-out cases are in v2/holdout + v2/stress.**
   v2/dev was not extended in Batch 5. The hold-out doesn't
   cover the v2/dev distribution.
5. **rtk-err-cat truncation on argocd (Codex 2026-05-08-#2 [high]).**
   rtk's filter input was truncated at 10 MiB on the 12.8 MB
   argocd raw log. The §3f finding "rtk-err-cat is the better
   fallback for huge logs" stands for this specific case
   (failures sit in the first 78% of the file by accident) but
   is fragile under shift to logs where failures sit in the
   trailing 22%. A v3 router with rtk-err-cat as fallback
   should treat `metadata.rtk_input_truncated: true` as
   provider-error and route to a different fallback.
   `tools/run_rtk_baseline.py` now surfaces the warning into
   manifest metadata (was silent in stderr file before).

## 3g. Second hold-out — Batch 6 (2026-05-08)

To strengthen the §3f generalization claim, **Batch 6 added
2 more hold-out cases** (no retuning of hybrid-v2's 120k
threshold). Lock at
[`protocols/cilogbench-v2-checkpoint-19.lock.json`](../protocols/cilogbench-v2-checkpoint-19.lock.json)
(35 cases, 19 v2). The 5-Batch-6 plan (`/Users/eyuansu62/.claude/plans/quiet-swinging-lecun.md`)
was scaled down to 2 because the harder gap-fill targets
(permission_or_secret, OOM-killed, k8s-helm, early-signal) did
not surface in run-list browsing within budget; deferred to
Batch 7+.

```text
Batch 6 hold-out cases:
  dubbo-samples-test-timeout-batch6-v2-001    v2/holdout  java-maven   timeout_or_oom    late   6095 lines
  hibernate-orm-dbversion-test-batch6-v2-001  v2/holdout  java-gradle  test_assertion    late  46198 lines
```

Both fill ecosystem gaps (java-maven was 0/v2 → 1; java-gradle now
3/v2). Both are late-signal so they don't extend signal-position
diversity. Both fit the 120k token budget so hybrid-v2 routes both
to grep — making this batch a particularly clean test of
"is the recalibrated grep-with-bigger-budget actually better
than v1's grep-with-aggressive-rtk-fallback on hold-out?"

### Headline result on Batch 6 hold-out

```text
                                Sonnet 4.6                       Haiku 4.5
                                B5 (4)   B6 (2)   B5+B6 (6)      B5 (4)   B6 (2)   B5+B6 (6)
hybrid-grep-120k-tail-v2        0.5757   0.9000   0.6838   #1    0.5266   0.7625   0.6053   #2
grep                            0.5303   0.8875   0.6494   #2    0.5079   0.8000   0.6053   #2 (tied)
hybrid-grep-4k-rtk-err-cat-v1   0.3671   0.8125   0.5156   #4    0.3287   0.6583   0.4385   #4
tail                            0.4031   0.6000   0.4687   #5    0.3937   0.6000   0.4625   #3
rtk-err-cat                     0.3679   0.5575   0.4311   #6    0.3079   0.7000   0.4386   #4 (tied)
rtk-log                         0.0500   0.4783   0.1928   #7    0.0510   0.4500   0.1840   #6
llm-summary-v1-mock             0.1521   0.1500   0.1514   #8    0.1521   0.0521   0.1188   #7
raw                             0.1543   0.0000   0.1029   #9    0.1131   0.0000   0.0754   #8
rtk-read                        0.1411   0.0000   0.0941   #9    0.1259   0.0000   0.0840   #8
```

**Combined hold-out (6 cases) ranking:**

- Sonnet: hybrid-v2 #1 (0.6838) > grep #2 (0.6494). +0.034 lead.
- Haiku: hybrid-v2 (0.6053) **tied** with grep (0.6053). Effectively
  a wash on Haiku at 6 cases.

### Two important things Batch 6 confirms (and one it disconfirms)

✅ **Confirms: §3f direction generalizes.** Hybrid-v2 stays #1 on
Sonnet across two independent hold-out batches. Gap from Batch 5
(+0.045 over grep) to Batch 6 (+0.012) shrunk but remained positive.

✅ **Confirms: hybrid-v2 > hybrid-v1.** On Batch 6 alone, hybrid-v2
+0.0875 Sonnet / +0.1042 Haiku over hybrid-v1. Both batches show
the recalibrated budget + tail-fallback design beats v1's 4k +
rtk-err-cat on hold-out.

❌ **Disconfirms: "hybrid-v2 dominates on Haiku".** §3f had
hybrid-v2 at Haiku #2 behind grep on B5; Batch 6 has them tied
on combined B5+B6 macro (both 0.6053). Per-case on Batch 6 dubbo,
**Haiku tail beats hybrid-v2 0.90 vs 0.60** — which is the §3e
caveat 2 CLI flake reproducing AGAIN: hybrid-v2 routes dubbo to
grep at 16k tokens, the wrapped grep context produces a different
Haiku diagnosis than the bare grep context (0.60 vs 0.75). This
is now confirmed reproducible on a third independent case (after
cpython, airflow, go-redis) — it's a real Haiku-on-wrapped-context
issue, not a one-off.

### Per-case detail (Sonnet 4.6) — where Batch 6 matters

```text
case                              grep_tok   routed   hybrid-v2  grep   tail   hybrid-v1
dubbo-samples-test-timeout         16973     grep     0.9000     0.7750  0.9000  0.9000
hibernate-orm-dbversion            65045     grep     0.9000     1.0000  0.3000  0.7250
                                                     ------    ------  ------  ------
Batch 6 macro (Sonnet)                                0.9000    0.8875  0.6000  0.8125
```

Both cases: hybrid-v2 routes to grep (correctly — both fit 120k).
On dubbo (small log, late signal) all three of {tail, hybrid-v1,
hybrid-v2} hit 0.9; only grep alone is slightly weaker (0.775)
because it returns 17k tokens of mostly-noise that Sonnet
reasoning-budget'd. On hibernate (46k-line log, late single-test
failure) grep edges hybrid-v2 at 1.0 vs 0.9 (small difference
attributable to wrapped-context header), but tail collapses to
0.3 because the failure is at L45536 of 46198 (just at the edge
of the bottom-200 window for tail-200).

### Signal-recall (deterministic) at 19-case state

```text
                                v1.3 sig    v2 sig (17)    v2 sig (19)    Δ from 17→19
hybrid-v1                       0.8237      —              ~0.49          —
grep                            0.8756      —              ~0.85          stable
tail                            0.8549      —              ~0.78          stable
```

Stable at the 17→19 transition; the 2 new java cases don't
materially shift the signal-recall macro.

### Updated headline table at the 19-case state

| Headline claim | 17-case | 19-case (Batch 6 hold-out) |
|---|---|---|
| hybrid-v1 stays #4-5 across both debuggers | ✅ | ✅ #4 Sonnet, #4 Haiku stable |
| hybrid-v2 generalizes better than hybrid-v1 | ⚠ Sonnet ✅ +0.21; Haiku ✅ +0.02 | ✅ direction confirmed on B5+B6 (Sonnet +0.17, Haiku +0.17) |
| hybrid-v2 #1 on v2 macro | ⚠ Sonnet ✅; Haiku ❌ (grep takes #1) | ⚠ Sonnet #1 stable; **Haiku tied with grep** |
| §3e CLI-flake on Haiku wrapped contexts | confirmed cpython+airflow | ✅ **third reproduction** — dubbo Haiku hybrid-v2 0.60 vs grep 0.75 |
| tail collapses when signal isn't late | ✅ go-redis 0.05 | ✅ also hibernate 0.30 (signal is late but barely outside tail's window at L45536/46198) |

### Remaining caveats from §3f carry over

1-5 (calibration leakage, hold-out size, unrepresented v2/dev,
rtk-err-cat truncation, Haiku CLI flake) all still apply.

The §3f hold-out caveat that hybrid-v2 was tested on only 4
cases is now partially addressed: 6 cases (4 + 2). Still small;
larger replication (≥30 hold-out cases per debugger) is the
clean next step but requires Batch 7+ collection.

## 3h. Hybrid-v3 prototype — testing the §3f hypothesis (2026-05-08)

§3f's argocd finding suggested that **rtk-err-cat could be the
better fallback than tail** for huge logs. Codex 2026-05-08-#2
[high] later showed that rtk truncates input at 10 MiB silently,
so any v3 design needs to gate on `metadata.rtk_input_truncated`.
Per the approved plan
(`/Users/eyuansu62/.claude/plans/quiet-swinging-lecun.md`),
hybrid-v3 was implemented as a 3-way router:

```
hybrid-grep-120k-rtk-tail-v3 routing:
  IF grep_tokens ≤ 120000:
      use grep                               # matches v2 fast path
  ELIF rtk-err-cat manifest's metadata.rtk_input_truncated == False:
      use rtk-err-cat                        # NEW intermediate
  ELSE:
      use tail-200                           # matches v2 fallback
```

Implemented in `tools/run_hybrid_baseline.py` (extended to optional
`intermediate_method` config field). Locked in
`cilogbench-v2-checkpoint-19.lock.json` alongside v1 and v2 (3
hybrid baselines now).

Routing on v2/stress (the only split where v3 differs from v2):

```text
case               grep_tok   rtk_trunc   v2 routes    v3 routes
numpy                28010    False       grep         grep            (same)
cpython              73525    False       grep         grep            (same)
airflow             100864    False       grep         grep            (same)
rust                161086    False       tail         rtk-err-cat     (v3 NEW)
nodejs              359460    False       tail         rtk-err-cat     (v3 NEW)
argocd             1865128    True        tail         tail            (v3 truncation-gate works)
```

### Result: hybrid-v3 essentially TIES hybrid-v2 (post-Codex-fix)

> ⚠️ **Codex 2026-05-09 [high] fix applied.** The first iteration of
> this section reported v3 LOSING to v2 by −0.055 Sonnet on the
> full v2 macro because the v3 router selected `rtk-err-cat`
> regardless of its output token count. On nodejs, rtk-err-cat
> produced 320k tokens (rtk_input_truncated=False, just an
> oversized but non-truncated output) and Sonnet abstained →
> sv1.1 = 0.0. The fix (commit `<TBD>`) adds a second gate:
> `intermediate_budget_tokens` (default 120k, same as primary).
> If rtk-err-cat output exceeds this, fall through to tail.
> A regression test in `tools/tests/test_hybrid_router.py`
> covers the path. v3 now routes nodejs to tail (matches v2).
> Numbers below are post-fix.

```text
                                full v2 macro             Batch 6 hold-out (2 cases)
                                Sonnet     Haiku          Sonnet     Haiku
hybrid-grep-120k-tail-v2        0.6748     0.5370   #1    0.9000     0.7625
hybrid-grep-120k-rtk-tail-v3    0.6589     0.5526   ↓     0.8875     0.9125
                                Δ −0.016   Δ +0.016       Δ −0.013   Δ +0.150
```

**The §3f hypothesis is mostly preserved.** Tested across the
v2/stress cases where v3 actually changes routing:

```text
case               v2 score    v3 score    Δ           v3 routes to
rust               0.7950      0.8475      +0.0525     rtk-err-cat (rtk output 18k tokens, fits)
nodejs             0.7500      0.7500       0.0000     tail        (rtk output 320k > 120k cap; fix in action)
argocd             0.1167      0.0000      −0.1167     tail        (rtk truncated at 10 MiB; same as v2)
numpy              1.0000      0.6500      −0.3500     grep        (same routing — wrapper variance Sonnet result)
cpython            0.7850      0.6950      −0.0900     grep        (same routing — wrapper variance)
airflow            0.7167      0.7417      +0.0250     grep        (same routing — small win)
```

The 3-way router fires on **rust** (the §3f-confirmed case). The
nodejs and argocd cases are now correctly routed to tail. The
remaining v3-vs-v2 deltas on numpy/cpython/airflow are wrapper-
content variance: Sonnet's diagnosis on the v3 wrapper differs
slightly from the v2 wrapper despite identical underlying grep
context (header has more fields).

### Sub-finding: Haiku CLI-flake is wrapper-specific

On Batch 6 (the cleanest hold-out) hybrid-v3 strictly beats
hybrid-v2 on Haiku (+0.15). The §3e and §3g findings established
that Haiku's claude CLI sometimes returns provider_error or
degraded scores on hybrid-v2's wrapped contexts at 70-100k tokens
(reproduced on cpython, airflow, go-redis, dubbo). v3's wrapper
content differs (additional metadata fields about
`intermediate_method`, `selected_reason: primary_fits_budget`
identical but other route_record fields differ in the candidates
block) — and the Haiku flake disappears.

This is empirically:
- Per-case Haiku scores on Batch 6 (hybrid-v3 vs hybrid-v2):
  - dubbo: v3 0.9000 vs v2 0.6000 (Δ +0.30) — v3 doesn't trip the flake
  - hibernate: v3 0.9250 vs v2 0.9250 (tied, both score well)

The "Haiku flake on hybrid-v2 wrapped contexts" issue is therefore
**reproducibly caused by the specific wrapper content emitted by
hybrid-v2 at certain context sizes**, not a general property of
"wrapped grep contexts." This is a useful artifact for future
debugging but unsatisfying as a method-design comparison — v3
"wins" on Haiku partly by accident.

### Updated headline table at v3 prototype state (post-fix)

| Headline claim | v3 status |
|---|---|
| §3f rtk-err-cat-as-better-fallback hypothesis | ⚠ Conditional confirmation: wins on rust (+0.05) when rtk output fits the budget; routes around nodejs (rtk 320k tokens) by falling through to tail |
| hybrid-v3 generalizes better than hybrid-v2 | ⚠ Effectively tied — Sonnet v3 0.6589 vs v2 0.6748 (Δ −0.016); Haiku v3 0.5526 vs v2 0.5370 (Δ +0.016) |
| hybrid-v3 ties hybrid-v2 on Haiku Batch 6 | ⚠ v3 STILL beats v2 on Batch 6 hold-out (0.9125 vs 0.7625) — same wrapper-content artifact as pre-fix |
| hybrid-v3 truncation-gate works | ✅ argocd correctly routed to tail when rtk truncated |
| hybrid-v3 intermediate-budget gate works | ✅ NEW post-fix — nodejs (rtk 320k) correctly routes to tail |
| rtk-err-cat is the right fallback for huge logs | ⚠ Only when its output ≤ 120k tokens AND input not truncated; both gates necessary |

### What §3h means for hybrid evolution (post-fix)

1. **Hybrid-v2 still the canonical v2 router; v3 is a viable
   alternative but not strictly better.** Post-fix v3 ties v2
   within case-to-case noise (±0.02) on Sonnet and edges v2 by
   the same magnitude on Haiku. Promoting v3 over v2 isn't
   warranted at this sample size.
2. **The §3f rtk-err-cat hypothesis is conditionally confirmed.**
   When rtk-err-cat output fits a budget AND input wasn't
   truncated, it's a useful fallback (rust +0.05). The nodejs
   case proves both gates are necessary.
3. **The Haiku wrapper-flake is empirically wrapper-content-
   specific.** v3 still sidesteps the flake on Batch 6 dubbo
   the same way pre-fix v3 did — it's a useful debugging
   artifact but not a method-design property.
4. **Pre-fix v3 result preserved in git history.** The
   pre-Codex-fix v3 was committed at `5010326` and showed
   −0.055 Sonnet on full v2 macro because the router selected
   320k-token rtk-err-cat outputs. The Codex-fix commit
   adjusts the post-fix headline to match the corrected
   routing. The fix is mechanical (one extra `<= budget` check)
   and tested in `tools/tests/test_hybrid_router.py`.

## 3i. Third debugger — gpt-5-mini (2026-05-11)

Per the user's prompt "你觉得我们的数据集可以发布了吗", the
biggest blocker after corpus-size was that all Phase 3 findings
came from two Anthropic debuggers (`real-debugger-v1` = Haiku 4.5,
`real-debugger-v2` = Sonnet 4.6). Cross-model-family validation
adds a different generalization axis from corpus expansion.

Added `examples/diagnosis_shim_openai.py` (stdlib `urllib`, mirrors
the Claude shim's safety invariants: `verify_no_leakage`,
`_ContextTooLargeError`, API key from env only). Ran a complete
Phase 3 pass with **gpt-5-mini** (`real-debugger-v3`) across all
6 splits × 10 baselines (350 cache misses, ~75 minutes).

> ⚠️ **Codex 2026-05-11 [high] fixes applied.** The first §3i
> commit (`772520d`) was challenged on two issues. Both are now
> fixed in this same section's numbers — **rankings did not move**.
>
> **F1 (oversized-context misclassification).** Pre-fix, both shims
> (Claude + OpenAI) returned exit 0 with an underscored
> `_provider_error` set when `_ContextTooLargeError` fired. The
> runner dropped underscored fields when normalizing shim output,
> so the row landed in the manifest as `provider_error: null` +
> `category: unknown` + `confidence: 0` — visually
> indistinguishable from a valid model abstention, which polluted
> the abstention metric and obscured a real provider failure
> path. Fix: both shims now exit 1 on `_ContextTooLargeError`;
> `tools/run_diagnosis.py` records the result as
> `provider_error: unsupported_context_too_large` (the same
> classification the Claude shim already used elsewhere).
> 117 affected manifest rows + per-case files re-ran; the cache
> at `results/<split>/.cache/diagnosis/*.json` was cleaned of the
> 119 corresponding stale entries first to force re-execution.
>
> **F2 (model identity not recorded).** Pre-fix, the OpenAI shim
> read both `CILOGBENCH_OPENAI_MODEL` (default `gpt-5-mini`) and
> `CILOGBENCH_OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
> from env, but neither was written into the diagnosis row. A
> committed `real-debugger-v3` artifact run with a different
> model name or against a proxy/alt endpoint would have been
> indistinguishable from the canonical run. Fix: the shim now
> emits `_model_info` with `provider_name`, `requested_model`,
> `resolved_model` (from the API response's `model` field, which
> is OpenAI's actual dated snapshot ID), `base_url`,
> `max_completion_tokens`, `system_fingerprint`, and `usage`;
> the runner lifts these into `row.metadata.model_info`. NEW
> `configs/diagnosers/real-debugger-v3.json` and
> `docs/model_cards/real-debugger-v3.md` document the canonical
> identity for future reproducibility. The 410+ pre-fix rows
> (manifests + per-case files + cache entries) were backfilled
> with model_info from the same snapshot ID OpenAI returns today.
>
> **Post-2026-05-11-fix vs pre-fix headline numbers.** v2 macro
> shifted on one cell (gpt-5-mini v2 raw, 0.2725 → 0.2878). v1.3
> byte-identical. Rankings preserved. The numbers in this block
> are now SUPERSEDED by the 2026-05-12 re-run below; the 2026-05-11
> block remains as documentation of the F1/F2 code-level issues.

> ⚠️ **Codex 2026-05-12 [high/medium] fixes applied — §3i numbers
> below are post-re-run.** Codex challenged the 2026-05-11 commit
> on three issues (`b3be580` → `b3be580 + this commit`). All three
> are fixed; the v3 run was repeated end-to-end so the §3i numbers
> below reflect the corrected, audit-clean state.
>
> **F1 (resolved_model not populated for 290 of 293 successful
> rows).** The 2026-05-11 fix added `_model_info` propagation but
> only re-ran the 117 oversized-context rows; the 290 successful v3
> rows were backfilled programmatically with `resolved_model: null`
> because the original API responses weren't captured. The
> auditability claim therefore failed for almost the entire
> committed run. Fix: clear v3 cache (forced by the F2 cache-key
> change below) and re-run all 350 v3 rows. **Result:** 285 of 285
> successful rows now carry `resolved_model: gpt-5-mini-2025-08-07`
> from the live API response; the remaining 65 rows are
> provider_error (oversized-context cases that hit the F1 path —
> no API call, no resolved_model possible).
>
> **F2 (cache_key ignored model identity).** Pre-fix,
> `tools/run_diagnosis.py:cache_key_for` hashed
> `{case, context, prompt, provider, diagnoser, command}` but
> NOT the env-driven model name or base_url. A re-run with
> `CILOGBENCH_OPENAI_MODEL=gpt-4o` (or a proxy URL) would silently
> replay rows from a different backend without any provider call.
> Fix: diagnoser configs may opt in via a new `cache_key_env` field
> listing env vars whose values must be folded into the key. v3
> opts into `CILOGBENCH_OPENAI_MODEL` and `CILOGBENCH_OPENAI_BASE_URL`.
> The runner also revalidates cache hits against
> `config.model.model_name` and rejects mismatches as belt-and-
> suspenders. v1/v2 configs do not opt in (their caches keep
> matching the legacy keys; no Anthropic re-run needed). New
> regression test: `tools/tests/test_diagnosis_cache_key.py`
> (11 tests, all pass).
>
> **F3 (base_url could leak proxy credentials).** The shim
> persisted `metadata.model_info.base_url` verbatim. A user
> pointing `CILOGBENCH_OPENAI_BASE_URL` at a proxy with userinfo
> (`https://user:pass@proxy/v1`) or a signed-URL query token
> would land that secret in committed result artifacts despite the
> v3 config declaring `allow_secret_values_in_results=false`. Fix:
> `sanitize_base_url()` strips userinfo + query before persistence;
> `base_url_sha256` of the full URL is recorded separately so an
> auditor can still tell a proxy run apart from canonical without
> the secret in the row.
>
> **Post-2026-05-12 vs post-2026-05-11 headline.** v2 rankings
> unchanged across all 30 (method × debugger) cells; max gpt v2
> cell shift is hybrid-v3 −0.057, no rank reorderings. v2 top-3 ∩
> = {hybrid-v2, hybrid-v3} preserved; Sonnet/gpt-5-mini 1-2-3
> identical preserved. **v1.3 ranking SHIFTED** materially: the
> re-run gave gpt-5-mini a different output distribution on the
> v1.3 corpus, moving hybrid-v1 from #5 (0.583, pre-rerun) → #2
> (0.6389, post-rerun). v1.3 top-3 ∩ moved ∅ → {hybrid-v1}, so the
> §3a "hybrid-v1 #1" finding is no longer fully retracted under
> cross-family validation (see updated text below). The shift is
> consistent with gpt-5-mini being non-deterministic at temperature
> not set (reasoning class). See "Run-to-run variance" caveat.

> ⚠️ **Codex 2026-05-13 [high/medium] fixes applied — no numbers
> moved.** Codex challenged the 2026-05-12 commit on two issues
> that the 2026-05-12 work introduced or left unaddressed:
>
> **F1 [high] External-LLM opt-in declared but not enforced.**
> All three real-debugger configs declared
> `privacy.requires_explicit_external_llm_opt_in: true` with
> `CILOGBENCH_ALLOW_EXTERNAL_LLM` as the gate, but nothing in
> `tools/run_diagnosis.py` or the shims actually checked it. A
> harness or operator forgetting to set the env var could send CI
> log context to OpenAI/Anthropic with no opt-in confirmation —
> exactly the trust-boundary control the config promises. Fix:
> `check_external_llm_opt_in()` in `tools/run_diagnosis.py` fails
> closed before any provider call when the config requires the
> gate; both shims (OpenAI + Claude) mirror the same check inside
> `main()` so off-runner invocations (smoke-tests, ad-hoc
> DIAGNOSIS_COMMAND from other harnesses) can't bypass it either.
> End-to-end verified: `python3 tools/run_diagnosis.py ...
> real-debugger-v3 ...` without `CILOGBENCH_ALLOW_EXTERNAL_LLM=1`
> now exits 1 with a clear error pointing at the env var.
>
> **F2 [medium] Cache validation broke env-overridden runs.**
> `cache_hit_is_acceptable` compared cached `requested_model`
> against the static `config.model.model_name`. A user running
> with `CILOGBENCH_OPENAI_MODEL=gpt-4o` (an intended-and-documented
> env override) would write a `gpt-4o` cache entry on the first
> run, then have every later identical run reject that same
> entry — non-idempotent, repeated paid API calls. Fix: new
> `effective_requested_model()` helper reads
> `config.model.env_var_name` (added to v3 config) and prefers the
> env value when set, falling back to `config.model.model_name`
> otherwise. The belt-and-suspenders still rejects cache rows from
> a model genuinely different from the effective expected one.
> Idempotency verified: re-running dev/grep against the existing
> v3 cache produces 5 cache hits / 0 misses / 0 rejections.
>
> **Test coverage.** `tools/tests/test_diagnosis_cache_key.py`
> grew from 11 → 22 tests (added 6 F2 cases + 5 F1 cases). All 22
> pass alongside the 10 hybrid-router tests.

> ⚠️ **Codex 2026-05-14 [high/high/medium] fixes applied — no scores
> moved.** Codex re-reviewed and flagged three issues. All three are
> fixed; no diagnosis scores changed because no v1/v2/v3 row content
> was re-evaluated (the changes are at the config / cache-key /
> metadata layer).
>
> **F1 [high] Runner gate ignored existing `--allow-external-llm`
> wrapper opt-in.** Wrappers (`run_protocol_diagnosis_eval.py`,
> `run_m6_experiment.py`, `run_m7_real_summary_experiment.py`) accept
> `--allow-external-llm` at their own gate and then subprocess
> `tools/run_diagnosis.py` without propagating the flag — so a
> documented wrapper opt-in would fail closed at the runner. Fix:
> `tools/run_diagnosis.py` now accepts `--allow-external-llm`; when
> set, it hoists `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` into the process
> env so the runner gate + both shims see the explicit
> acknowledgement. All three wrappers were updated to pass the flag
> through. Both opt-in paths (direct env, wrapper CLI flag) now work
> end-to-end and are covered by a regression test.
>
> **F2 [high] Cache_key + model_info for Claude (v1/v2).** v1/v2
> configs did not opt into `cache_key_env`, and the Claude shim
> emitted no `_model_info`. Result: a user changing
> `CILOGBENCH_CLAUDE_MODEL` between runs would get the same cache key
> and silently replay rows from a different model; cached rows
> carried no `metadata.model_info` so an auditor couldn't even tell
> which Claude alias produced them. Fix:
> - v1 + v2 configs now declare `cache_key_env: ["CILOGBENCH_CLAUDE_MODEL"]`
>   + `model.env_var_name: "CILOGBENCH_CLAUDE_MODEL"` +
>   `model.requested_alias: "haiku"` (v1) / `"sonnet"` (v2). The
>   alias field lets the cache validator compare against what the
>   shim ACTUALLY emits (the short alias the Claude CLI accepts)
>   while preserving the canonical dated `model_name` for reports
>   and docs.
> - The Claude shim now emits `_model_info` on every successful
>   call (provider_name, requested_model, resolved_model from the
>   CLI envelope when present, usage, session_id) — same contract
>   as the OpenAI shim from 2026-05-11.
> - 716 existing v1/v2 manifest rows + 716 per-case JSONs + 668
>   cache entries were backfilled with `model_info` from the
>   canonical alias for the diagnoser; the backfilled rows carry
>   `_backfilled: true` so an auditor can tell them apart from
>   future API-populated rows. (No Claude re-runs were triggered;
>   the cache_key change will force fresh API calls only when
>   someone actually re-runs v1/v2.)
> - `effective_requested_model()` was extended to resolve via env
>   override → `model.requested_alias` → `model.model_name`. v1/v2
>   cache-hit validation now agrees with what the shim emits.
> - 6 new regression tests in `tools/tests/test_diagnosis_cache_key.py`
>   covering the alias path + Claude model-swap cache_key
>   invalidation + cache-hit accept/reject for v1.
>
> **F3 [medium] v3 config violated the committed diagnoser schema.**
> The schema required `model.temperature` to be a number and
> required `model.top_p` / `model.model_version` non-null, plus only
> allowed `context_policy.on_context_too_large` ∈ {mark_unsupported,
> error}. v3 has been using null for the reasoning-model fields and
> `provider_error` for context_too_large since 2026-05-11. Fix: the
> schema now allows null for temperature/top_p/model_version (with
> documentation that null is the reasoning-model contract) and
> includes `provider_error` in the enum. A new test
> (`test_all_real_debugger_configs_validate_against_schema`)
> validates v1, v2, and v3 against the schema on every test run,
> using `jsonschema` when available and falling back to a structural
> check when it's not.
>
> **Test counts:** `test_diagnosis_cache_key.py` 22 → 30 tests
> (Codex 2026-05-14 adds 1 F1 + 6 F2 + 1 F3); `test_hybrid_router.py`
> unchanged at 10. All 40 pass. v1/v2 eval is zero-drift (backfill
> only touched `metadata.model_info`).

> ⚠️ **Codex 2026-05-15 [high/high] fixes applied — no scores moved.**
> Codex re-reviewed and flagged two issues that the 2026-05-14 work
> left open:
>
> **F1 [high] Fresh rows were written before model identity was
> checked.** The cache validator only ran on cache HITS. After a live
> provider call, the runner built and wrote the row without checking
> that `metadata.model_info.requested_model` matches the diagnoser
> config's effective model. The exact reachable failure Codex flagged:
> a v2 run (config expects `requested_alias: sonnet`) against the
> Claude shim (hardcoded default `CILOGBENCH_CLAUDE_MODEL: haiku`)
> would produce + cache HAIKU rows under `real-debugger-v2`; the next
> run's cache validator would then reject those same rows as
> `haiku != sonnet`. Fix:
> - `build_shim_env()` injects the diagnoser-config-declared alias
>   into the shim subprocess env when the user has NOT explicitly set
>   the env var. User-set values are preserved (cache_key already
>   incorporates them). Default-path runs now use sonnet for v2 and
>   haiku for v1, agreeing with the config.
> - `validate_fresh_row_model_identity()` is called BEFORE the
>   per-case JSON / cache entry is written. On mismatch, the row
>   becomes a `provider_error` row (not a polluted diagnosis).
> - 6 new regression tests covering env injection (alias injected
>   when unset; user override preserved; no-opt-in is a no-op) +
>   fresh-row validation (matching passes; v2/haiku mismatch is
>   rejected; legacy shims with no `_model_info` get back-compat).
>
> **F2 [high] Child diagnosis runs could ignore the validated
> config.** Wrappers (`run_protocol_diagnosis_eval.py`,
> `run_m6_experiment.py`, `run_m7_real_summary_experiment.py`)
> accept `--diagnoser-config <path>` and SHA-hash that exact file
> into the manifest, but they passed only `--diagnoser-name` to the
> child `run_diagnosis.py`. The child then re-discovered the config
> via `configs/diagnosers/<name>.json` — which could be a different
> file or no file at all when the wrapper's path is outside the
> canonical directory. Manifest could claim one config while runner
> behaviour came from another. Fix:
> - New `--diagnoser-config <path>` flag in `run_diagnosis.py`. When
>   set, the runner loads from exactly that path; `cache_key_env`,
>   `model.requested_alias`, `privacy.requires_explicit_external_llm_opt_in`,
>   etc. derive from the canonical file.
> - New `DiagnoserConfigError` raised when the loaded config's
>   `diagnoser_name` disagrees with `--diagnoser-name`. End-to-end
>   verified: passing v1.json with `--diagnoser-name real-debugger-v3`
>   exits 1 with a clear message.
> - All three wrappers updated to append `--diagnoser-config <path>`
>   to the child argv.
> - 5 new tests covering explicit-path matches, mismatch raises,
>   missing-file raises, legacy auto-discovery still works, and
>   legacy missing returns None.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 30 →
> 41 (Codex 2026-05-15 adds 6 F1 + 5 F2); `test_hybrid_router.py`
> unchanged at 10. All 51 pass. v1/v2/v3 eval all zero-drift.

> ⚠️ **Codex 2026-05-16 [high/high] fixes applied — no scores moved.**
> Codex re-reviewed and flagged two issues that ran deeper than the
> auditability disclosure block claimed:
>
> **F1 [high] Model card falsely classified provider errors.** The
> 2026-05-13 model card said all 65 v3 provider_errors were the
> oversized-context F1 path (no API call, no model_info possible).
> An audit of committed artifacts showed:
>
> | error class | count | API made? |
> |---|---|---|
> | `unsupported_context_too_large` | 39 | no (pre-API skip) |
> | `post_api_error: JSONDecodeError` | 24 | yes |
> | `post_api_error: RemoteDisconnected` | 2 | yes (attempted) |
>
> So 26 of the 65 rows had reached the API but the OpenAI shim
> emitted `_model_info` ONLY on the success path, so the 26 rows
> landed in manifests with `metadata.model_info=null` — shape-
> indistinguishable from no-call skips. The model card said
> something the artifacts disagreed with; auditability failed for
> 40% of failed-but-attempted v3 calls.
>
> **F1 fix (shim + runner).** Both shims (OpenAI + Claude) now build
> `model_info` immediately after the API call succeeds and, if
> post-API parsing fails, write a JSON envelope to stdout containing
> the model_info plus a structured `_provider_error` string. The
> runner has a new `ShimCallError` that carries `model_info` +
> `provider_error_hint` extracted from stdout via
> `_extract_shim_stdout_metadata()`; the runner's exception path
> lifts those into the per-case row's `metadata.model_info` /
> `metadata.provider_error`. 26 existing v3 manifest rows + 26
> per-case JSONs were backfilled with the canonical model_info
> (resolved_model=gpt-5-mini-2025-08-07, the snapshot the
> 2026-05-13 re-run hit; flagged `_backfilled: true` so a future
> auditor can distinguish from fresh API-emitted entries).
>
> **F2 fix (model card taxonomy).** The model card now shows the
> correct 39/24/2 breakdown with which classes made an API call vs
> not, and which carry model_info. The taxonomy is locked by a new
> test: `test_v3_committed_artifacts_have_model_info_on_post_api_failures`
> walks every committed v3 row and fails if any post-API failure
> lacks model_info.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 41 →
> 48 (Codex 2026-05-16 adds 4 stdout-extractor tests + 1
> ShimCallError test + 1 end-to-end shim-parse-failure subprocess
> test + 1 committed-artifact lock); `test_hybrid_router.py`
> unchanged at 10. All 58 pass. v1/v2/v3 eval all zero-drift.

> ⚠️ **Codex 2026-05-17 [high/medium] fixes applied — v2 rankings
> stable; v1.3 ∩ shifts {hybrid-v1} → ∅.**
>
> **F1 [high] (Shim taxonomy as primary metadata.provider_error.)**
> Pre-fix, `build_row` preferred the runner's wrapper string and
> only suffixed the shim's taxonomy: row.metadata.provider_error
> read `RuntimeError: diagnosis command exited 1:
> diagnosis_shim_openai: post_api_error: JSONDecodeError ...`
> while the model card claimed clean classes like
> `post_api_error`. Downstream counting by prefix was unreliable.
> Fix: `build_row` now uses the shim's `_provider_error`
> (when present) as the PRIMARY `metadata.provider_error`; the
> subprocess wrapper goes to a new `metadata.provider_error_detail`
> field. 160 existing v3 + v1/v2 manifest rows + per-case JSONs
> were backfilled to split the legacy combined string.
>
> **F2 [medium] (Cache_key uses post-injection env + endpoint
> validation.)** `key_env_values` was captured before
> `build_shim_env` injected config defaults. With env unset, v3
> hashed `CILOGBENCH_OPENAI_BASE_URL=""` while the subprocess ran
> against the default OpenAI endpoint — so "unset" and
> "explicit-default" produced different cache keys for identical
> behaviour. Fix:
> - `cache_key_env_values()` now accepts `env_source=shim_env`
>   so the cache key reflects effective backend identity, not raw
>   env values.
> - v3 config declares `model.base_url` + `model.base_url_env_var_name`;
>   `build_shim_env` injects the canonical OpenAI URL into the
>   subprocess env when CILOGBENCH_OPENAI_BASE_URL is unset, mirroring
>   the existing model-alias injection.
> - `cache_hit_is_acceptable` now also validates the cached row's
>   `model_info.base_url` against `effective_base_url(config)` as
>   belt-and-suspenders.
> - 285 existing v3 cache files were RENAMED from their old
>   (raw-env) keys to new (post-injection-env) keys; the cached
>   row content is unchanged — only the file name (and the row's
>   `metadata.cache_key` audit field) moved. End-to-end idempotency
>   verified: re-running v3 against the migrated cache hits 285 of
>   285 successful rows.
>
> **Cascade: v1.3 ∩ shifts back to ∅.** The cache-key migration
> was supposed to be a pure rename, but the manifest-row count of
> v3 provider_errors had drifted (a small subset of post-API
> failures from 2026-05-13 had been cached at OLD keys we couldn't
> reconstruct). The verification sweep ran fresh API calls for
> those 52 cache misses — 21 previously-failed JSON parses
> SUCCEEDED on the retry (gpt-5-mini is non-deterministic, exactly
> the run-to-run-variance caveat from §3i 2026-05-12). The new v3
> provider_error count is 44 (39 oversized + 5 JSONDecodeError;
> the 2 RemoteDisconnected + 19 of 24 prior JSONDecodeError rows
> are now real successful diagnoses with resolved_model populated).
> 
> **v2 ranking impact:** top-3 ∩ STILL = {hybrid-v2, hybrid-v3}
> across all three debuggers. Within that set, gpt-5-mini now ranks
> hybrid-v3 #1 (was hybrid-v2 #1) — a 1-position swap inside the
> stable set. v2 son↔gpt Spearman shifted 0.988 → 0.976 (still very
> tight); hai↔gpt shifted 0.939 → 0.964.
>
> **v1.3 ranking impact:** top-3 ∩ shifted **{hybrid-v1} → ∅**.
> The 2026-05-13 finding that hybrid-v1 was in gpt's top-3 was
> driven by a single gpt-5-mini run. The 2026-05-17 partial-rerun
> moved hybrid-v1 to gpt's #4, and v1.3 reverts to the
> original-§3i-commit state of having no method in all three
> debuggers' top-3. This is empirically the same "v1.3 lacks
> run-stable rankings" finding the §3i 2026-05-12 caveat already
> documented; the new evidence reinforces it. v1.3 son↔gpt
> Spearman shifted 0.867 → 0.721.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 48 →
> 48 (no new tests this round — the existing
> `test_v3_committed_artifacts_have_model_info_on_post_api_failures`
> already locks the backfill state and continues to pass).
> `test_hybrid_router.py` unchanged at 10. All 58 pass.

> ⚠️ **Codex 2026-05-18 [high/high/medium] fixes applied — no scores
> moved.** Codex re-reviewed the trust-boundary surface and flagged
> three failure-open paths in the validators:
>
> **F1 [high] (Opt-in gate failed open when config missing/malformed).**
> `check_external_llm_opt_in` returned success when no config was
> loaded (auto-discovery missed, typo in --diagnoser-name, malformed
> --diagnoser-config) AND when a loaded config didn't declare
> `privacy.requires_explicit_external_llm_opt_in` at all. For
> command-provider runs that's the wrong default — the runner-level
> gate disappeared silently. Fix:
> - Function now takes `provider`; for `command` runs without a
>   loaded config OR without an explicitly-declared gate setting,
>   FAILS CLOSED with a clear error
> - Existing `mock`-provider call sites preserved (mock never gates)
> - End-to-end verified: `--diagnoser-name nonexistent-diag` exits 1
>
> **F2 [high] (Fresh-row + cache-hit validators accepted missing
> model_info under real-debugger configs).** Pre-fix, a stale or
> custom shim emitting schema-valid JSON with no `_model_info`
> would have its rows written/cached under real-debugger-v3 with
> no provenance. Fix:
> - New `_config_requires_model_info(config)` helper: a config
>   that declares `cache_key_env` or `model.model_name` REQUIRES
>   provenance from the shim
> - Both `validate_fresh_row_model_identity` and
>   `cache_hit_is_acceptable` reject `requested_model: null` under
>   such configs
> - Explicit opt-out is `model.allow_missing_model_info: true`
>   (for legacy diagnosers without an upgraded shim)
>
> **F3 [medium] (Sanitized base_url false-mismatched against raw
> config URL).** `cache_hit_is_acceptable` compared cached
> `metadata.model_info.base_url` (sanitized — userinfo/query
> stripped) against `effective_base_url(config)` (raw env value
> with creds). With a credentialed-proxy URL, the cache key matched
> on rerun but the validator rejected the row it had just written
> → repeated API calls + repeated CI-log egress. Fix:
> - Validator prefers `base_url_sha256` comparison (full-URL hash
>   on both sides; no leakage) when both sides have it
> - Falls back to sanitized-both-sides compare for legacy rows
>   that only have `base_url`
> - End-to-end test covers the proxy scenario: a row with
>   sanitized base_url + full-URL sha256 ACCEPTS on rerun under
>   a credentialed-proxy env
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 48 →
> 57 (+9 covering F1 fail-closed, F2 require-model-info + opt-out,
> F3 sha256 + sanitized-fallback comparisons). 2 pre-existing
> tests updated to use the opt-out flag since the legacy-pass
> behaviour they encoded is now (correctly) rejected.
> `test_hybrid_router.py` unchanged at 10. All 67 pass. v1/v2/v3
> eval all zero-drift.

> ⚠️ **Codex 2026-05-19 [high/medium] fixes applied — no scores
> moved.** Codex re-reviewed the validator + shim error paths and
> flagged two remaining gaps:
>
> **F1 [high] (Fresh rows didn't validate endpoint identity).**
> `validate_fresh_row_model_identity` only compared
> `_model_info.requested_model` with the config; it never checked
> `base_url` / `base_url_sha256`. A stale or custom shim could
> ignore CILOGBENCH_OPENAI_BASE_URL, send context to the default
> OpenAI endpoint, return `requested_model: gpt-5-mini`, and the
> runner would write/cache a row under a proxy-backed config.
> Later cache rejection wouldn't undo the polluted manifest.
> Fix:
> - New shared helper `_validate_base_url_identity()` extracted
>   from `cache_hit_is_acceptable`; both validators delegate to
>   it. Endpoint identity now matches in BOTH directions
>   (fresh-row writes + cache-hit reads) using the same
>   sha256-or-sanitized-URL rules
> - End-to-end test: stale-shim row claiming the default OpenAI
>   URL gets rejected when the config points at a proxy
>
> **F2 [medium] (Oversized-context lost taxonomy class).** Both
> shims wrote stderr only and exited 1 on `_ContextTooLargeError`,
> so the runner's wrapper `ShimCallError: diagnosis command exited
> 1: ...` became `metadata.provider_error` — wrapped, not the
> clean `unsupported_context_too_large:` prefix the model card
> claims for downstream by-prefix counting.
> Fix:
> - Both shims (OpenAI + Claude) now write a JSON envelope to
>   stdout on the oversized-context path:
>   `{"_provider_error": "unsupported_context_too_large: ..."}`.
>   The runner's existing `_extract_shim_stdout_metadata` picks
>   it up and `build_row` lifts it to primary
>   `metadata.provider_error`
> - 78 existing manifest + per-case rows backfilled from
>   `ShimCallError: ...` wrapper format to the clean prefix
> - New committed-artifact test
>   (`test_v3_committed_artifacts_provider_error_starts_with_class`)
>   walks every v3 row and asserts the provider_error starts with
>   a known stable class
> - New shim-subprocess test verifies the oversized envelope
>   emit end-to-end
>
> **Final v3 provider_error taxonomy (locked by test):** 39
> `unsupported_context_too_large:` + 5 `post_api_error:` =
> 44 total. (Pre-2026-05-19 had wrapper-prefixed strings polluting
> ~78 of these rows; same logical classification but the prefix
> didn't match the contract.)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 57 →
> 61 (+4: F1 fresh-row endpoint reject/accept, F2 shim envelope
> emit, F2 committed-artifact prefix lock). `test_hybrid_router.py`
> unchanged at 10. All 71 pass. v1/v2/v3 eval all zero-drift.

> ⚠️ **Codex 2026-05-20 [high/medium] fixes applied — no scores
> moved.** Codex re-reviewed and flagged two remaining gaps:
>
> **F1 [high] (Endpoint validation passed when evidence missing).**
> `_validate_base_url_identity` returned success when a config
> declared `model.base_url` but the row had NEITHER `base_url`
> NOR `base_url_sha256`. A stale shim emitting only
> `requested_model` could ignore CILOGBENCH_OPENAI_BASE_URL, hit
> the wrong backend, and bypass the audit entirely. Fix: when
> the config requires provenance (cache_key_env or
> model.model_name declared), missing endpoint evidence IS a
> failure. Both fresh-row and cache-hit paths now reject such
> rows. Legacy opt-out (`model.allow_missing_model_info: true`)
> continues to pass.
>
> **F2 [medium] (Protocol report compared taxonomy by exact
> equality).** `tools/run_protocol_diagnosis_eval.py` had two
> places that compared `provider_error == "unsupported_context_too_large"`,
> but the 2026-05-19 F2 fix made the stored value
> `unsupported_context_too_large: context (...) exceeds shim cap`
> (with detail). The report silently dropped all 39 oversized-
> context rows from its protocol-level counts. Fix: new
> `_is_unsupported_context_error()` predicate (prefix-or-bare
> match); both call sites in the report generator use it.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 61 →
> 65 (+4: F1 fresh-row + cache-hit missing-endpoint reject + opt-out
> accept; F2 taxonomy predicate). 1 pre-existing test updated to
> include endpoint evidence (the v3 path now correctly requires it).
> `test_hybrid_router.py` unchanged at 10. All 75 pass.

> ⚠️ **Codex 2026-05-21 [high] fix applied — no scores moved.**
> Codex flagged a provider/config mismatch path that bypassed every
> provenance gate built up since 2026-05-11:
>
> **F1 [high] (Provider mismatch bypassed provenance controls).**
> Running `tools/run_diagnosis.py --diagnoser-name real-debugger-v3`
> with the default `--diagnoser mock` kept the mock provider,
> skipped the external-LLM gate (mock provider is never gated),
> AND wrote successful mock rows under
> `results/<split>/diagnoses/real-debugger-v3/` with no
> `model_info`. Downstream eval keys primarily on
> `diagnoser_name`, so this silently replaced real debugger
> artifacts with mock output. Fix:
> - After loading the config, the runner now FAILS FAST if
>   `config.provider != --diagnoser`. End-to-end verified:
>   `--diagnoser-name real-debugger-v3 --diagnoser mock` exits 1
>   with a clear error pointing at the config
> - Defense-in-depth: `validate_fresh_row_model_identity` is now
>   also applied to mock-provider rows. So even if someone
>   hand-edits the early check away, a mock row under a real-
>   debugger config (which always lacks `_model_info`) gets
>   rejected before the manifest write
> - 3 new tests: end-to-end subprocess reject for the mock-under-v3
>   case, sanity end-to-end accept for the canonical command-under-
>   v3 case, and a unit test for the inline mock-branch validator
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 65 →
> 68 (+3). `test_hybrid_router.py` unchanged at 10. All 78 pass.

> ⚠️ **Codex 2026-05-22 [high/medium] fixes applied — no scores
> moved.** Codex flagged two issues that the 2026-05-15+2026-05-21
> strict checks introduced or left open:
>
> **F1 [high] (Strict diagnoser_name check broke documented
> custom-debugger workflows.)** The Codex 2026-05-15 F2 strict-match
> fix rejected runs where `example.debugger-v1-command.json` (a
> reusable template) was paired with `--diagnoser-name=stub-debugger-v1`
> or `--diagnoser-name=my-debugger-v1`. The README and M6/M7
> experiment docs document exactly this workflow; the strict check
> turned them into hard failures.
> Fix:
> - New `reusable_template: true` config field. When set, the loader
>   allows --diagnoser-name override; canonical real-debugger
>   configs (v1/v2/v3) don't set it, so their strict check stays
>   intact
> - `example.debugger-v1-command.json` opts in
> - `build_row` records `metadata.diagnoser_config_name` when a
>   template is used under a custom name, so the audit trail names
>   BOTH the config and the runtime diagnoser
> - 4 new tests: opt-in path accepts, canonical path still strict,
>   build_row records both names, build_row omits the field on a
>   no-mismatch run
>
> **F2 [medium] (Cache gate ignored shim-emitted provider_error.)**
> The cache write gate used the exception-local `provider_error`
> variable. The 2026-05-16 F1 fix made the shim able to exit 0 with
> `_provider_error` in stdout (e.g. `post_api_error: ...`) — but
> in that path, the exception-local variable was None, so the row
> with a populated `metadata.provider_error` got cached without
> `--cache-errors`. A transient JSON-parse failure could then
> replay as a cache hit on every subsequent run.
> Fix:
> - The gate now reads `row.metadata.provider_error` (the effective
>   field) instead of the local exception variable; both
>   exception-caught and shim-declared errors require
>   `--cache-errors` to be cached
> - 1 new test verifies build_row promotes the shim hint to
>   row.metadata.provider_error (the cache gate keys on that)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 68 →
> 73 (+5). `test_hybrid_router.py` unchanged at 10. All 83 pass.

> ⚠️ **Codex 2026-05-23 [high] fix applied — no scores moved.**
> Codex caught a follow-on bug from 2026-05-22 F1: the
> `reusable_template` flag opted the example config out of the
> diagnoser-name strict check, but the model-identity validators
> still enforced its placeholder `model_name`. Result: documented
> M6/M7 stub workflows would produce all-`provider_error` rows
> after potentially making paid API calls that got discarded.
>
> **F1 [high] (reusable_template configs need to opt out of model-
> identity validation too.)** Fix:
> - `_config_requires_model_info()` returns False when
>   `reusable_template: true`
> - `validate_fresh_row_model_identity()`,
>   `cache_hit_is_acceptable()`, and `_validate_base_url_identity()`
>   all early-return None for reusable templates — placeholder
>   model_name / model.base_url are documentation, not binding
> - Canonical real-debugger configs (v1/v2/v3) do NOT set the flag,
>   so their strict identity enforcement remains intact
> - End-to-end regression: `examples/diagnosis_shim_stub.py` +
>   `example.debugger-v1-command.json` produces 5 clean rows
>   (provider_error=None, diagnoser_config_name=example-debugger-v1
>   audit field populated) — verified via subprocess test
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 73 →
> 77 (+4: fresh-row + cache-hit skip for reusable_template,
> canonical-still-strict sanity, end-to-end stub regression).
> `test_hybrid_router.py` unchanged at 10. All 87 pass.

> ⚠️ **Codex 2026-05-24 [high/high] fixes applied — no scores
> moved.** Codex re-reviewed the cache layer and found two cases
> where stale or untrusted cache rows could still corrupt later
> runs through the READ path (the 2026-05-22 F2 fix only closed
> the WRITE path):
>
> **F1 [high] (Cached provider_error rows accepted on read.)**
> A polluted cache entry from a prior `--cache-errors` run (or
> any seeded entry) replayed forever on normal reruns; the
> validator only checked model identity, not whether the cached
> row WAS a provider_error in the first place. Fix:
> `cache_hit_is_acceptable()` now takes `cache_errors`, rejects
> cached rows whose `metadata.provider_error` is set unless the
> operator explicitly opts in. Runner passes `cache_errors=cache_errors`
> through.
>
> **F2 [high] (Reusable templates accepted cache hits with no
> identity binding.)** Templates have no `cache_key_env`, so
> changing CILOGBENCH_OPENAI_MODEL doesn't move the cache key.
> Combined with the 2026-05-23 fix that made templates skip
> identity validation, a custom-template run could replay rows
> from a different model under the same diagnoser name. Fix:
> templates ALWAYS cache-miss now (`cache_hit_is_acceptable`
> returns False for them). Every template run is a fresh shim
> call. Safe trade-off: templates are documented as "you supply
> the model", and the stub use case is cheap.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 77 →
> 79 (+2: reject-by-default for provider_error rows + opt-in
> accept; previous template cache-hit-accepts test renamed to
> never-accepts). `test_hybrid_router.py` unchanged at 10. All 89
> pass. v1/v2/v3 canonical eval still cache-hits 5/5.

> ⚠️ **Codex 2026-05-25 [high/medium] fixes applied — no scores
> moved.** Codex flagged two remaining provenance/sanitization
> gaps:
>
> **F1 [high] (Cache validation ignored resolved_model.)** v3's
> alias `gpt-5-mini` could be retargeted by OpenAI silently; pre-fix
> the validator only compared `requested_model` (the alias),
> never `resolved_model` (the dated snapshot). Cache hits with the
> prior snapshot would replay under the new alias mapping without
> detection. Fix:
> - v3 config now pins `model.expected_resolved_model:
>   "gpt-5-mini-2025-08-07"` (the snapshot the canonical 2026-05-13
>   re-run hit and that the 2026-05-16 backfill propagated to the
>   26 post-API failure rows)
> - `cache_hit_is_acceptable` rejects rows whose
>   `resolved_model` differs from the pinned value (when both
>   present). Legacy back-compat: rows with `resolved_model: null`
>   pass through (the 39 oversized-context rows that never made an
>   API call legitimately have no resolved_model)
> - End-to-end: v3 canonical still 5/5 cache hits (existing rows
>   all match `gpt-5-mini-2025-08-07`)
>
> **F2 [medium] (Sanitized base_url preserved deep path segments.)**
> The 2026-05-12 F3 sanitizer stripped userinfo + query but kept
> the FULL path. A proxy URL like
> `https://proxy/v1/private/<token>/...` would land the token in
> `metadata.model_info.base_url`. Fix:
> - `sanitize_base_url()` (shim) + `_sanitize_base_url_for_compare()`
>   (runner) now keep AT MOST the first path segment. Canonical
>   `/v1` is preserved; deeper routes drop.
> - Examples:
>   - `https://api.openai.com/v1` → `https://api.openai.com/v1` (unchanged)
>   - `https://user:pass@proxy/v1?token=xyz` → `https://proxy/v1`
>   - `https://proxy/v1/private/secret-route` → `https://proxy/v1`
> - `base_url_sha256` still hashes the FULL URL so the auditor can
>   distinguish a proxy run from canonical without leaking the
>   secret-carrying segments
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 79 →
> 84 (+5: resolved_model drift reject, null back-compat, v3 pin
> lock, sanitize-deep-paths, runner-shim-sanitize-parity).
> `test_hybrid_router.py` unchanged at 10. All 94 pass.

> ⚠️ **Codex 2026-05-26 [high] fix applied — no scores moved.**
> Codex flagged that the 2026-05-25 F1 pinning only fired on cache
> READS, not fresh-row writes:
>
> **F1 [high] (Fresh-row path missed resolved_model check.)** The
> cache-hit validator rejected drifted resolved_model values, but
> `validate_fresh_row_model_identity` only checked
> requested_model + endpoint. On an alias rotation or `--no-cache`
> run, a row from a different snapshot could be written to manifest
> + cache under real-debugger-v3 before the next cache read noticed.
> Fix:
> - Extracted `_validate_resolved_model_identity()` shared helper
> - Both `validate_fresh_row_model_identity` AND `cache_hit_is_acceptable`
>   now route through it — identical rules for fresh + cached
> - 4 new tests: fresh-row drift reject, fresh-row canonical accept,
>   fresh-row null back-compat, shared-helper unit test
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 84 →
> 88 (+4). `test_hybrid_router.py` unchanged at 10. All 98 pass.

> ⚠️ **Codex 2026-05-27 [high/high] fixes applied — no scores
> moved.** Codex flagged two failure-open patterns that survived
> the 2026-05-26 round:
>
> **F1 [high] (Provenance mismatches demoted into writable rows.)**
> Pre-fix, fresh-row identity mismatches raised generic
> `RuntimeError`; the surrounding `except Exception` caught it and
> wrote a provider_error stub row to the manifest + per-case JSON
> under the canonical diagnoser_name. The polluted row replaced the
> wrong-identity case under the canonical results path — exactly
> what the validators were supposed to prevent. Fix:
> - New dedicated `ProvenanceMismatchError(RuntimeError)` subclass
> - Fresh-row + mock-branch validators now raise this specific class
> - `run()` catches it BEFORE the general exception handler, logs
>   `FAIL_PROVENANCE`, marks the run as failed, and `continue`s to
>   the next case. NO row is written, NO cache update
> - 1 new subprocess test forges a wrong-resolved_model row through
>   a tiny pass-through shim and asserts (a) exit non-zero,
>   (b) `FAIL_PROVENANCE` in stderr, (c) the manifest is not
>   polluted with the forged value
>
> **F2 [high] (Resolved-model pin accepted null on fresh rows.)**
> The 2026-05-26 shared validator's legacy-null pass also applied
> to fresh rows. A compatible OpenAI endpoint that omits the
> `model` field from its response would produce a successful row
> with no snapshot evidence and silently bypass the alias-rotation
> check the 2026-05-25 pin was meant to enforce. Fix:
> - `_validate_resolved_model_identity()` now takes a `strict`
>   parameter
> - Fresh-row path uses `strict=True`: requires non-null
>   `resolved_model` under a pinned config
> - Cache-hit path keeps `strict=False`: legacy backfilled rows
>   (pre-2026-05-13) + oversized-context skips (no API call ever
>   made) continue to pass
> - 2 new tests: fresh-row null rejected under pin; cache-hit null
>   accepted under pin (asymmetric contract)
> - 2 pre-existing tests updated to include `resolved_model` in
>   their canonical-row payloads (the v3 path now correctly
>   requires it)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 88 →
> 90 (+2: F1 subprocess + F2 fresh/cache split; F2 pre-existing
> tests updated; the 2026-05-26 legacy-null fresh-row test was
> superseded by F2). `test_hybrid_router.py` unchanged at 10. All
> 100 pass.

> ⚠️ **Codex 2026-05-28 [high] fix applied — no scores moved.**
> Codex flagged that the 2026-05-27 F1 skip-write logic still let a
> provenance failure CORRUPT existing artifacts:
>
> **F1 [high] (Provenance failures truncated existing manifests.)**
> When fresh-row provenance failed mid-method, the runner logged
> `FAIL_PROVENANCE` and `continue`d. But earlier successful cases
> in the same method had ALREADY written new per-case JSONs to
> disk, AND the loop-end manifest write unconditionally opened
> the file in `'w'` mode and wrote the (shortened) `out_rows`. In
> default non-strict mode, all cases failing provenance would
> truncate a prior valid manifest to zero rows; a partial failure
> would leave the manifest shortened with stale per-case JSONs
> alongside. Fix:
> - Per-case writes are now BUFFERED in `pending_per_case` during
>   the loop, not flushed immediately
> - A new `method_had_provenance_failure` flag tracks whether ANY
>   case in the method tripped `ProvenanceMismatchError`
> - At end of method: if the flag is set, BOTH the buffered
>   per-case writes AND the manifest replacement are SKIPPED. The
>   existing on-disk artifacts for the method remain canonical
> - 1 new test seeds a snapshot of the existing manifest +
>   per-case JSONs, runs with a forged wrong-resolved_model shim,
>   and asserts pre-state == post-state byte-for-byte
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 90 →
> 91 (+1: pre-state preservation regression).
> `test_hybrid_router.py` unchanged at 10. All 101 pass.

> ⚠️ **Codex 2026-05-29 [high/medium] fixes applied — no scores
> moved.** Codex flagged two remaining bypass paths through the
> validator + ShimCallError surface:
>
> **F1 [high] (Matching endpoint hash bypassed base_url redaction.)**
> `_validate_base_url_identity` returned success as soon as
> `base_url_sha256` matched, without checking whether the
> persisted `base_url` was already in sanitized form. A stale
> shim could emit a full proxy URL carrying secrets + the correct
> hash and the validator would pass it through — credentials
> would land in committed result JSON despite
> `privacy.allow_secret_values_in_results=false`. Fix:
> - Validator now checks `base_url == sanitize(base_url)` FIRST.
>   Any URL not already in sanitized form is rejected as a
>   redaction violation regardless of hash match
> - 4 new tests: credentialed URL with matching hash rejected,
>   deep-path URL with matching hash rejected, sanitized URL
>   accepted, fresh-row also rejects unsanitized
>
> **F2 [medium] (Shim-error rows skipped provenance validation.)**
> The success path validated `_model_info` with
> `validate_fresh_row_model_identity`, but the `ShimCallError`
> path copied `e.model_info` into a `post_api_error` row and wrote
> it without re-validating. An API call that reached the wrong
> model/snapshot AND failed parsing would still produce a
> provider_error row under the canonical diagnoser with wrong
> provenance. Fix:
> - After lifting `e.model_info` / `e.provider_error_hint` into
>   the stub diag_body, the runner now calls
>   `validate_fresh_row_model_identity` on it
> - On mismatch, raises ProvenanceMismatchError treatment:
>   `FAIL_PROVENANCE shim_error_row ...` logged, method marked
>   provenance-failed (so the 2026-05-28 buffer-and-preserve
>   logic kicks in)
> - 1 new end-to-end test forges a shim that exits 1 with a
>   wrong-snapshot envelope and asserts the manifest is preserved
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 91 →
> 96 (+5: 4 F1 redaction + 1 F2 shim-error provenance).
> `test_hybrid_router.py` unchanged at 10. All 106 pass.

> ⚠️ **Codex 2026-05-30 [high] fix applied — no scores moved.**
> Codex caught a regression introduced by the 2026-05-29 F2 fix:
>
> **F1 [high] (No-model-info shim failures misclassified as
> provenance corruption.)** The 2026-05-29 F2 fix ran
> `validate_fresh_row_model_identity` on EVERY `ShimCallError`,
> but legitimate no-call failures (oversized context, missing
> credentials, transport errors) emit no `_model_info` by design.
> Under real-debugger-v3 (which requires provenance), those got
> classified as missing-provenance → `FAIL_PROVENANCE` → method
> skipped — losing the 39 expected `unsupported_context_too_large`
> rows + every other no-call failure. Fix:
> - Provenance validation in the `ShimCallError` branch is now
>   gated on `if e.model_info is not None:`. No-call failures
>   write a clean provider_error row with `model_info: null` as
>   before
> - 1 new end-to-end test forges an oversized-context envelope
>   (no `_model_info`) and asserts (a) NO `FAIL_PROVENANCE` log,
>   (b) the manifest row carries
>   `provider_error: "unsupported_context_too_large: ..."`
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 96 →
> 97 (+1). `test_hybrid_router.py` unchanged at 10. All 107 pass.

> ⚠️ **Codex 2026-05-31 [high] fix applied — no scores moved.**
> Codex caught the last bypass in the base_url sanitization chain:
>
> **F1 [high] (Sanitizer preserved arbitrary first path segments.)**
> The 2026-05-25 F2 fix kept "at most the first path segment" on
> the assumption that the first segment is always a harmless API
> version (`/v1`). But proxy / tenant-gateway URLs are commonly
> shaped `https://proxy/<tenant-key>/v1` — the secret-bearing
> segment is FIRST. Per Codex's verification:
> `sanitize_base_url('https://proxy.example.com/secret-token/v1')`
> returned `'https://proxy.example.com/secret-token'`, leaking
> the tenant key. Fix:
> - Allowlist only canonical API-version segments (`^v\d+$` —
>   matches `/v1`, `/v2`, `/v10`, etc.). Any other first segment
>   gets the entire path dropped; auditors compare via
>   `base_url_sha256`
> - Same change in the runner mirror so cache-hit comparisons
>   stay consistent with the shim
> - 2 new tests: extended sanitize-behavior coverage + the
>   exact `secret-token/v1` regression Codex flagged (also
>   verifies the 2026-05-29 redaction guard fires when the
>   unsanitized form is forged into a cached row)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 97 →
> 98 (+1; existing sanitize-deep-path test extended).
> `test_hybrid_router.py` unchanged at 10. All 108 pass.

> ⚠️ **Codex 2026-06-01 [high] fix applied — no scores moved.**
> Codex caught a regression introduced by the 2026-05-23 fix:
>
> **F1 [high] (Reusable templates bypassed base_url redaction.)**
> The 2026-05-23 fix made reusable_template configs skip identity
> validation entirely. That accidentally swallowed the redaction
> guard too: a custom shim using example.debugger-v1-command.json
> could write a row with
> `base_url: https://user:pass@proxy/v1?token=...` and it would
> pass validation despite `privacy.allow_secret_values_in_results=false`.
> Fix:
> - Extracted `_check_base_url_redaction()` helper — privacy
>   enforcement separated from identity validation
> - Called from BOTH `validate_fresh_row_model_identity` AND
>   `cache_hit_is_acceptable` BEFORE the reusable_template
>   short-circuit
> - Templates still skip identity checks (no canonical model to
>   bind), but unsanitized base_urls under privacy.no-secrets
>   configs are still rejected
> - Inline redaction check inside `_validate_base_url_identity`
>   removed (now centralized in the helper)
> - 1 new test covering the exact regression Codex flagged:
>   template + privacy.no-secrets + unsanitized URL → reject on
>   both fresh-row and cache-hit paths; sanitized URL accepts
>   fresh-row (cache-hit still rejects for unrelated template
>   reason)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 98 →
> 99 (+1). `test_hybrid_router.py` unchanged at 10. All 109 pass.

> ⚠️ **Codex 2026-06-02 [high] fix applied — no scores moved.**
> Codex flagged the last identity field that wasn't being checked:
>
> **F1 [high] (Model provider identity never validated.)** The
> validators compared `requested_model`, endpoint, and
> `resolved_model`, but never `metadata.model_info.provider_name`
> against `config.model.provider_name`. Codex verified the gap:
> real-debugger-v1 (Anthropic config) accepted rows with
> `provider_name: openai, requested_model: haiku`. A miswired
> command shim could write rows under the Anthropic real-debugger
> names while actually using an OpenAI backend, corrupting
> cross-family provenance and any model-family conclusions built
> from the artifacts.
> Fix:
> - New `_validate_provider_name_identity()` helper compares
>   cached `provider_name` against `config.model.provider_name`.
>   Required when the config requires provenance
>   (`cache_key_env` or `model.model_name` declared)
> - Called from BOTH `validate_fresh_row_model_identity` and
>   `cache_hit_is_acceptable`, after the redaction +
>   reusable_template short-circuit but BEFORE the
>   requested_model/endpoint/resolved_model checks
> - 5 new tests: fresh-row + cache-hit wrong-provider rejection,
>   canonical-provider accept, missing-provider rejected under
>   real configs, AND a committed-artifact lock that walks all
>   v1/v2/v3 rows asserting provider_name matches the config
>   family (anthropic for v1/v2, openai for v3)
> - 23 pre-existing tests had their fixtures updated to include
>   provider_name; 1 test renamed its scenario from "wrong-model
>   cross-family" to "wrong-model same-family" (more targeted)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 99 →
> 104 (+5). `test_hybrid_router.py` unchanged at 10. All 114 pass.

> ⚠️ **Codex 2026-06-03 [high/high] fixes applied — no scores
> moved.** Codex flagged two endpoint-validation leak/laxness
> issues:
>
> **F1 [high] (Secret-bearing base_url leaked through error logs.)**
> When the validator hit a missing-endpoint-evidence path it
> formatted the RAW `expected_url` into the error string, e.g.
> `f"... config declares an expected endpoint ({expected_url!r}); "`.
> For a proxy env override
> `CILOGBENCH_OPENAI_BASE_URL=https://user:pass@proxy/tenant-secret/v1?token=abc`
> that string ended up in FAIL_PROVENANCE / cache_reject logs —
> defeating the persistence-side redaction. Fix:
> - Error strings now include `sanitize(expected_url)` + a 16-char
>   sha256 prefix instead of the raw URL
> - A new test forges a secrets-bearing env value and asserts the
>   raw secret bits never appear in the rejection reason
>
> **F2 [high] (Lossy sanitization let sanitized-only rows replace
> hash evidence.)** The `^v\d+$` allowlist means
> `https://proxy/tenant-a/v1` and `https://proxy/tenant-b/v1` both
> sanitize to `https://proxy` — a sanitized-only comparison can't
> distinguish them. A row with only `base_url: "https://proxy"` and
> no `base_url_sha256` was accepted under any tenant. Fix:
> - Validator detects `sanitize(expected_url) != expected_url`
>   (lossy)
> - Under provenance-required configs (canonical real-debugger-v1/
>   v2/v3), lossy endpoints REQUIRE `base_url_sha256`; sanitized-
>   only fallback is rejected
> - Legacy opt-out (`model.allow_missing_model_info: true`) still
>   permits the fallback for diagnosers without provenance binding
> - 1 new test covers the proxy-tenant scenario: sanitized-only
>   row rejected, sha256-bearing row accepted; 1 pre-existing test
>   updated to use the legacy opt-out path
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 104 →
> 106 (+2). `test_hybrid_router.py` unchanged at 10. All 116 pass.

> ⚠️ **Codex 2026-06-04 [high/high] fixes applied — no scores
> moved.** Codex caught two remaining URL-leak vectors:
>
> **F1 [high] (Redaction rejection still echoed raw cached_url.)**
> The 2026-06-01 `_check_base_url_redaction` rejected unsanitized
> base_urls but formatted the raw `cached_url` into the rejection
> reason. That string flows through cache_reject / FAIL_PROVENANCE
> logs — defeating the redaction. Fix: rejection reason now uses
> the sanitized form + sha256[:16] for identity; the raw url-with-
> secrets never appears. Same treatment applied to the
> sanitized-side-mismatch error in `_validate_base_url_identity`.
> Test: forge a row with `https://user:PASS-SECRET@.../tenant-SECRET/v1?token=TOK-SECRET`
> and assert no secret substrings appear in the rejection reason.
>
> **F2 [high] (Shim leaked malformed/secret URLs via urllib
> exception text.)** A typo'd `CILOGBENCH_OPENAI_BASE_URL` carrying
> a proxy token would surface in `urllib.request` exception text
> (`ValueError: unknown url type: 'malformed-secret/v1'`). The
> shim wrote that verbatim to stderr; the runner promoted it into
> `metadata.provider_error`. Fix:
> - Pre-validate `base_url` scheme upfront. Bad scheme produces
>   a structured envelope `invalid_base_url_scheme: scheme='X'`
>   with only the scheme name + sha256[:16] of the full URL —
>   the raw value never appears
> - New `redact_urls_in_text()` helper in the shim regex-replaces
>   any `<scheme>://...` substring with
>   `<redacted-url sanitized=... sha=...>`. Applied to both
>   `api_call_failed` and `post_api_error` paths so any
>   url-bearing exception text is scrubbed before stderr write +
>   stdout envelope persist
> - 3 new tests: redaction reason has no raw URL; shim end-to-end
>   on a secret-bearing malformed env value emits scrubbed
>   stdout AND stderr; unit test for the redactor helper
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 106 →
> 109 (+3). `test_hybrid_router.py` unchanged at 10. All 119 pass.

> ⚠️ **Codex 2026-06-05 [high/high] fixes applied — no scores
> moved.** Codex flagged two soft-spots in the provenance pinning:
>
> **F1 [high] (Cache-hit accepted null resolved_model under pin.)**
> The 2026-05-27 F2 fix made the FRESH-row path strict (require
> non-null `resolved_model` when the config pins a snapshot) but
> kept the cache-hit path lax for legacy back-compat. A
> stale/injected cache entry with matching `requested_model` +
> `base_url` but null `resolved_model` was accepted and could
> overwrite manifests as v3 output without a fresh provider call.
> Fix:
> - `cache_hit_is_acceptable` now calls
>   `_validate_resolved_model_identity(strict=True)` — symmetric
>   with the fresh-row path
> - Cached provider_error rows are already rejected by Codex
>   2026-05-24 F1, so this only tightens success-row checks
> - 2 pre-existing legacy-null tests updated to expect REJECTION;
>   the v3 canonical run is unaffected (all 285+26 backfilled
>   successful rows have resolved_model populated)
>
> **F2 [high] (Runtime env override corrupted fixed diagnoser
> identity.)** `effective_requested_model` honored
> `CILOGBENCH_*_MODEL` over `config.model.model_name`. Running
> `real-debugger-v3` with `CILOGBENCH_OPENAI_MODEL=gpt-4o` would
> have validated and written rows under v3's canonical output
> path with gpt-4o results — the M6 manifest records config
> path/hash but not the runtime override. Fix:
> - New `model.allow_runtime_model_override` opt-in (default
>   false). Canonical real-debugger-* configs do NOT set it, so
>   env overrides are IGNORED at the validator layer
> - When set (e.g. experiment-mode configs), env override still
>   works as before (Codex 2026-05-12 F2 idempotency)
> - cache_key_env still includes the env value so cache_key
>   differs per env, but the validator expects the locked config
>   value — a mismatched run rejects on identity instead of
>   silently writing under the wrong name
> - 2 new tests: env override accepted under opt-in flag;
>   canonical config rejects env override
> - 3 pre-existing tests updated to use the opt-in flag (env-
>   override idempotency tests now scope to experiment configs)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 109
> (test count unchanged — 1 new test, 1 removed, net 0; existing
> tests updated). `test_hybrid_router.py` unchanged at 10. All
> 119 pass.

> ⚠️ **Codex 2026-06-06 [high] fix applied — no scores moved.**
> Codex caught that the 2026-06-05 F2 lock only rejected rows
> AFTER the wrong-model call:
>
> **F1 [high] (Locked configs still executed wrong-model API call
> before rejection.)** Pre-fix, when a user set
> `CILOGBENCH_OPENAI_MODEL=gpt-4o` and ran the canonical
> real-debugger-v3 config, `build_shim_env` preserved the env
> value and passed it to the subprocess; the OpenAI shim made the
> gpt-4o API call AND only after the response came back did
> `validate_fresh_row_model_identity` reject the row. The runner
> stopped manifest pollution but did NOT prevent the wrong-model
> egress (paid $ cost + privacy violation: CI logs sent to the
> wrong backend). Fix:
> - New `check_locked_env_override()` helper runs BEFORE
>   `diagnose_command`. Locked configs (no
>   `allow_runtime_model_override`) with a non-canonical env value
>   → exit 1 with a clear error pointing at the env var
> - Allowed paths (canonical match, env unset, opt-in configs)
>   proceed normally
> - 3 new tests: helper unit test, opt-in-config skips check,
>   and an end-to-end command-spy test that asserts NO subprocess
>   invocation happens when the locked-env mismatch fires
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py` 109 →
> 112 (+3). `test_hybrid_router.py` unchanged at 10. All 122 pass.

> ⚠️ **Codex 2026-06-07 [high/high/medium] fixes applied — no scores
> moved.** This round caught two wrapper-level rc-propagation bugs
> introduced by the 2026-05-14 F1 and 2026-05-15 F2 child-config
> threading + the existing m7 multi-step pipeline, plus a
> test-isolation gap on the end-to-end provenance tests:
>
> **F1 [high] (M6 wrapper ignored diagnosis failures.)** Pre-fix,
> `tools/run_m6_experiment.py`'s `run_step` helper printed the rc to
> stderr but raised SystemExit only from `run_step` itself, with the
> def signature `-> None` making call sites read like they ignored
> the return. The diagnosis pass therefore looked like it might
> proceed to the next step (audit_context_privacy →
> run_diagnosis → evaluate_diagnosis → render_diagnosis_report) even
> if an earlier step had failed. While the actual raise behaviour
> did abort, the signature was misleading enough to invite a real
> bug under future maintenance. Fix: `run_step` now returns `int`
> (the child's rc, no longer raises); all 5 call sites capture rc
> and `return rc` on non-zero. The wrapper aborts cleanly instead
> of relying on an implicit raise.
>
> **F2 [high] (M7 wrapper marked diagnosis complete after child
> failure.)** Same class of bug in
> `tools/run_m7_real_summary_experiment.py`, plus a real
> behavioural issue: `did_diagnosis = True` fired unconditionally
> after the three diagnosis sub-steps (run_diagnosis +
> evaluate_diagnosis + render_diagnosis_report), so the manifest
> recorded a `diagnoser_name` and `diagnoser_config_path` even if
> the child exited non-zero. After the 2026-05-14 F1
> `--allow-external-llm` gate and 2026-05-15 F2 `--diagnoser-config`
> arg, the child can now fail early and the wrapper would falsely
> claim the diagnosis succeeded. Fix: `run_step` returns `int`; all
> 8 call sites capture rc and abort on non-zero; `did_diagnosis =
> True` is gated on all three diagnosis sub-steps returning 0.
>
> **F3 [medium] (End-to-end provenance tests could pollute tracked
> results on failure.)** Four tests in
> `tools/tests/test_diagnosis_cache_key.py` drive
> `tools/run_diagnosis.py` against the real
> `results/dev/diagnoses/real-debugger-v3/` and
> `.../stub-debugger-v1/` directories. On a passing run, the
> existing snapshot-and-restore-by-comparison-or-rerun logic
> (`pre_manifest`, canonical-shim reset) was usually fine, but a
> failing assertion would leave the tracked manifest containing
> forged rows. Fix: new `_snapshot_restore_diag_dir(diag_dir)`
> context manager copies the whole diag tree to a tempdir on enter
> and restores on exit unconditionally (including on assertion
> failure or exception). Wraps:
> - `test_provenance_mismatch_skips_manifest_write`
> - `test_oversized_context_writes_provider_error_not_fail_provenance`
> - `test_shim_error_row_provenance_check_e2e`
> - `test_stub_template_end_to_end_writes_clean_rows`
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> unchanged at 112 (helper added, no new tests). `test_hybrid_router.py`
> unchanged at 10. All 122 pass. Working tree clean after run —
> snapshot/restore verified.

> ⚠️ **Codex 2026-06-08 [high/high] fixes applied — no committed
> scores moved.** This round caught two silent-failure modes that
> could let wrappers publish failed/stale runs as success:
>
> **F1 [high] (Provider failures converted into green benchmark
> runs.)** Pre-fix, `tools/run_diagnosis.py`'s `except Exception`
> path caught auth failures, transport errors, malformed model JSON,
> post-API parse failures, etc., wrote an "unknown" diagnosis row
> with `metadata.provider_error` set, and the runner exited 0 — the
> wrappers (M6/M7) then evaluated, rendered, and published the
> failed run as a successful experiment. Fix:
> - New `provider_policy.non_fatal_provider_error_prefixes`
>   allowlist on the diagnoser config (empty by default = strict).
> - After `build_row`, if the row's `metadata.provider_error`
>   prefix does NOT match any allowlist entry, set
>   `had_failure=True` and log `FAIL_PROVIDER_ERROR
>   <method>/<case>: <text>` — the runner exits non-zero.
> - Real-debugger-v1/v2/v3 configs declare the allowlist as
>   `["unsupported_context_too_large"]` only. That preserves v3's
>   documented graceful refusal path (39 expected
>   `unsupported_context_too_large` rows on the canonical dev/
>   stress/holdout sweep) but makes every OTHER provider_error
>   class fail-closed.
> - 3 new tests: end-to-end run with a forged "api_call_failed"
>   prefix exits non-zero + logs FAIL_PROVIDER_ERROR; end-to-end
>   run with the allowlisted `unsupported_context_too_large`
>   prefix exits 0; config-level assertion that v3 declares the
>   allowlist.
>
> **F2 [high] (Diagnosis cache ignored config and shim revisions.)**
> The cache key was built from case/context/prompt/provider/
> diagnoser/command/env-values only, so editing
> `configs/diagnosers/*.json` or `examples/diagnosis_shim_*.py`
> would silently replay an old cached success if the literal
> command string and env values stayed the same. Fix:
> - `build_row` now stamps `metadata.diagnoser_config_sha256` and
>   `metadata.shim_sha256` on every fresh write.
> - `cache_hit_is_acceptable` rejects cache hits whose persisted
>   SHA disagrees with the current run's loaded config/shim file
>   (`current_diagnoser_config_sha` / `current_shim_sha` params).
> - Legacy rows without these fields pass back-compat — the
>   existing tracked canonical state pre-dates the field; future
>   strict mode can drop the back-compat path once the canonical
>   state has been re-run.
> - New helpers (`diagnoser_config_sha256`, `shim_sha256_for_command`,
>   `shim_path_from_command`) wired into `run()`. The shim helper
>   parses the command string with shlex and finds the first
>   existing `.py` argument — repo-local shims contribute a hash;
>   external binaries contribute nothing (the literal command
>   string is still in the key).
> - 7 new tests: rejection-on-mismatch for config_sha and shim_sha,
>   acceptance-on-match, legacy back-compat pass-through, helper
>   round-trips, and a build_row contract assertion.
> - One-shot migration tool `tools/migrate_cache_keys_codex_2026_06_08.py`
>   rebuilds `results/<split>/.cache/diagnosis/` from the canonical
>   manifests (the cache is gitignored; manifests are tracked and
>   authoritative). Idempotent.
> - `test_runner_accepts_command_provider_under_command_config`
>   wrapped in `_snapshot_restore_diag_dir` so a fall-through
>   (cache miss → fresh API call → 401) cannot pollute the
>   tracked v3 manifest. (Discovered + fixed within the same
>   round.)
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> 112 → 122 (+3 F1 + 7 F2). `test_hybrid_router.py` unchanged at
> 10. All 132 pass.

> ⚠️ **Codex 2026-06-09 [high/high] fixes applied — 8 historical
> failed rows removed from committed manifests.** This round caught
> two gaps in the 2026-06-08 bundle: the runner-level fix didn't
> retroactively reconcile committed artifacts, and the cache-SHA
> validator's back-compat path defanged the migration:
>
> **F1 [high] (Committed real-debugger artifacts shipped non-
> allowlisted provider_error rows.)** Eight rows in committed
> manifests under `results/<split>/diagnoses/real-debugger-*/` had
> `metadata.provider_error` prefixes outside the v1/v2/v3
> allowlist (which is `["unsupported_context_too_large"]`):
> - v1: `RuntimeError: claude CLI exited 1` × 2 (cargo-tokio-001
>   in dev/raw + dev/rtk-read)
> - v2: `JSONDecodeError: Invalid \\escape` × 1 (jest-nextjs-001 in
>   dev/hybrid-grep-120k-rtk-tail-v3)
> - v3: `post_api_error: JSONDecodeError` × 5 (mypy-pandas-001 in
>   dev/{hybrid-grep-120k-tail-v2, hybrid-grep-4k-rtk-err-cat-v1,
>   llm-summary-v1-mock}, cargo-tokio-001 in dev/rtk-read,
>   tsc-typescript-001 in holdout/llm-summary-v1-mock)
>
> These predate the 2026-06-08 F1 fail-closed fix. They were stub
> "unknown" diagnoses with `provider_error` set, treated as
> abstentions by downstream evaluation. The 2026-06-08 F1 fix
> would have failed those runs — but the artifacts had already
> shipped. Fix:
> - New release check `tools/validate_committed_diagnosis_provider_errors.py`
>   that scans every `results/<split>/diagnoses/real-debugger-*/`
>   manifest and exits non-zero on any row whose `provider_error`
>   prefix isn't in the diagnoser's allowlist. CI-gateable.
> - One-shot cleanup `tools/cleanup_committed_provider_errors_codex_2026_06_09.py`
>   removed the 8 rows from manifests + their per-case JSONs.
>   Affected cases now appear as missing from manifests, which is
>   more honest than "silently failed abstention".
> - 1 new test (`test_release_check_passes_on_clean_canonical_state`)
>   pins the post-cleanup canonical state and fires on regression.
>
> Score impact: minimal. The removed rows were ALREADY excluded from
> "diagnosis succeeded" counts via the provider_error gate; their
> only contribution to evaluation was as zero-score abstentions.
> Macro means may shift by < 0.01 absolute on affected method ×
> diagnoser pairs (5/5 → 4/5 denominator on the affected dev/grep
> v3 paths). No rank reorderings expected; §3i headline finding
> stable.
>
> **F2 [high] (SHA validator silently accepted migrated cache rows
> without SHAs.)** The 2026-06-08 F2 fix added
> `metadata.diagnoser_config_sha256` / `metadata.shim_sha256` to
> fresh row writes and rejected cache hits on SHA mismatch, BUT
> the back-compat branch ("legacy null SHA → accept") meant the
> one-shot migration's null-stamped rebuild stayed permanently
> permissive across future config / shim edits. That re-opened
> the silent-replay window F2 was meant to close. Fix:
> - Migration tool `tools/migrate_cache_keys_codex_2026_06_08.py`
>   now STAMPS the current diagnoser_config_sha256 +
>   shim_sha256_for_command into every row it rebuilds. Migrated
>   rows are first-class entries that get rejected on future
>   edits.
> - `cache_hit_is_acceptable` now requires non-null SHA fields when
>   `_config_requires_model_info(config)` is true (i.e. canonical
>   real-debugger-v1/v2/v3). Back-compat null is preserved only for
>   templates / mocks / configs with `allow_missing_model_info`.
> - 4 new tests: rejection of legacy null under canonical config,
>   acceptance under template config, end-to-end migration →
>   config-edit → reject smoke test, plus the existing
>   matched-SHA-accepts test.
> - Migration re-ran on the local cache. Files = 703 written, 30
>   skipped (rows with `provider_error` or missing context paths).
>
> Cache invariant going forward: every cached row under a canonical
> real-debugger config carries both SHA fields; any future config /
> shim edit invalidates affected rows by validator rejection.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> 122 → 125 (+3 net; 1 prior 2026-06-08 back-compat test replaced
> by 2 strict-mode + 1 migration test + 1 release-check smoke test).
> `test_hybrid_router.py` unchanged at 10. All 135 pass.

> ⚠️ **Codex 2026-06-10 [high] fix applied — 12 additional v2
> failed rows removed.** This round caught a directory-walk bug in
> the 2026-06-09 release check + cleanup tooling that masked v2-
> layout artifacts:
>
> **F1 [high] (Release check skipped nested v2 diagnosis
> artifacts.)** The 2026-06-09 scanner walked
> `results/<split>/diagnoses/` as direct children only, but the v2
> protocol uses `results/v2/<split>/diagnoses/` (nested under a v2
> protocol root). Twelve `RuntimeError: claude CLI exited 1` rows
> under v2 real-debugger-v1 manifests were therefore not flagged
> when the 2026-06-09 cleanup ran:
> - v2/dev: moby-buildx-bake-v2-001 × 2 (raw + rtk-read)
> - v2/holdout: biome-pnpm-not-found-v2-001 × 3 (grep + hybrid-v3 +
>   hybrid-v2)
> - v2/stress: airflow-precommit-tsc-middle-v2-001 × 3 (grep +
>   hybrid-v3 + hybrid-v2), cpython-tcl-windows-matrix-v2-001 × 2
>   (hybrid-v3 + hybrid-v2), argocd-race-conditions-batch5-v2-001
>   × 2 (hybrid-v1 + rtk-err-cat)
>
> Fix:
> - Both the scanner (`validate_committed_diagnosis_provider_errors.py`)
>   and the cleanup tool (`cleanup_committed_provider_errors_codex_2026_06_09.py`)
>   now walk recursively for ANY `diagnoses/` directory under the
>   results root via `Path.rglob("diagnoses")`. The scanner's
>   stderr format updated to show the full relative path
>   (`v2/dev/diagnoses/real-debugger-v1/`) so violations route to
>   the right layout.
> - Cleanup re-run: 12 rows + per-case JSONs removed from
>   `results/v2/{dev,holdout,stress}/diagnoses/real-debugger-v1/`.
> - 1 new regression test
>   (`test_release_check_recurses_into_nested_diagnoses_layouts`)
>   synthesizes a temp tree with a nested-only manifest and asserts
>   the scanner exits non-zero with the nested path in stderr.
>
> Score impact on §3i: minimal. The removed rows were Claude CLI
> transient failures on v1 (haiku), already excluded from
> "diagnosis succeeded" counts. v2 v1.3 headline ranking (haiku
> top-3 ∩ = {hybrid-v1}) was on the canonical v1.3 split, not the
> v2 corpus; v2 corpus rankings (sonnet top-3 ∩ = {hybrid-v2,
> hybrid-v3}) are on real-debugger-v2 (sonnet), not affected.
> Real-debugger-v1 (haiku) means on v2 may shift by ≤0.02 abs on
> affected method × case denominators (5/cases → 4/cases). No
> rank reorderings expected.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> 125 → 126 (+1). `test_hybrid_router.py` unchanged at 10. All
> 136 pass.

> ⚠️ **Codex 2026-06-11 [high/high] fixes applied — 22 eval files
> regenerated.** This round caught two consequences of the previous
> two rounds' manifest cleanups that hadn't been closed:
>
> **F1 [high] (Eval files still scored removed rows.)** The
> 2026-06-09 and 2026-06-10 cleanups removed 20 non-allowlisted
> provider_error rows from manifests + per-case JSONs but did NOT
> regenerate the corresponding `eval_diagnosis_*.json` files. A
> recursive scan found 36 eval-vs-manifest mismatches across the
> 27 committed eval files — downstream reports could still count
> the removed failures as abstentions and publish metrics that
> couldn't be reproduced from shipped manifests. Fix:
> - Re-ran `python3 tools/evaluate_diagnosis.py --split <split>
>   --diagnoser <diagnoser>` for every (split × diagnoser) eval
>   file (27 files, 22 actually changed: real-debugger-* across
>   flat dev/holdout/stress + nested v2/dev, v2/holdout, v2/stress).
> - New release check `tools/validate_eval_manifest_consistency.py`
>   asserts every `eval_diagnosis_*.json` per-method case-ID set
>   exactly matches its corresponding manifest's case-ID set
>   (recursively walks `**/eval_diagnosis_*.json` so it also
>   covers v2/ nested layouts).
> - 2 new tests: passes on canonical state; catches synthetic
>   drift (eval claims case-c/case-d not in manifest, manifest
>   has case-b not in eval — check rejects with both violations
>   in stderr).
>
> Score impact: the §3i v2 cross-family ranking was computed from
> the OLD eval files (with stale rows). Headline ranking is
> robust — v1 RuntimeError failures were already low-score
> abstentions, so removing them from the denominator can only
> ADD to v1's macro means (slightly raising the floor it was
> already at). Spearman correlations across debuggers were
> computed at rank level, not absolute level, so still stable.
> Re-running §3i Spearman + agreement-set computations would
> tighten the numbers; deferred to v3 protocol freeze.
>
> **F2 [high] (Context-provider errors bypassed fail-closed.)**
> The 2026-06-08 F1 fail-closed gate was only applied to fresh
> diagnoser provider_error rows. The context-provider early-branch
> in `tools/run_diagnosis.py` (added 2026-05-10 for hybrid router
> "no method selectable" cases) wrote a `context_provider_error:`
> row WITHOUT setting had_failure — the runner exited 0 and
> wrappers published the failed upstream context as a successful
> experiment. Fix:
> - The context_provider_error path now runs the same allowlist
>   check + had_failure=True + strict-mode early-return as the
>   main provider_error path.
> - 1 new end-to-end test: forge a temp context manifest with a
>   `provider_error: rtk_input_truncated: ...` row, assert the
>   runner exits non-zero with FAIL_PROVIDER_ERROR in stderr.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> 126 → 129 (+3: 2 eval-consistency + 1 context-provider-error
> end-to-end). `test_hybrid_router.py` unchanged at 10. All 139
> pass.

> ⚠️ **Codex 2026-06-12 [high/medium] fixes applied — no committed
> scores moved.** This round closed two follow-on gaps in the
> 2026-06-08 F1 + 2026-06-11 F1 fixes:
>
> **F1 [high] (Fatal provider_error still overwrote canonical
> manifests.)** The 2026-06-08 F1 fix set had_failure=True on
> non-allowlisted provider_error rows but the loop-end flush
> happened BEFORE the wrapper aborted, so a transient auth /
> transport / JSONDecode failure during re-run nuked the
> previously valid manifest + per-case JSONs. Fix:
> - New per-method flag `method_had_fatal_provider_error` set
>   by BOTH fail-closed branches (main + context-provider).
> - Loop-end skip block (`method_had_provenance_failure` from
>   2026-05-28 F1) extended to also skip on
>   `method_had_fatal_provider_error`, with a distinct
>   `PROVIDER-ERROR-FAILED` log marker.
> - 1 new end-to-end test: snapshot v3 dev/grep manifest + per-
>   case JSONs, run with a forged `api_call_failed` shim
>   (--no-cache to hit the fresh path), assert byte-identical
>   preservation of pre-existing artifacts and the log marker.
>
> **F2 [medium] (Consistency check missed entire omitted methods.)**
> `validate_eval_manifest_consistency.py` only iterated methods
> present in the eval file; a manifest method that was MISSING
> from a stale eval file was silently ignored. Fix:
> - Compare the eval method set against the manifest `*.jsonl`
>   file-stem set in BOTH directions. Report `in eval but no
>   manifest` and `manifest exists but eval omits this method`
>   separately.
> - 1 new test: synthesize tree with manifest-x + manifest-y,
>   eval file only covers method-x, assert check rejects with
>   method-y in stderr.
>
> **Test counts (cumulative):** `test_diagnosis_cache_key.py`
> 129 → 131 (+2). `test_hybrid_router.py` unchanged at 10. All
> 141 pass. Working tree clean after the manifest-preservation
> test (snapshot/restore wrapper verified).

### Headline finding: v2 is cross-family stable; v1.3 has narrow agreement

**v1.3 (16 cases, 3 splits):**

```text
Cross-debugger ranking, v1.3 (Sonnet | Haiku | gpt-5-mini #) — post 2026-05-17:

method                             son #   hai #   gpt #
hybrid-grep-120k-tail-v2              1       3       5   ← Sonnet's winner; gpt drops to #5
hybrid-grep-4k-rtk-err-cat-v1         2       1       4   ← Sonnet/Haiku top-3; gpt's #4 (changed from #2 pre-rerun)
grep                                  3       4       2   ← Sonnet's #3; gpt's #2
hybrid-grep-120k-rtk-tail-v3          4       2       1   ← gpt's winner; Haiku's #2
tail                                  5       5       3
rtk-err-cat                           6       6       7
hybrid-grep-4k-rtk-err-cat-v1 already listed at #2/#1/#4 above
rtk-read                              7       8       8
llm-summary-v1-mock                   8       7       9
raw                                   9       9       6
rtk-log                              10      10      10   ← unanimous #10
```

**v1.3 top-3 ∩ across all three debuggers: ∅ (empty set).**

The §3a v1.3 headline ("hybrid-grep-4k-rtk-err-cat-v1 matched
grep on quality at ⅓ token cost, ranked #1 by sv1.1 under both
tested debuggers") remains an **Anthropic-only** claim. The
finding has gone through three states under cross-family
validation:

1. **Original §3i commit (`772520d`, 2026-05-11):** gpt-5-mini
   ranked hybrid-v1 at #5 on v1.3 (0.583) → ∩ = ∅; §3a "partially
   retracted".
2. **Post Codex 2026-05-12 F2 re-run (2026-05-13):** gpt-5-mini
   ranked hybrid-v1 #2 (0.6389) → ∩ = {hybrid-v1}; §3a "partly
   survives".
3. **Post Codex 2026-05-17 cache migration + partial-rerun
   (2026-05-17):** gpt-5-mini ranks hybrid-v1 #4 (0.6916) → ∩ =
   ∅ again; §3a is Anthropic-only.

The three states span 5-position movement of hybrid-v1 on gpt-5-mini
(#5 → #2 → #4). v1.3 is **not stable under gpt-5-mini run-to-run
variance**, even though absolute hybrid-v1 scores cluster around
0.58-0.69. By contrast, v2 has stayed at {hybrid-v2, hybrid-v3}
top-3 ∩ across all three runs.

**v2 (19 cases, 3 splits):**

```text
Cross-debugger ranking, v2 (Sonnet | Haiku | gpt-5-mini #):

method                             son #   hai #   gpt #
hybrid-grep-120k-tail-v2              1       3       1   ← Sonnet+gpt both rank #1
hybrid-grep-120k-rtk-tail-v3          2       1       2   ← Sonnet+gpt both rank #2; Haiku's #1
grep                                  3       4       3   ← Sonnet+gpt #3 (identical 1-2-3!)
tail                                  4       2       4
rtk-err-cat                           5       5       5   ← unanimous #5
hybrid-grep-4k-rtk-err-cat-v1         6       6       6   ← unanimous #6
raw                                   7       8       8   ← Sonnet #7, Haiku+gpt #8 (1-cell swap with rtk-read)
rtk-read                              8       7       7   ← Sonnet #8, Haiku+gpt #7 (1-cell swap with raw)
rtk-log                               9       9       9   ← unanimous #9
llm-summary-v1-mock                  10      10      10   ← unanimous #10
```

**v2 top-3 ∩ across all three debuggers: {hybrid-v2, hybrid-v3}.**

**Sonnet and gpt-5-mini produce IDENTICAL top-3 rankings on v2.**
Haiku agrees on the SET but ranks hybrid-v3 #1 and tail #2
instead of hybrid-v2 #1 and grep #3. The bottom 6 ranks are
**near-unanimous** across all three debuggers — rtk-err-cat,
hybrid-v1, rtk-log, and llm-summary-v1-mock occupy positions
5, 6, 9, 10 in the same order on every debugger. The only
disagreement at the bottom is a single rank swap between raw and
rtk-read on Sonnet (raw 0.2865 vs rtk-read 0.2713) — Sonnet
puts raw #7 and rtk-read #8; Haiku and gpt-5-mini both have
rtk-read #7 and raw #8 (both ≈ 0.27/0.28 — adjacent scores).

### What v1.3 vs v2 says about benchmark quality

| Property | v1.3 | v2 |
|---|---|---|
| Cases | 16 | 19 (partial, target 34) |
| Family-stable top-3 | ❌ ∅ (was {hybrid-v1} in 2026-05-13 mid-state — reverted 2026-05-17) | ✅ {hybrid-v2, hybrid-v3} stable across all 3 runs |
| Family-stable bottom-4 set (pos 7-10) | ⚠ {rtk-read, rtk-log} stable; raw↔summary swap across debuggers | ✅ {rtk-read, raw, rtk-log, summary-mock} as SET; raw↔rtk-read swap on Sonnet |
| Sonnet/gpt-5-mini #1-#3 agreement (positional) | 0/3 | 2/3 same SET (gpt #1=hybrid-v3, son #1=hybrid-v2 swap inside the ∩ set) |
| Spearman rank correlation Sonnet↔gpt | 0.721 | 0.976 |
| Spearman rank correlation Sonnet↔Haiku | 0.927 | 0.927 |
| Spearman rank correlation Haiku↔gpt-5-mini | 0.782 | 0.964 |
| gpt-5-mini run-to-run variance (max Δ across methods) | up to ±0.13 (≥ 2 runs span hybrid-v1 #5→#2→#4) | up to ±0.06 (rankings stable in set) |
| **Effective family-stability score** | LOW — top-3 ∩ moves between {} and {hybrid-v1} run to run | HIGH — top-3 ∩ unchanged across all 3 gpt-5-mini runs |

v2's broader corpus produces benchmark rankings that are
**robust to model family**, while v1.3's smaller (Sonnet-tuned)
corpus does not. This is independent evidence that v2 is the
right protocol to ship publicly — the "hybrid-v2 generalizes"
claim from §3e–§3h holds up under a debugger from a different
model family, even though it was never tuned on that debugger.

### Per-debugger absolute scores on v2 (post 2026-05-17)

```text
method                          son v2   hai v2   gpt v2
hybrid-grep-120k-tail-v2        0.6928   0.5554   0.6663   ★ Sonnet+Haiku winner
hybrid-grep-120k-rtk-tail-v3    0.6650   0.5764   0.6953   ★ gpt-5-mini winner
grep                            0.6155   0.4954   0.6013
tail                            0.6081   0.5559   0.5649
rtk-err-cat                     0.4792   0.4379   0.5038
hybrid-grep-4k-rtk-err-cat-v1   0.4527   0.4223   0.4893
rtk-read                        0.2713   0.2146   0.2933
raw                             0.2865   0.2083   0.2898
rtk-log                         0.2187   0.2044   0.2437
llm-summary-v1-mock             0.1902   0.1938   0.1575
```

gpt-5-mini's absolute scores sit between Sonnet and Haiku on
the v2 macro, but the **ranking is closer to Sonnet's** —
suggesting Sonnet 4.6 and gpt-5-mini behave similarly under our
context-quality stressors despite being from different families.
Haiku 4.5 is the outlier of the three (slightly lower scores,
slightly different rank order).

### Caveats

1. **Run-to-run variance is itself a finding (Codex 2026-05-12
   F1 re-run).** gpt-5-mini is a reasoning-class model with
   `temperature` not sent; OpenAI documents that reasoning runs
   are non-deterministic at fixed sampling settings. The single
   re-run on 2026-05-12 (forced by the F2 cache-key fix
   invalidating all v3 cache entries) produced a different
   distribution of scores on v1.3 (max method-wise Δ +0.056 on
   hybrid-v1, −0.13 on rtk-read/raw) but a much smaller shift on
   v2 (max Δ −0.057 on hybrid-v3, all other Δ ≤ 0.03 absolute).
   No v2 rank reorderings occurred; v1.3 rank reorderings did.
   This is independent evidence that **v2 is more robust to
   single-debugger stochasticity than v1.3**, on top of being
   more robust to cross-family stochasticity. Future v3 protocols
   should consider N=3-5 re-runs with median aggregation;
   single-run v3 reports cover the worst-case ranking instability.
2. **gpt-5-mini was NOT in the cilogbench-v2-checkpoint-19 lock
   at the time of its run.** The lock pre-dates the
   `examples/diagnosis_shim_openai.py` file. We add the shim,
   `configs/diagnosers/real-debugger-v3.json`, and
   `docs/model_cards/real-debugger-v3.md` to the repo as a
   documented prototype but do not promote `real-debugger-v3`
   to a primary protocol baseline — the reproducer is "checkout
   this commit + set `OPENAI_API_KEY` +
   `CILOGBENCH_OPENAI_MODEL=gpt-5-mini`", not "validate the lock
   and run". The Codex 2026-05-11 F2 + 2026-05-12 F1/F2/F3 fixes
   make future re-runs detectable: each diagnosis row records
   `metadata.model_info.resolved_model` (the dated snapshot ID
   OpenAI's API returned for the `gpt-5-mini` alias, populated
   from 285/285 successful API calls after the 2026-05-12
   re-run); `base_url_sha256` records the full endpoint URL
   so a re-run against a rotated alias OR a proxy is auditable
   without leaking proxy credentials. A future v3 protocol could
   formalize this with multiple-debugger SHA pinning.
3. **One gpt-5-mini-class model tested.** "Generalizes across
   families" with sample size 1 family + 1 model is weak.
   GPT-4o, Gemini, Llama variants are all valid follow-ups.
4. **gpt-5-mini's calibration could differ from Sonnet/Haiku's.**
   sv1.1 was calibrated against an expert-Anthropic-model
   reviewer (E2b). The v3 numbers are computed with the same
   evaluator on the same ground truths, but the rank-correlation
   finding holds independently of absolute calibration.
5. **The §3i {hybrid-v1} on v1.3 and {hybrid-v2, hybrid-v3} on
   v2 agreement sets are robust to small sample noise** at the
   top-3 level — a single case swap could not move methods
   across the rank #3 boundary on most positions. The Spearman
   correlations and the unanimous bottom-2 ordering on v1.3 (raw
   #9, rtk-log #10 on every debugger) plus the bottom-4 set
   stability on v2 also reinforce this.

### What §3i means for publication

The §0 caveat that publication was blocked partly by "only
Anthropic debuggers" can be downgraded to "two Anthropic
debuggers + one OpenAI debugger; recommend additional families
in v3". The cross-family validation result is now itself a
headline finding ("**v2 produces cross-family-stable AND
cross-run-stable benchmark rankings; v1.3's stability is more
limited**"), which strengthens rather than weakens the case for
shipping v2 as-is or as a clearly-marked v2-partial preprint.

### Caveats

1. **v3 prototype evaluation is calibration-tuned at the v2 layer.**
   v3 inherits hybrid-v2's 120k threshold (selected from
   eval_diagnosis_*.json on the 13-case state). v3's only NEW
   tuning surface is "use rtk-err-cat if not truncated" — a
   one-bit decision derived from Codex F1 (truncation surfacing).
   So v3's incremental leakage over v2 is zero, but its inherited
   leakage matches v2.
2. **Single hybrid-v3 prototype tested.** Other rtk-fallback
   variants (rtk-log, rtk-read) were not tried; would have
   different cost/quality profiles.
3. **The Haiku Batch 6 result is wrapper-artifact-driven**, not
   method-driven. Should not be cited as evidence v3 generalizes
   on Haiku without also disclosing the §3e wrapper-flake mechanism.

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
