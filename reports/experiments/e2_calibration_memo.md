# E2 Calibration Memo (Expert-Model Review)

> **Reviewer disclosure**: the labels backing this memo were produced by an LLM-as-judge reviewer (`claude-opus-4-7-expert`), not by an unaffiliated human. Treat these results as **expert-model review**. Real human review remains the canonical calibration; until then, every claim here should be read as model-on-model. See `reports/e2b_score_calibration_v1_1.md` for the downstream score-rule calibration that depends on these labels.

- **Batch:** `e2-real-debugger-v1-holdout-001`
- **Protocol:** `cilogbench-v1.1`
- **Split:** `holdout`
- **Diagnoser:** `real-debugger-v1`
- **Methods reviewed:** `raw`, `grep`, `rtk-err-cat`, `rtk-log`
- **Reviewers:** `claude-opus-4-7-expert`
- **Items:** 20 absolute + 30 pairwise = 50 total

## 1. Review setup

Built from E1 real-debugger-v1 outputs on `cilogbench-v1.1`.
Methods chosen so the calibration can resolve four questions:

- `raw` — full-context baseline
- `grep` — top sv1 on stress split (E1 winner-side example)
- `rtk-err-cat` — top sv1 on dev split (alternate winner)
- `rtk-log` — bottom sv1 on every split (loser-side example)

## 2. Main correlations

| Metric pair | Spearman | n | Interpretation |
|---|---:|---:|---|
| overall_usefulness vs diagnosis_score_v1 | 0.637 | 20 | passes 0.6 — auto score tracks usefulness |
| evidence_support vs critical_signal_mention_recall | 0.799 | 20 | does evaluator's literal-mention proxy track human evidence judgment? |
| evidence_support vs valid_evidence_quote_rate | 0.218 | 20 | does quote-validity proxy track human evidence judgment? |
| root_cause_correctness vs category_accuracy | 0.365 | 20 | does taxonomy match track human root-cause judgment? |
| hallucination_severity vs forbidden_claim_count | n/a | 20 | does forbidden-claim guard catch human-perceived hallucinations? |

Method-level rank correlation (mean human overall vs mean det_score_v1 across 4 methods): **0.800**

## 3. Pairwise preference summary

| Pair | Human → Auto | Match | Mismatch | Auto-tie |
|---|---|---:|---:|---:|
| `grep` vs `raw` |  | 1 | 1 | 0 |
| `grep` vs `rtk-err-cat` |  | 4 | 1 | 0 |
| `grep` vs `rtk-log` |  | 4 | 1 | 0 |
| `raw` vs `rtk-err-cat` |  | 4 | 1 | 0 |
| `raw` vs `rtk-log` |  | 4 | 1 | 0 |
| `rtk-err-cat` vs `rtk-log` |  | 2 | 1 | 0 |
| **TOTAL** |  | **19** | **6** | **0** |

Aggregate human/auto agreement rate (over non-tie pairs): **0.760**

### Per-method human means

| Method | mean overall | mean root cause | mean evidence | mean halluc severity | W / L / T |
|---|---:|---:|---:|---:|---|
| `raw` | 3.400 | 3.600 | 3.400 | 0.800 | 10 / 2 / 3 |
| `grep` | 3.800 | 4 | 3.600 | 0.200 | 12 / 0 / 3 |
| `rtk-err-cat` | 1.400 | 1 | 1.800 | 0.800 | 2 / 11 / 2 |
| `rtk-log` | 1 | 1 | 1.200 | 1.400 | 1 / 12 / 2 |

## 4. Largest disagreements (top 5, classified)

| Case | Method | human_overall | det_score_v1 | gap | bucket |
|---|---|---:|---:|---:|---|
| `actions-terraform-001` | `grep` | 4 | 0.300 | 0.700 | `confident_wrong_unflagged` |
| `dependabot-cargo-001` | `grep` | 3 | 0.065 | 0.685 | `confident_wrong_unflagged` |
| `actions-terraform-001` | `rtk-log` | 2 | 0.008 | 0.492 | `confident_wrong_unflagged` |
| `actions-terraform-001` | `raw` | 3 | 0.263 | 0.487 | `wrong_category_but_useful` |
| `dependabot-cargo-001` | `raw` | 2 | 0.075 | 0.425 | `other` |

**Bucket counts in top-5:**
- `confident_wrong_unflagged`: 3
- `wrong_category_but_useful`: 1
- `other`: 1

## 5. Evaluator failure modes (derived from buckets)

- **confident_wrong_unflagged** (n=3) — Diagnoser was confidently wrong by auto rule but humans did not perceive this as a hallucination — confident-error threshold may be too aggressive.
- **wrong_category_but_useful** (n=1) — Diagnosis picks the wrong taxonomy bucket but humans still found it useful — category match may be too coarse a feature.
- **other** (n=1) — Disagreement does not match any pre-defined bucket — inspect the row manually.

## 6. Confident-error calibration

- Rows where diagnoser was confidently wrong AND a human label exists: **5**
- Of those, humans flagged severe hallucination (human_hallucination >= 3): **0**
- ...flagged unhelpful (human_overall <= 1): **0**
- ...flagged either: **0** (0.000 of confident-error rows)

Interpretation: a high human_flag_rate confirms `confident_error` is a useful safety signal. A low rate suggests the auto rule is over-firing or under-firing.

## 7. Decision and recommended next experiment

**Verdict: `PASS`**

Rationale:
- overall_vs_score_v1 Spearman = 0.637 (PASS>=`0.6`, FAIL<`0.3`)
- pairwise human/auto agreement = 0.760 (over 25 non-tie pairs; PASS>=`0.6`, FAIL<`0.4`)
- method-level Spearman (mean human_overall vs mean det_score_v1) = 0.800

### Recommended next step

Auto evaluator is trustworthy enough to keep using as the primary signal. Proceed to **E3: real LLM summary baseline** with the same fixed debugger (`real-debugger-v1`). Do not change the debugger or evaluator yet — only add `llm-summary-v1-real` as a new context method and re-run the full protocol. Track summary processing tokens, final context tokens, and diagnosis tokens to evaluate the cost/quality trade-off.

## Appendix A. E1 reference numbers (for context only)

Method-level `diagnosis_score_v1` from the E1 protocol run, all splits:

| Method | dev sv1 | holdout sv1 | stress sv1 |
|---|---:|---:|---:|
| `grep` | 0.429 | 0.549 | 0.686 |
| `llm-summary-v1-mock` | 0.409 | 0.438 | 0.489 |
| `raw` | 0.092 | 0.580 | 0.429 |
| `rtk-err-cat` | 0.651 | 0.411 | 0.420 |
| `rtk-log` | 0.178 | 0.273 | 0.146 |
| `rtk-read` | 0.090 | 0.614 | 0.364 |
| `tail` | 0.355 | 0.682 | 0.669 |

## Appendix B. Pipeline

```
# Validate labels first
python3 tools/validate_human_review_labels.py --batch-id e2-real-debugger-v1-holdout-001

# Aggregate + correlate
python3 tools/analyze_human_review.py --batch-id e2-real-debugger-v1-holdout-001

# Render this memo
python3 tools/render_e2_calibration_memo.py --batch-id e2-real-debugger-v1-holdout-001
```

