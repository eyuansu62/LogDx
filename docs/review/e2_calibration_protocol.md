# E2 / E2.5 / E2b — Calibration of E1 against expert-model review

E2 is the first M11-style review pass applied to a real debugger run
(E1's `real-debugger-v1`). The first reviewer used here is
`claude-opus-4-7-expert` — i.e. an LLM-as-judge expert reviewer, not an
unaffiliated human. Treat the E2 outputs as **expert-model review**;
real human review remains the canonical calibration.

E2.5 is the calibration memo that decides whether `diagnosis_score_v1`
and the deterministic metrics are trustworthy enough to keep using as
the primary signal in subsequent experiments (E3 real LLM summary,
second debugger model, MCP/agent baselines).

E2b (`reports/legacy/e2b_score_calibration_v1_1.md`) is the score-rule
calibration that ran after E2.5 closed at PASS-but-marginal. E2b adds
`category_match_score_v1_1` (partial match) and a stricter
`confident_error_v1_1` trigger; it does NOT rerun any model. The
result is `diagnosis_score_v1_1`, frozen as
`protocols/legacy/cilogbench-v1.2.lock.json`.

If E2.5 says the auto evaluator is **not** trustworthy at all, the
next milestone is **E2b**, not E3. Do not skip this gate.

## Inputs

| What | Where |
|---|---|
| Diagnoses to score | `results/holdout/diagnoses/real-debugger-v1/*.jsonl` (from E1) |
| Eval (auto metrics) | `results/holdout/eval_diagnosis_real-debugger-v1.json` |
| Protocol lock | `protocols/legacy/cilogbench-v1.1.lock.json` |
| Review batch | `review/batches/e2-real-debugger-v1-holdout-001/` |

## Scope

- **Split:** holdout (5 cases — same per the M11 plan).
- **Methods (4):** `raw`, `grep`, `rtk-err-cat`, `rtk-log`.
  - `raw` = full-context baseline.
  - `grep` = E1's stress-split winner.
  - `rtk-err-cat` = E1's dev-split winner.
  - `rtk-log` = E1's worst-across-all-splits.
  Picking one winner-side method, one alternate winner, one loser
  ensures the calibration can resolve "does the auto rank order match
  the human rank order".
- **Item count:** 20 absolute + 30 pairwise (C(4,2)·5) = 50.
- **Batch ID:** `e2-real-debugger-v1-holdout-001`.

Do **not** add `tail` or `rtk-read` here unless the next memo also
re-builds the batch — we want every reviewer to see the same set so
the human means are comparable across reviewers.

## Workflow

```bash
# (already done) build the blinded batch:
python3 tools/build_human_review_set.py \
  --protocol protocols/legacy/cilogbench-v1.1.lock.json \
  --split holdout \
  --diagnoser real-debugger-v1 \
  --methods raw,grep,rtk-err-cat,rtk-log \
  --batch-id e2-real-debugger-v1-holdout-001 \
  --mode both

# 1. Reviewers label items.jsonl, writing to:
#    review/batches/e2-real-debugger-v1-holdout-001/labels/reviewer_<id>.jsonl
#    See docs/review/reviewer_instructions.md for the rubric.

# 2. Validate label files (catches missing fields, bad ranges, leaked method names):
python3 tools/validate_human_review_labels.py \
  --batch-id e2-real-debugger-v1-holdout-001

# 3. Aggregate + correlate:
python3 tools/analyze_human_review.py \
  --batch-id e2-real-debugger-v1-holdout-001

# 4. Render the calibration memo (this is the E2.5 deliverable):
python3 tools/render_e2_calibration_memo.py \
  --batch-id e2-real-debugger-v1-holdout-001
# -> reports/legacy/e2_calibration_memo.md
```

## What the calibration memo answers

Five questions, mapped to the analyzer output:

1. Does `diagnosis_score_v1` track human `overall_usefulness`?
   → `correlation_with_deterministic.overall_vs_score_v1` (Spearman)
2. Does `critical_signal_mention_recall` track human `evidence_support`?
   → `correlation_with_deterministic.evidence_vs_critical_mention`
3. Does `confident_error` correspond to human-perceived hallucination
   or unhelpfulness?
   → `confident_error_calibration.human_flag_rate`
4. Does pairwise human preference match the auto-score-implied winner?
   → `pairwise_vs_auto_consistency.totals.agreement_rate`
5. What disagreement types dominate the top-5 gaps?
   → `disagreement_bucket_counts` (categorical taxonomy)

## Verdict thresholds

| Verdict | Conditions |
|---|---|
| `PASS` | `overall_vs_score_v1 ≥ 0.6` AND `pairwise agreement ≥ 0.6` AND `method-rank Spearman ≥ 0.6` |
| `PARTIAL` | `overall_vs_score_v1 ∈ [0.3, 0.6)` OR any guardrail dips while overall correlation holds |
| `FAIL` | `overall_vs_score_v1 < 0.3` OR `pairwise agreement < 0.4` (with ≥ 5 non-tie pairs) |

These thresholds are intentionally rough — sample is small, so the
verdict is mostly about which **disagreement bucket** dominates and
whether the rank order between methods agrees with human pairwise
preference.

## What happens after the verdict

| Verdict | Next milestone |
|---|---|
| `PASS` | If marginal (~0.6) and dominated by `confident_wrong_unflagged` disagreements, do **E2b** first (zero-cost score-rule calibration) before E3. Otherwise, go straight to **E3** — add a real LLM summarizer as a new context method, keep `real-debugger-v1` fixed. |
| `PARTIAL` | **E3** with reduced claims (do not quote a single composite ranking number) OR **E2b** first. |
| `FAIL` | **E2b** — build `diagnosis_score_v2` and re-score the existing 109 E1 diagnoses (no new model runs). Freeze a new `cilogbench-vX` if method ranking changes. |

**E2 (claude-opus-4-7-expert) actually closed at:** PASS, marginal
(0.637) — top-5 disagreements were dominated by `confident_wrong_
unflagged` (3/5). E2b was therefore run, lifted Spearman 0.637 → 0.839
and pairwise agreement 0.760 → 0.880, and `cilogbench-v1.2` was frozen
with `diagnosis_score_v1_1` as primary. E3 should be planned against
v1.2.

## Anti-patterns to avoid

- Do not jump to E3 (real LLM summary) or any second-debugger /
  MCP / search-agent baseline before E2.5 lands a verdict. You will
  not know what your numbers mean.
- Do not change the rubric mid-batch. If the memo surfaces an
  evaluator failure mode, fix the evaluator (E2b) — do not relax the
  rubric.
- Do not re-run E1 model calls just because E2 is in flight. E2
  scores existing diagnoses; the model is held fixed by design.
