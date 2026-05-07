# E9 cross-model expert-style review (NOT human-verified)

> **Disclosure (read first).** The 48 review labels analyzed in this memo
> were produced by **ChatGPT (an LLM)** and explicitly delivered by the
> reviewer's author as an *expert-style review draft*, with the disclaimer
> *"It is not an independent human-verified label set unless a human
> reviewer inspects and accepts/edits the labels."* This document treats
> the labels accordingly: **the E9 human-verification gap is NOT closed
> by this analysis.** What this memo can do is provide a second
> expert-model spot-check (different model family from E2/E2b's
> `claude-opus-4-7-expert`) to triangulate the v1.3 headline. Treat
> every number as one LLM's opinion, not as a human label.

- **Batch:** `e9_v1_3_hybrid_vs_grep_human_001` (the same items.jsonl
  built for the E9 plan; 32 absolute + 16 pairwise = 48 items over 16
  cases × 2 methods).
- **Reviewer:** `chatgpt_draft` (ChatGPT, model family/version not
  disclosed in the source upload).
- **Diagnoser scored:** `real-debugger-v2` (Sonnet 4.6 — same as E6).
- **Methods compared:** `hybrid-grep-4k-rtk-err-cat-v1` vs `grep`.

## 1. Headline numbers

### Per-method mean overall_usefulness (0–4)

| Method | n | mean | stdev | distribution `[0,1,2,3,4]` |
|---|---:|---:|---:|---:|
| `hybrid-grep-4k-rtk-err-cat-v1` | 16 | **3.875** | 0.342 | `[0, 0, 0, 2, 14]` |
| `grep` | 16 | **3.938** | 0.250 | `[0, 0, 0, 1, 15]` |

Δ = 0.063 on a 0–4 scale — **inside E9's 0.25 tie threshold**, but the
distribution is extremely top-clustered (29/32 of all 32 absolute scores
are 4). The reviewer barely differentiated.

### Pairwise winner distribution (16 items)

| Decision | Count |
|---|---:|
| `winner = grep` | **8** |
| `winner = hybrid` | **2** |
| `tie` | 6 |
| `both_bad` | 0 |
| `insufficient_information` | 0 |

Of the 10 decisive pairwise judgments, **grep wins 8 / hybrid wins 2**.

## 2. Correlation with deterministic metrics

| Metric pair | Spearman | n |
|---|---:|---:|
| `overall_usefulness` vs `diagnosis_score_v1` | **−0.46** | 32 |
| `overall_usefulness` vs `diagnosis_score_v1_1` (primary) | **−0.46** | 32 |
| `root_cause_correctness` vs `category_match_score_v1_1` | −0.18 | 32 |
| `evidence_support` vs `critical_signal_mention_recall` | −0.25 | 32 |
| `evidence_support` vs `must_mention_coverage` | +0.37 | 32 |

The negative `overall vs sv1.1` correlation is **almost certainly a
score-compression artifact**: the reviewer marked 29/32 items as 4. With
human ratings essentially constant and sv1.1 ranging 0.475 to 0.992, the
Spearman is dominated by tie-breaking noise. Read this as "the cross-
model reviewer didn't differentiate hybrid from grep enough to compute a
meaningful correlation," not as "sv1.1 is anti-correlated with usefulness."

For comparison, E2's expert-model reviewer (Claude Opus on 5 holdout
cases × 4 methods, with much wider score variance) gave Spearman = 0.84
on the same metric.

## 3. Pairwise human-vs-auto winner agreement

Filtering to the 10 decisive human pairwise judgments and comparing with
the auto-sv1.1 winner:

| | Count |
|---|---:|
| match (human and auto agree) | **4** |
| mismatch | 5 |
| auto_tie (sv1.1 hybrid == grep) | 1 |
| **agreement rate (over decisive non-tie pairs)** | **44.4%** |

Below the E9 plan's 50% threshold for `REVISE_EVALUATOR`, but again
remember the small sample and the cross-model nature of the reviewer.

Per-pair detail (showing where reviewer and sv1.1 diverge):

| Case | Human winner | Auto winner | Notes |
|---|---|---|---|
| `cargo-tokio-001` | grep | grep | match |
| `jest-nextjs-001` | grep | hybrid | mismatch |
| `mypy-pandas-001` | grep | grep | match |
| `pytest-pandas-001` | hybrid | grep | mismatch |
| `actions-terraform-001` | grep | (sv1.1 tie) | auto_tie |
| `pushpr-nextjs-001` | grep | hybrid | mismatch |
| `tsc-typescript-001` | hybrid | hybrid | match |
| `docbuild-hf-stress-001` | grep | hybrid | mismatch |
| `pytest-sklearn-stress-001` | grep | grep | match |
| `pytest-sklearn-stress-002` | grep | hybrid | mismatch |

## 4. Confident-error v1.1 false-positive rate

| | Count |
|---|---:|
| rows with `confident_error` (v1) | 8 / 32 |
| rows with `confident_error_v1_1` (primary) | **0 / 32** |
| v1 confident-errors confirmed by reviewer (halluc≥3 OR overall≤1) | 0 / 8 = **0%** |
| v1.1 confident-errors confirmed by reviewer | 0 / 0 = n/a |

This **reproduces the core E2b finding** under a second LLM family:
sv1's confident-error trigger fires on cases the reviewer rates 3-or-4,
and sv1.1's stricter trigger fixes that — exactly what E2b was designed
to do.

## 5. Disagreement bucket counts (top-5 by gap)

All 5 of the largest sv1-vs-human disagreements fell into the same
bucket:

| Bucket | Count |
|---|---:|
| `confident_wrong_unflagged` | 5 |

These are the *same* failure mode E2b's calibration addressed —
diagnoses the reviewer rated 4/4 but `sv1` flagged as confident-wrong
because of binary `category_accuracy=0`. Under sv1.1 these gaps shrink
substantially (the cases in question now score 0.55-0.70 instead of
0.14-0.30 under sv1).

## 6. Verdict on the v1.3 headline (cross-model only)

Applying the E9 plan's decision rules **to this cross-model data**
(and not as a substitute for human review):

| Rule | This data | Verdict component |
|---|---|---|
| pairwise hybrid ≥ grep | hybrid 2 W vs grep 8 W | ❌ grep preferred |
| overall_usefulness hybrid ≥ grep − 0.25 | 3.875 ≥ 3.938 − 0.25 = 3.688 → **YES** | ✅ within tie band |
| sv1.1 correlation ≥ 0.5 | −0.46 (score-compressed) | ❌ inconclusive |
| no systematic rejection of hybrid | distribution: `[0,0,0,2,14]` for hybrid | ✅ |

Per the plan, the closest verdict is **`WEAKEN_HEADLINE`** — *"human
reviewers clearly prefer grep BUT hybrid is still close and much
cheaper"* — but only as a cross-model spot-check. The strict E9
verdict (which the plan defines for **human** labels) remains
**`REVIEW_INCONCLUSIVE`** until a human reviewer (or a second human)
labels the same batch.

## 7. What this means for v1.3

The v1.3 technical report's headline phrase is:

> *On CILogBench v1.3, a simple deterministic hybrid context strategy
> matched or beat grep in diagnosis quality while using roughly one
> third of the tokens, and this result was stable across two debugger
> models.*

Cross-model expert-style review **partially supports and partially
weakens** this:

- ✅ "matched": mean overall_usefulness within 0.063 (tie band)
- ❌ "or beat": pairwise 8-2 in grep's favor on the cross-model signal
- ✅ "one third of the tokens": cost story unchanged — this review
  doesn't touch token cost
- ✅ "stable across two debugger models": cost-stable yes; quality-
  stable now reads more like "tied or slightly favoring grep" under
  cross-model review of the Sonnet run

## 8. Recommended public-doc edits

Conservative — the v1.3 limitations doc already discloses the human-
review gap. The polite update is **one paragraph in §2 of the
limitations doc** acknowledging the cross-model spot-check:

> Add to `docs/reports/cilogbench_v1_3_limitations.md` §2:
>
> *Update (2026-05): An additional cross-model expert-style review pass
> (ChatGPT, 48 items over the 16-case v1.3 corpus) reproduced the E2b
> finding that sv1.1 fixes sv1's confident-error false positives, and
> rated hybrid and grep diagnoses as effectively tied on overall
> usefulness (means 3.875 vs 3.938 on a 0–4 scale, distribution
> `[0,0,0,2,14]` and `[0,0,0,1,15]`). Pairwise judgments leaned toward
> grep (8 wins vs 2 for hybrid out of 16 items, with 6 ties). This
> remains expert-model review across two model families
> (Claude Opus, ChatGPT), not human review. The full E9 human-
> verification gap is unchanged.*

Do **not** edit the v1.3 technical report's headline phrasing on the
basis of this one ChatGPT pass — sample is small, distribution is
score-compressed, and the reviewer is still an LLM.

## 9. Recommended next step

The honest path to closing E9 is **still a real human reviewer on the
same batch**. This memo gives the eventual human reviewer one piece of
prior evidence (cross-model says ≈tied with mild grep lean), but does
not substitute for human labels. Until those land, the v1.3 public
report's "expert-model review only" caveat **stays**.

If finding a human reviewer is blocking, two acceptable interim moves:

1. **Run a third expert-model reviewer of a different family**
   (e.g., Gemini) on the same batch. If two of three model-family
   reviewers agree on hybrid vs grep, the headline is materially
   strengthened — but this is still cross-model triangulation, not E9.
2. **Sub-sample to 6 cases** (1 dev + 2 holdout + 3 stress, picked
   to span the failure-mode distribution) and **fully label them
   yourself**. 6 cases × 2 methods × (1 absolute + 1 pair) ≈ 18 items;
   ~30 min of focused work. That would constitute a partial-but-real
   E9 pass and would let the v1.3 limitations doc shift to "spot-checked
   by human review on a subset."

## 10. Inputs and provenance

```text
Source labels (uploaded):
  /Users/eyuansu62/Downloads/e9_absolute_expert_style_review.csv
  /Users/eyuansu62/Downloads/e9_pairwise_expert_style_review.csv
  /Users/eyuansu62/Downloads/e9_expert_style_review_summary.md   (disclosure)

Materialized as:
  review/batches/e9_v1_3_hybrid_vs_grep_human_001/labels/reviewer_chatgpt_draft.jsonl
  review/batches/e9_v1_3_hybrid_vs_grep_human_001/expert_style_review_summary_chatgpt.md

Analyzer output:
  results/human_review_e9_v1_3_hybrid_vs_grep_human_001.json

Eval data joined (read-only):
  results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v2.json
```

Validator confirmed 0 issues on `reviewer_chatgpt_draft.jsonl` (48
labels, all required fields present, all integer scores in [0,4], no
forbidden method names in `notes`/`reason`).
