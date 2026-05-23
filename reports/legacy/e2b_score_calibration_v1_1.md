# E2b Score Calibration v1.1

> **Reviewer disclosure**: the 50 review labels backing this memo were produced by `claude-opus-4-7-expert` acting as an LLM-as-judge expert reviewer, not by an unaffiliated human. This is **expert-model review**, not human review. Public summaries should refer to it as such until human reviewers cross-check the labels.

- **Batch:** `e2-real-debugger-v1-holdout-001`
- **Protocol:** `cilogbench-v1.1`
- **Split:** `holdout`
- **Diagnoser:** `real-debugger-v1`
- **Methods reviewed:** `raw`, `grep`, `rtk-err-cat`, `rtk-log`
- **Reviewer:** `claude-opus-4-7-expert` (expert-model)

## 1. Motivation

E2 closed with `overall_usefulness vs sv1` Spearman = 0.637 — just over the PASS threshold. Three of the top-5 disagreements landed in the `confident_wrong_unflagged` bucket: diagnoses where the reviewer rated the answer 3 or 4 out of 4, but the auto evaluator marked them as confident errors purely because `category_accuracy = 0`. That is a structural scoring bug — semantically correct, operationally useful diagnoses were being penalized twice (zero category credit + the confident-error penalty).

E2b is a zero-cost calibration layer that:

1. Replaces binary `category_accuracy` with `category_match_score` (1.0 / 0.5 / 0.0) using an explicit compatibility table.
2. Rewrites `confident_error` so that wrong category alone no longer triggers it — the diagnosis must also miss critical evidence or violate forbidden-claim rules.
3. Adds `diagnosis_score_v1_1` alongside `diagnosis_score_v1`. v1 is preserved unchanged.

It does not change models, prompts, methods, cases, ground truth, or human labels.

## 2. What changed and what did not

| Field | v1 | v1.1 |
|---|---|---|
| Category match | `category_accuracy` (binary 0/1) | `category_match_score_v1_1` (0 / 0.5 / 1) using `configs/evaluation/category_compatibility_v1_1.json` |
| Confident-error trigger | `confidence >= 0.7 AND (category_accuracy=0 OR forbidden>0)` | `confidence >= 0.7 AND (forbidden>0 OR (category_match=0 AND critical<0.5 AND must_mention<0.5))` |
| Composite | `diagnosis_score_v1` (preserved) | `diagnosis_score_v1_1` (added) |

Unchanged: diagnosis outputs, model, prompt, cases, methods, ground truth, expert-model labels.

## 3. Correlation comparison

| Metric | v1 | v1.1 | Δ |
|---|---:|---:|---:|
| overall_usefulness Spearman | 0.637 | 0.839 | +0.201 |
| pairwise human/auto agreement | 0.760 | 0.880 | +0.120 |
| method-rank Spearman | 0.800 | 0.800 | +0.000 |
| root_cause vs category | 0.365 | 0.403 | +0.039 |
| evidence vs critical signal | 0.799 | 0.799 | +0.000 |

## 4. Confident-error comparison

| Stat | v1 | v1.1 |
|---|---:|---:|
| confident_error rows (in reviewed set) | 5 | 0 |
| confirmed by reviewer (severe halluc OR overall<=1) | 0/5 | 0/0 |
| false-positive rate | 1.00 | n/a |

(Lower confident-error count + lower false-positive rate = better calibration.)

## 5. Method ranking on the reviewed split

| Method | mean human overall | sv1 | sv1.1 | Δ score | cat_v1 | cms_v1.1 | confErr_v1 | confErr_v1.1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | 3.400 | 0.580 | 0.705 | +0.125 | 0.600 | 0.700 | 0.400 | 0.000 |
| `grep` | 3.800 | 0.549 | 0.674 | +0.125 | 0.600 | 0.700 | 0.400 | 0.000 |
| `rtk-err-cat` | 1.400 | 0.411 | 0.411 | +0.000 | 0.600 | 0.600 | 0.000 | 0.000 |
| `rtk-log` | 1 | 0.273 | 0.373 | +0.100 | 0.400 | 0.600 | 0.200 | 0.000 |

## 6. Top disagreements before vs after

### Top-5 under sv1

| Case | Method | human_overall | sv1 | gap |
|---|---|---:|---:|---:|
| `actions-terraform-001` | `grep` | 4 | 0.300 | 0.700 |
| `dependabot-cargo-001` | `grep` | 3 | 0.065 | 0.685 |
| `actions-terraform-001` | `rtk-log` | 2 | 0.008 | 0.492 |
| `actions-terraform-001` | `raw` | 3 | 0.263 | 0.487 |
| `dependabot-cargo-001` | `raw` | 2 | 0.075 | 0.425 |

### Top-5 under sv1.1

| Case | Method | human_overall | sv1.1 | gap |
|---|---|---:|---:|---:|
| `dependabot-cargo-001` | `grep` | 3 | 0.315 | 0.435 |
| `dependabot-cargo-001` | `rtk-log` | 0 | 0.333 | 0.333 |
| `actions-terraform-001` | `grep` | 4 | 0.675 | 0.325 |
| `docs-transformers-001` | `grep` | 4 | 0.693 | 0.307 |
| `docs-transformers-001` | `rtk-err-cat` | 1 | 0.530 | 0.280 |

Average gap among top-5: v1=0.558 -> v1.1=0.336 (-0.222)

## 7. Verdict

**`ACCEPT_V1_1`**

Rationale:
- overall_vs_score Spearman: v1=0.637 -> v1.1=0.839
- pairwise agreement: v1=0.760 -> v1.1=0.880
- method-rank Spearman: v1=0.800 -> v1.1=0.800
- confident-error count: v1=5 -> v1.1=0
- confident-error confirmed by reviewer (severe halluc OR overall<=1): v1=0/5 -> v1.1=0/0

Adopt `diagnosis_score_v1_1` as the primary score for E3 and downstream experiments. Continue to emit `diagnosis_score_v1` alongside for historical comparison. Freeze the calibration table as `cilogbench-v1.2`.

## 8. Caveats

- 50 expert-model labels on 5 holdout cases is a small sample. The verdict reflects the calibration direction, not statistical certainty.
- The reviewer is `claude-opus-4-7-expert` (LLM-as-judge), not an unaffiliated human. Real human review remains the canonical calibration.
- The compatibility table is intentionally narrow. Adding new partial pairs without justification will erode score discrimination.

## 9. Pipeline

```
# Re-score all splits with v1.1 fields:
python3 tools/evaluate_diagnosis.py --split dev --diagnoser real-debugger-v1
python3 tools/evaluate_diagnosis.py --split holdout --diagnoser real-debugger-v1
python3 tools/evaluate_diagnosis.py --split stress --diagnoser real-debugger-v1

# Render this memo:
python3 tools/render_e2b_score_calibration_memo.py --batch-id e2-real-debugger-v1-holdout-001
```

