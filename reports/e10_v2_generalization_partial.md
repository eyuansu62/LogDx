# CILogBench E10 — v2 generalization (partial)

> **Two protocols are described in this report:**
>
> - [`cilogbench-v2-partial`](../protocols/cilogbench-v2-partial.lock.json)
>   (lock 2026-05-07, 24 cases) — the **8-case** v2 state that the
>   first Phase 3 run measured against. This is what the §3 8-case
>   numbers below are anchored to.
> - [`cilogbench-v2-checkpoint`](../protocols/cilogbench-v2-checkpoint.lock.json)
>   (lock 2026-05-07, 26 cases) — the **10-case** Phase 2 checkpoint
>   state, adding the v2/stress split (numpy segfault + cpython
>   matrix). The §4 10-case numbers below are anchored to this lock.
>
> Both locks SHA-pin the same v1.3 schemas, prompts, and evaluators
> that were in `cilogbench-v1.3.lock.json`, so v1.3 numbers reproduce
> identically against either; only the case set has grown.
>
> **Companion docs:**
> [`e10_phase3_v2_partial_signal_recall.md`](e10_phase3_v2_partial_signal_recall.md)
> (deterministic proxy detail) and
> [`e10_phase3_v2_partial_diagnosis.md`](e10_phase3_v2_partial_diagnosis.md)
> (real-debugger sv1.1 detail). This file is the single canonical
> narrative aggregating both.
>
> **Caveats** (covered in §5 below): 8-case sample, AI-drafted +
> single-author-verified ground truth, no independent human review,
> two Anthropic models only, mock LLM summary only.

## TL;DR

The v1.3 hybrid does **not** generalize to a fresh v2 corpus.
This is the strongest single result of E10 so far. Magnitudes
shifted between the 8-case (v2-partial) and 10-case (v2-checkpoint)
refreshes — the **direction** is unchanged in both cases; the
**ranking magnitude** softened from "rank #1 → #6" (8-case) to
"rank #1 → #3–4" (10-case), because adding the v2/stress split
revealed that *every* method except grep/tail collapses on
stress-bucket cases (raw and rtk-read both hit 0.000 sv1.1 on the
2 stress cases when Sonnet abstains; relative rank shifts).

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

- Hybrid falls from rank #1 (tied with grep) to **rank #6 of 8**.
  Confirmed with both Haiku 4.5 and Sonnet 4.6 — the rank shift is
  not debugger-specific.
- Top-2 (`grep`, `tail`) and bottom-3 (`hybrid` at #6,
  `llm-summary-v1-mock` at #7, `rtk-log` at #8) are **identical
  across both debuggers** on v2. This invariance protects the
  direction against random-noise concerns even at 8 cases.
- The cost advantage of hybrid is intact (~95% reduction in tokens).
  Only the quality match with grep does not survive distribution
  shift.

The v1.3 one-pager headline ("matched grep on quality at ~⅓ token
cost") was rewritten on 2026-05-07 to carry an explicit v2 caveat;
see [`docs/reports/cilogbench_v1_3_one_pager.md`](../docs/reports/cilogbench_v1_3_one_pager.md).

## 1. What changed in v2

The v2 corpus carries forward all 16 v1.3 cases (now tagged
`origin: legacy_v1_3` in `tags.json`) plus 8 new cases collected in
this round:

| split | new_v2 | filling |
|---|---:|---|
| `v2/dev` | 3 | docker_build (was 0/16), test_assertion, network_or_flaky (was 0/16) |
| `v2/holdout` | 5 | go ecosystem (was 0/16), dependency_install (audit), github_actions_config (2nd), snapshot_or_golden_diff (was 0/16), compile_error+cpp (was 0/16 cpp) |
| `v2/stress` | 2 | first stress cases — see §4 below |

The 10 new cases were sourced from real public CI runs (pnpm/pnpm,
pypa/pip, moby/buildkit, cli/cli, biomejs/biome,
prettier/prettier, pandas-dev/pandas, numpy/numpy, python/cpython)
and imported through the v2 intake pipeline
(`tools/import_case_skeleton.py` → ground_truth + tags annotation
→ raw-sanity gate at 100% signal preservation per case).

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
tcltk regression) — Phase 3 was re-run on the 10-case state.
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
6. **v2/stress is empty (0/3).** The 8 accepted cases are all in
   `v2/dev` (3) and `v2/holdout` (5). "Deliberately difficult"
   stress cases (huge logs, scattered evidence, multi-failure with
   distinct causes, unusual evidence format) have not been collected
   yet.
7. **Hybrid's threshold is the variable, not the method shape.**
   This study cannot say "hybrid as a strategy is bad." It only
   says "this specific 4k-token threshold tuned on v1.3 is bad on
   v2." A v2-tuned threshold would likely recover most of the gap;
   we deliberately did not retune on the same v2 corpus to avoid
   the same selection-by-method risk that produced the v1.3
   overfit (see `cilogbench_v1_3_limitations.md` §9).

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

Everything below is locked in
[`protocols/cilogbench-v2-partial.lock.json`](../protocols/cilogbench-v2-partial.lock.json):

```text
schemas         9 SHA-pinned schema files
prompts         3 SHA-pinned prompts (debugger_v1, llm_summary_v1_*)
evaluators      2 SHA-pinned evaluator scripts (signal_recall, diagnosis)
baselines       7 locked context-provider baselines
                 (raw, tail, grep, rtk-read, rtk-log, rtk-err-cat,
                  llm-summary-v1-mock, hybrid-grep-4k-rtk-err-cat-v1)
splits          5 splits: dev (5), holdout (5), stress (6),
                 v2/dev (3), v2/holdout (5)
total cases     24
```

To reproduce the headline numbers from a fresh checkout:

```bash
python3 tools/validate_protocol_lock.py --protocol protocols/cilogbench-v2-partial.lock.json
# Should print: "Protocol lock OK: cilogbench-v2-partial"

# Re-run all baselines on all splits (requires `rtk` on PATH):
for split in dev holdout stress v2/dev v2/holdout; do
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
  for split in dev holdout stress v2/dev v2/holdout; do
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

Sonnet 4.6 + Haiku 4.5 cost roughly $1.50 + $0.30 respectively for
the 64 calls each on v2 splits. v1.3 numbers are cached; only v2
needs re-running on a fresh checkout.

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
protocols/cilogbench-v2-partial.lock.json   ← THIS protocol's lock
docs/corpus/cilogbench_v2_case_matrix.md     ← target matrix + counts
docs/corpus/cilogbench_v2_collection_guidelines.md
docs/corpus/cilogbench_v2_annotation_guide.md
docs/corpus/v2_case_intake_queue.md          ← rolling intake worklist
cases/dev/, cases/holdout/, cases/stress/    ← 16 legacy v1.3 cases
cases/v2/dev/, cases/v2/holdout/             ← 8 new_v2 cases
results/{dev,holdout,stress,v2/dev,v2/holdout}/eval_diagnosis_real-debugger-{v1,v2}.json
                                              ← Haiku + Sonnet sv1.1 numbers
results/{...}/eval_<method>.json             ← signal-recall numbers
reports/e10_phase3_v2_partial_signal_recall.md   ← deterministic detail
reports/e10_phase3_v2_partial_diagnosis.md       ← real-debugger detail
reports/e10_codex_adversarial_review_fixes.md    ← privacy-gate fix log
reports/e10_v2_generalization_partial.md          ← THIS report
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
