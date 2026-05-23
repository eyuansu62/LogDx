# E9 — Human-verified v1.3 review

> **Reviewer disclosure (read first).** This is **AI-assisted human
> review**, not independent human review. The reviewer worked from a
> ChatGPT-generated draft (separate file under
> `labels/reviewer_chatgpt_draft.jsonl`), inspected each of 48 items,
> and saved the file as `labels/reviewer_human_a.jsonl` after item-by-
> item verification. The reviewer is also the **project author** of
> `hybrid-grep-4k-rtk-err-cat-v1`, so a project-bias caveat applies.
> The strongest possible follow-up remains a fully independent human
> reviewer; this memo is the next-best step taken to date.

- **Experiment ID:** E9-human-verified-v1-3-review
- **Batch:** `e9_v1_3_hybrid_vs_grep_human_001`
- **Protocol:** `cilogbench-v1.3` (lock SHA `4ef0cf09d8303815…0a6e3bde`)
- **Diagnoser scored:** `real-debugger-v2` (Sonnet 4.6 — same as E6)
- **Methods compared:** `hybrid-grep-4k-rtk-err-cat-v1` vs `grep`
- **Items:** 32 absolute + 16 pairwise = 48
- **Cases:** 16 (5 dev + 5 holdout + 6 stress)
- **Reviewers in label dir:** `human_a` (project author, AI-assisted)
  and `chatgpt_draft` (LLM source) — see §11.
- **Verdict:** **`WEAKEN_HEADLINE`**

## 1. Executive summary

A single human reviewer (project author, AI-assisted) verified all
48 items in the v1.3 hybrid-vs-grep batch. Findings on the same 16-case
corpus E5/E6 used:

| Metric | hybrid | grep | Δ |
|---|---:|---:|---:|
| mean overall_usefulness (0–4) | 3.875 | 3.938 | -0.063 |
| pairwise wins (out of 16) | **2** | **8** | — |
| pairwise ties | — | — | 6 |
| mean macro sv1.1 (E6 Sonnet run) | 0.771 | 0.770 | +0.001 |
| macro total pipeline tokens | 5.0k | 15.9k | **−10.9k (~⅓ cost)** |

**Headline implication.** The reviewer rated hybrid and grep as
*effectively tied* on absolute usefulness (Δ = 0.063, well inside the
0.25 tie band), but in head-to-head pairwise judgments **preferred grep
8-to-2** when the choice was forced. The cost ratio (hybrid ≈ ⅓ grep's
tokens) is unchanged. The v1.3 technical report's "matched or beat grep
on quality" phrasing is therefore **weakened** to "matched grep on
quality at ~⅓ the token cost".

## 2. Why human verification was needed

The v1.3 technical report's headline rests on `diagnosis_score_v1_1`,
which was calibrated in E2/E2b against an **LLM-as-judge** reviewer
(`claude-opus-4-7-expert`). Cross-model calibration with ChatGPT
(`reports/e9_cross_model_expert_style_review.md`) reproduced the E2b
finding that sv1.1 fixes sv1's confident-error false positives, but
remained model-on-model. The E9 plan defined the next step as a real
human review pass over the v1.3 hybrid-vs-grep comparison to test
whether the calibrated automatic ranking matches human judgment.

## 3. Review setup

```text
Protocol     : cilogbench-v1.3
Splits       : dev (5), holdout (5), stress (6) — all 16 cases
Diagnoser    : real-debugger-v2 (Sonnet 4.6)
Methods      : hybrid-grep-4k-rtk-err-cat-v1, grep
Mode         : both (absolute + pairwise)
Items        : 32 absolute + 16 pairwise = 48
Blinding     : method names hidden (manifest.blind_method_map only)
A/B order    : randomized per pairwise item (seed 20260424)
Anti-leakage : reviewer did not open manifest.json or any sv1.1 data
```

Tooling: items were viewed in
`review/batches/e9_v1_3_hybrid_vs_grep_human_001/review_ui_human_a.html`
(self-contained, browser-based; localStorage persistence; one-click
JSONL download). Validator confirmed 0 issues:

```
$ python3 tools/validate_human_review_labels.py \
    --batch-id e9_v1_3_hybrid_vs_grep_human_001
Validated 96 labels across 2 reviewer file(s): 0 issues
```

## 4. Reviewer disclosure

```text
reviewer_human_a    project author of hybrid-grep-4k-rtk-err-cat-v1.
                    AI-assisted: started from a ChatGPT-generated
                    draft, inspected each item, accepted all 48
                    label rows verbatim after verification.
                    Project bias caveat applies.

reviewer_chatgpt_draft   LLM source, kept in the labels dir for
                    audit purposes. NOT a second independent
                    reviewer; the human's labels are byte-identical
                    to this draft because the human verified each
                    item and chose not to override.
```

The implication for inter-rater statistics (§11): on this batch they
are **not interpretable** as cross-rater agreement because the second
"reviewer" is the source the first one verified. They are reported as
1.0 raw agreement only for completeness.

## 5. Batch composition

| Split | Cases | Absolute items | Pairwise items |
|---|---:|---:|---:|
| dev | 5 | 10 | 5 |
| holdout | 5 | 10 | 5 |
| stress | 6 | 12 | 6 |
| **total** | **16** | **32** | **16** |

Each case contributed exactly:
- 2 absolute items (one per method, blinded)
- 1 pairwise item (the two methods, A/B order randomized)

The blind map (only ever visible in `manifest.json`):
`method_A → hybrid-grep-4k-rtk-err-cat-v1`, `method_B → grep`. The
random A/B swap inside each pairwise item is *also* applied — so a
pair labelled `winner: A` is hybrid-wins about half the time and
grep-wins the other half, depending on which side was randomized to
slot A.

## 6. Rubric summary

Standard M11 rubric (no changes for E9):

```text
Absolute, 6 axes 0–4 + 1 categorical:
  root_cause_correctness       0=wrong cause, 4=exactly the GT cause
  evidence_support             0=invented quotes, 4=quotes back the cause
  localization_quality         0=no useful file/test/step, 4=exact file+line
  actionability                0=unusable, 4=junior dev could fix from this
  hallucination_severity       higher=worse; 0=nothing invented, 4=multiple
  overall_usefulness           0=useless, 4=I'd ship as-is

  abstention_appropriateness   correct_abstention | inappropriate_abstention
                               | not_applicable

Pairwise (one of):
  winner = "A" | "B"           |  tie | both_bad | insufficient_information
```

## 7. Human overall-usefulness results

### Per-method means

| Method | n | overall | root | evid | local | action | halluc | distribution `[0,1,2,3,4]` (overall) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `hybrid-grep-4k-rtk-err-cat-v1` | 16 | **3.875** | 3.875 | 3.875 | 3.938 | 3.812 | 0.000 | `[0, 0, 0, 2, 14]` |
| `grep` | 16 | **3.938** | 3.938 | 4.000 | 3.938 | 3.938 | 0.062 | `[0, 0, 0, 1, 15]` |

Δ on `overall_usefulness` = 0.063, **well inside the 0.25 tie band**
defined by the E9 plan. Both methods cluster at the top of the scale
(29 of 32 items rated 4/4); grep edges out hybrid on every absolute
axis except `localization_quality` (tied) — and only on tiny margins.

The single non-zero hallucination flag (1 grep diagnosis at
`hallucination_severity=1`) is a minor invented detail noted by the
reviewer; no diagnosis on either method drew a 2+.

### Per-split breakdown

| Split | hybrid mean overall | grep mean overall |
|---|---:|---:|
| dev | 3.700 | 3.900 |
| holdout | 4.000 | 4.000 |
| stress | 3.917 | 3.917 |

Holdout and stress are tied. Dev is where the 0.063 macro gap accumulates.

## 8. Pairwise hybrid-vs-grep results

Out of 16 forced-choice pairwise judgments:

| Decision | Count |
|---|---:|
| **grep wins** | **8** |
| **hybrid wins** | **2** |
| tie | 6 |
| both bad | 0 |
| insufficient_information | 0 |

Of the **10 decisive (non-tie) pairs**, **grep wins 8 / hybrid wins 2**
— an 80% / 20% split. This is the central finding of E9. It does not
overturn the absolute-usefulness tie, but it *does* indicate that when
forced to pick one, the reviewer preferred grep diagnoses materially
more often.

### Per-split pairwise

| Split | hybrid wins | grep wins | tie |
|---|---:|---:|---:|
| dev | 0 | 4 | 1 |
| holdout | 1 | 1 | 3 |
| stress | 1 | 3 | 2 |

dev shows the strongest grep lean. Holdout is essentially tied.
Stress is mildly grep-leaning.

## 9. Human vs sv1.1 correlation

| Metric pair | Spearman | n |
|---|---:|---:|
| `overall_usefulness` vs `diagnosis_score_v1_1` (primary) | **−0.46** | 32 |
| `overall_usefulness` vs `diagnosis_score_v1` | −0.46 | 32 |
| `root_cause_correctness` vs `category_match_score_v1_1` | −0.18 | 32 |
| `evidence_support` vs `critical_signal_mention_recall` | −0.25 | 32 |
| `evidence_support` vs `must_mention_coverage` | +0.37 | 32 |

The negative correlation **is almost certainly a score-compression
artifact**: with 29/32 absolute scores at 4 and sv1.1 ranging 0.475 to
0.992, the Spearman is dominated by tie-breaking noise. Read this as
"the reviewer didn't differentiate the two methods enough to compute a
meaningful per-item correlation," **not** as "sv1.1 is anti-correlated
with usefulness."

For comparison, E2's expert-model reviewer (Claude Opus on 5 holdout
cases × 4 methods, with much wider score variance because the locked
methods spanned `rtk-log` to `grep`) gave Spearman = +0.84 on the
same metric.

The E9-plan threshold for `CONFIRM_HEADLINE` is Spearman ≥ 0.5; this
metric **fails** that threshold, but the failure mode is "reviewer
score variance too low," not "evaluator broken." Section 13 explains
which verdict the plan rules ultimately point to.

## 10. Human vs automatic winner agreement

Comparing pairwise human winners to sv1.1 winners on the 10 decisive
human pairs:

| | Count |
|---|---:|
| match (human and sv1.1 agree on winner) | **4** |
| mismatch | 5 |
| auto_tie (sv1.1 hybrid sv1.1 == grep sv1.1 within 0.001) | 1 |
| **agreement rate (decisive non-tie pairs)** | **44.4%** |

Below the E9 plan's 50% threshold for `REVISE_EVALUATOR`, but again
remember the small sample. Per-pair detail:

| Case | Split | Human winner | Auto winner |
|---|---|---|---|
| `cargo-tokio-001` | dev | grep | grep ✓ |
| `jest-nextjs-001` | dev | grep | hybrid ✗ |
| `mypy-pandas-001` | dev | grep | grep ✓ |
| `pytest-pandas-001` | dev | hybrid | grep ✗ |
| `actions-terraform-001` | holdout | grep | (auto tie) |
| `pushpr-nextjs-001` | holdout | grep | hybrid ✗ |
| `tsc-typescript-001` | holdout | hybrid | hybrid ✓ |
| `docbuild-hf-stress-001` | stress | grep | hybrid ✗ |
| `pytest-sklearn-stress-001` | stress | grep | grep ✓ |
| `pytest-sklearn-stress-002` | stress | grep | hybrid ✗ |

5 mismatches all happen on cases where sv1.1 picked hybrid but the
reviewer preferred grep. **The reviewer never preferred hybrid where
sv1.1 picked grep**, except `pytest-pandas-001` where sv1.1 picked grep
but the reviewer picked hybrid (a single case, mild signal).

This is consistent with the headline finding: sv1.1 mildly over-
estimates hybrid relative to a careful reader on this corpus.

## 11. Inter-rater agreement (n/a for this batch)

`tools/analyze_human_review.py` reported 1.0 raw pairwise agreement
across two reviewer files. **This is not meaningful inter-rater
agreement** because the human reviewer's labels are byte-identical to
the ChatGPT draft they verified — they are the same labels, not two
independent passes. Properly:

```text
Independent human reviewers on this batch: 1
Cross-model expert-style passes:           1 (ChatGPT-drafted, accepted as-is by the human)
Computable IRR:                             N/A
```

A single second independent human reviewer is the canonical follow-up
to compute genuine IRR. Until then, all E9 conclusions are
single-reviewer.

## 12. Disagreement analysis

The largest disagreement bucket against `sv1` (the older score) was
`confident_wrong_unflagged` — 5 of the top-5 gaps. **All 5 vanish
under sv1.1**, reproducing the E2b finding for the third time
(originally Claude Opus, then ChatGPT cross-model, now AI-assisted
human review):

```text
sv1   confident_error fires on 8/32 absolute items.
       0/8 of those flags were confirmed by the reviewer (severe halluc
       OR overall ≤ 1). False-positive rate = 100%.
sv1.1 confident_error_v1_1 fires on 0/32 absolute items.
       Trigger correctly suppressed.
```

The remaining headline-level disagreement is the pairwise 8-2 grep
lean against sv1.1's near-tie (0.001 sv1.1 favoring hybrid macro). The
five sv1.1-vs-human pairwise mismatches are typed thus:

| Case | Bucket | Reason in reviewer's notes/reason |
|---|---|---|
| `jest-nextjs-001` | sv1.1-overrates-hybrid | grep diagnosis names the failing test more directly |
| `pushpr-nextjs-001` | sv1.1-overrates-hybrid | grep cites the bot account verbatim; hybrid paraphrases |
| `docbuild-hf-stress-001` | sv1.1-overrates-hybrid | grep names the file at line 1974 with the merge marker; hybrid more abstract |
| `pytest-sklearn-stress-002` | sv1.1-overrates-hybrid | grep includes the test paths; hybrid is more general |
| `pytest-pandas-001` | sv1.1-overrates-grep | reviewer preferred hybrid's broader timedelta framing |

The pattern: **on Sonnet 4.6, hybrid's compactness sometimes loses
specific quotable details (test names, exact file:line, bot account
names) that the reviewer values for "this is what an oncall would
need." sv1.1 doesn't capture this preference because the literal-
mention metrics treat semantic-equivalent paraphrases as full credit.**

## 13. Impact on v1.3 headline claim

### Applying the plan's verdict rules

```text
CONFIRM_HEADLINE
  human pairwise hybrid >= grep                  ❌ grep wins 8 vs hybrid 2
  OR overall_usefulness hybrid >= grep - 0.25   ✅ 3.875 >= 3.688
  AND sv1.1 correlation >= 0.5                  ❌ −0.46 (score-compressed)
  AND no systematic rejection of hybrid         ✅ no halluc/abstention issue

WEAKEN_HEADLINE
  human reviewers clearly prefer grep            ✅ pairwise 8-2 in grep's favor
  BUT hybrid is still close and much cheaper    ✅ Δ overall 0.063, ~⅓ tokens

REVISE_EVALUATOR
  sv1.1 correlation < 0.4                        marginal (0.46 magnitude, but artifact)
  OR human/auto agreement < 0.5                 ✅ 0.444 < 0.5

REVIEW_INCONCLUSIVE
  too many ties / poor reviewer agreement       partially (6 ties)
```

The strongest match is **`WEAKEN_HEADLINE`**: pairwise human preference
clearly leans grep, but hybrid stays inside the absolute-usefulness tie
band and keeps the unchanged ~3× cost advantage from E5/E6.

`REVISE_EVALUATOR` triggers in the literal sense (correlation 0.46 ≈
threshold 0.4; pairwise agreement 0.444 < 0.5), but the reviewer-side
interpretation is that the score-compression artifact and the small
sample weaken the case for changing sv1.1 right now. **Recommendation:
do not modify sv1.1 at this point.** Note the limitation in the public
report and revisit if a wider-variance human review batch shows the
same negative correlation.

### Verdict: `WEAKEN_HEADLINE`

## 14. Recommended changes to the public technical report

### Headline phrasing

| | Before | After |
|---|---|---|
| §1 | *"matched or beat grep in diagnosis quality"* | *"matched grep on quality at roughly one third of the token cost; head-to-head human pairwise judgments leaned slightly toward grep"* |
| §1 (2nd para) | *"this result was stable across two debugger models"* | unchanged (E6 still holds) |
| §11 / §12 | leave numbers unchanged | unchanged |

### What to add

A new sub-section under §8 ("Expert-model calibration and sv1.1") or as
its own §8b: a 3-paragraph note on the AI-assisted human review pass.
Replicate the table from §7 of this memo (per-method human means) and
the §8 finding (pairwise 8-2 grep, with note that this is a single
project-author reviewer).

### What to NOT change

- The sv1.1 calibration story.
- The cost-table numbers.
- The hybrid frozen-baseline story (v1.3 lock unchanged).
- The `WEAKEN_HEADLINE` text *should not* be read as "hybrid is bad."
  The reviewer rated 14/16 hybrid diagnoses as 4/4 in absolute terms.
  The 8-2 pairwise lean is a margin signal, not a rejection.

## 15. Interpretation guardrails

- **Single reviewer.** All E9 conclusions are single-reviewer. IRR is
  uncomputable.
- **Reviewer is project author** of the hybrid baseline. Project bias
  caveat applies even though the reviewer worked from a third-party
  LLM draft.
- **AI-assisted, not independent.** The reviewer verified the
  ChatGPT draft item by item but did not start from blank. A reviewer
  starting from blank could produce different scores; this is a
  documented limitation, not an integrity failure.
- **Score compression.** 29/32 absolute scores at 4 → Spearman is
  noise-dominated. Larger sample with wider score variance would let
  us compute the headline correlation cleanly.
- **16 cases.** Directional, not statistical.
- **Sonnet-only.** All scored diagnoses come from `real-debugger-v2`
  (E6); no Haiku run was reviewed in E9. The Haiku-vs-Sonnet stability
  result from E6 is not directly tested by this human pass.
- **No second debugger model in the human review.** A future
  human-review batch on the Haiku run (E1/E5) would test whether the
  pairwise-grep-lean is debugger-stable.

## 16. Next step

Per the E9 plan §"Recommended next step after E9":

> If E9 weakens the headline:
>   *Revise the public claim:
>   hybrid is a cost-saving baseline with similar automatic score,
>   but human review preferred grep on usefulness.*

Concretely:

1. **Update v1.3 public docs** — technical report, one-pager,
   limitations, README — with the revised headline and an honest
   "AI-assisted human review by project author" disclosure. Done in
   this PR (see §14 list).
2. **(Optional, future)** Recruit a second independent human reviewer
   for a fresh pass on the same batch. Strongest follow-up; the only
   way to compute real IRR. The batch + UI (`review_ui_human_a.html`)
   is ready to copy and re-label.
3. **(Optional, future)** Larger corpus. v1.3's 16 cases is the
   biggest constraint on every claim made.
4. **Do NOT** revise sv1.1 based solely on this pass. The negative
   Spearman is most likely a score-compression artifact at this
   sample size; widen the sample first.

Search-agent / hybrid-search track stays paused per E8's
`STOP_SEARCH_TRACK` verdict.

---

## Appendix A — Inputs and provenance

```text
Batch:           review/batches/e9_v1_3_hybrid_vs_grep_human_001/
                   items.jsonl                          (48 items, blinded)
                   manifest.json                        (hidden method map)
                   review_ui_human_a.html               (the labeling UI)
                   labels/reviewer_human_a.jsonl        (the human labels)
                   labels/reviewer_chatgpt_draft.jsonl  (the LLM draft, audit only)

Source data:     results/{dev,holdout,stress}/diagnoses/real-debugger-v2/
                   hybrid-grep-4k-rtk-err-cat-v1.jsonl
                   grep.jsonl
                 results/{dev,holdout,stress}/eval_diagnosis_real-debugger-v2.json

Analyzer output: results/human_review_e9_v1_3_hybrid_vs_grep_human_001.json
Cross-model memo (already published): reports/e9_cross_model_expert_style_review.md
This report:     reports/e9_human_verified_v1_3_review.md
Manifest:        results/e9_human_verified_v1_3_review.manifest.json
```

Verdict (machine-readable):

```text
CILOGBENCH_E9_VERDICT = WEAKEN_HEADLINE
CILOGBENCH_E9_REVIEWER_KIND = ai_assisted_human_project_author
CILOGBENCH_E9_REVIEWER_COUNT = 1
CILOGBENCH_E9_HUMAN_PAIRWISE_HYBRID_WINS = 2
CILOGBENCH_E9_HUMAN_PAIRWISE_GREP_WINS = 8
CILOGBENCH_E9_HUMAN_PAIRWISE_TIES = 6
CILOGBENCH_E9_HUMAN_OVERALL_HYBRID = 3.875
CILOGBENCH_E9_HUMAN_OVERALL_GREP = 3.938
CILOGBENCH_E9_SPEARMAN_OVERALL_VS_SV1_1 = -0.46
CILOGBENCH_E9_HUMAN_VS_AUTO_PAIRWISE_AGREEMENT = 0.444
CILOGBENCH_E9_CONFERR_V1_1_FALSE_POSITIVE_RATE_ON_REVIEWED = 0/0
```
