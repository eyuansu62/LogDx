# cilogbench-v1.3 — Protocol document

> ⚠️ **Historical document — frozen at v1.3 ship.** This page
> documents the cilogbench-v1.3 protocol as released. Its verdict
> that **`llm-summary-v1-haiku` is not competitive with grep / hybrid**
> was based on a 16-case prototype subset and a single Haiku-only
> debugger. The v1.1.1 full 35-case × 4-diagnoser backfill **reverses
> that verdict** — the real Haiku summarizer scores **0.632 overall
> (rank 4)** on the [live leaderboard](../leaderboard.md). The v1.3
> lock file stays frozen for reproducibility; the live ranking has
> moved on. New readers should treat this page as historical context,
> not a current recommendation.

`cilogbench-v1.3` differs from `v1.2` only by adding the deterministic
`hybrid-grep-4k-rtk-err-cat-v1` context-provider baseline.

## 1. What changed from v1.2

| Component | v1.2 | v1.3 |
|---|---|---|
| Cases | 5 dev + 5 holdout + 6 stress = **16** | unchanged |
| Splits | dev, holdout, stress | unchanged |
| Ground truth | per-case `ground_truth.json` | unchanged |
| Prompts | `debugger_v1`, `llm_summary_v1_map`, `llm_summary_v1_reduce` | unchanged |
| Diagnosis evaluator | `tools/evaluate_diagnosis.py` (sv1 + sv1.1) | unchanged |
| Category compatibility | `configs/evaluation/category_compatibility_v1_1.json` | unchanged |
| Primary score | `diagnosis_score_v1_1` | unchanged |
| Secondary score | `diagnosis_score_v1` | unchanged |
| Existing baseline configs | `raw, tail-200, grep, rtk-read, rtk-log, rtk-err-cat, llm-summary-v1-mock` | unchanged |
| **Locked baselines** | 7 | **8** (adds `hybrid-grep-4k-rtk-err-cat-v1`) |

Nothing else moves. Re-running every locked v1.2 method on v1.3 is byte-stable.

## 2. Why hybrid was added

E5 (`reports/e5_hybrid_grep_fallback_cilogbench_v1_2.md`) showed that the
deterministic policy `grep-if-fits-else-rtk-err-cat @4k` passed every
freeze criterion when implemented as a first-class baseline:

| Criterion | Hybrid | Grep | Pass |
|---|---:|---:|:---:|
| Macro `diagnosis_score_v1_1` (3 splits) | **0.715** | 0.675 | ✅ |
| Macro total pipeline tokens | **4.9k** | 15.7k | ✅ |
| Macro `confident_error_rate_v1_1` | 0.0% | 0.0% | ✅ |
| Provider error rate | 0.0% | — | ✅ |

E4 had predicted macro sv1.1 = 0.723 from the offline policy sweep; E5's
real-run macro sv1.1 was 0.715 — a delta of −0.008 from the offline
prediction. The hybrid is therefore a stable, deterministic, cheap
context method that beats `grep` on the calibrated metric.

## 3. Locked baselines in v1.3

```text
raw
tail-200
grep
rtk-read
rtk-log
rtk-err-cat
llm-summary-v1-mock
hybrid-grep-4k-rtk-err-cat-v1   ← NEW
```

`llm-summary-v1-haiku` is **not** locked in v1.3. E3 showed real
Haiku summary was useful only under very tight final-context budgets
and was not competitive with grep / hybrid on the quality-cost
trade-off. Real summary remains an experiment artifact, not a v1.3
baseline.

> **2026-05-20 forward-pointer (v1.1)**: the v1.3 exclusion verdict was
> based on a 16-case prototype subset and a single Haiku-only debugger.
> A v1.1 full 35-case × 4-diagnoser backfill of `llm-summary-v1-haiku`
> places it at **rank 4 overall (0.632)** on the live leaderboard
> (vs the mock's 0.328). v1.3's lock file stays frozen for
> reproducibility, but the live `docs/leaderboard.md` now uses the real
> Haiku summary as the LLM-summary class representative. A future v1.4
> protocol could codify this by locking `llm-summary-v1-haiku` into the
> baseline list.

## 4. Hybrid routing rule

```text
For each case:
  if grep is available and (output_byte_size / 4) <= 4000:
      select grep
  elif rtk-err-cat is available:
      select rtk-err-cat            # primary_too_large_used_fallback OR
                                      # primary_provider_error_used_fallback
  else:
      record provider_error          # do not silently fall back to raw
```

Token estimate: `output_byte_size // 4` from the existing manifest rows.
This matches `tools/run_diagnosis.py`'s `context_tokens` accounting on
every locked grep / rtk-err-cat manifest (verified ratio 1.000).

The 4k threshold and the choice of `rtk-err-cat` as fallback come from
E4's offline budget-frontier sweep (`reports/e4_summary_failure_
attribution_cilogbench_v1_2.md`). They are not tunable per case at run
time.

## 5. Anti-leakage statement

The hybrid router uses only context manifests and token-budget metadata.
For each case it reads:

- the primary (`grep`) and fallback (`rtk-err-cat`) manifest rows
- the per-row `case_id`, `context_path`, `output_byte_size`,
  `output_line_count`, `included_line_ranges`,
  `metadata.provider_error`

The router **does not** read:

- `cases/<split>/<case_id>/ground_truth.json`
- `results/<split>/eval_*.json` (signal recall or diagnosis eval)
- `review/batches/*/labels/*.jsonl` (expert / human review labels)
- any `failure_category` / `required_signals` / `evidence_spans` field

The 4k threshold itself was chosen in E4's offline budget sweep, but the
per-case decision in v1.3 only consults the budget and the raw manifest
fields above — no scoring information leaks into the router.

A grep over the router source confirms only one match for any
"forbidden" identifier, and that match is in the file's docstring (not
in code).

## 6. Primary score

`diagnosis_score_v1_1` — calibrated in E2b (`reports/e2b_score_calibration_v1_1.md`)
and adopted as primary in v1.2. v1.3 inherits this without change.

## 7. Secondary score

`diagnosis_score_v1` — preserved alongside sv1.1 for historical
comparison; emitted by `tools/evaluate_diagnosis.py` per case.

## 8. Splits

```text
dev:     5 cases
holdout: 5 cases
stress:  6 cases  (+ formatting_failure → lint_failure aliasing in tags.json)
```

Same split manifests as v1.1 / v1.2.

## 9. What v1.3 can support

- "Under the calibrated `diagnosis_score_v1_1` rubric and the fixed
  `real-debugger-v1` (Haiku 4.5) debugger, the deterministic
  `hybrid-grep-4k-rtk-err-cat-v1` baseline outperforms `grep` on macro
  sv1.1 while spending ~⅓ the total-pipeline tokens, on this 16-case
  corpus."
- "The hybrid baseline introduces no provider errors and no confident
  errors v1.1 across dev / holdout / stress in the v1.3 protocol run."
- "The E4 offline budget-frontier prediction (sv1.1 = 0.723) closely
  matched the E5 first-class baseline result (sv1.1 = 0.715)."

## 10. What v1.3 cannot support

- "Hybrid routing is generally best for all CI debugging agents."
  → only one debugger model, one threshold, one fallback method, 16 cases.
- "`grep` is bad."
  → grep remains the best single-method baseline at 4k+ budgets.
- "Real LLM summary is useless."
  → real summary remains the only deployable method at <2k final-context
  budgets in the E4 sweep; it was excluded from v1.3 because it is not
  competitive at the standard ~4k budget, not because it is useless.
- Anything stronger than directional: 16 cases is too small for
  statistical claims.
