# E9 — Human-verified review protocol

E9 is the first **human** review pass on CILogBench. Earlier review
(E2/E2b) used an LLM-as-judge expert reviewer (`claude-opus-4-7-expert`)
and the calibration documents (`reports/experiments/e2_calibration_memo.md`,
`reports/experiments/e2b_score_calibration_v1_1.md`) and the v1.3 limitations doc
(`docs/reports/cilogbench_v1_3_limitations.md` §2) all explicitly flag
that as expert-model review, not human review. E9 closes that gap by
running a real human pass on the v1.3 headline comparison.

## Scope

| Field | Value |
|---|---|
| Protocol | `cilogbench-v1.3` |
| Splits | dev (5) + holdout (5) + stress (6) = 16 cases |
| Diagnoser | `real-debugger-v2` (Sonnet 4.6) |
| Methods | `hybrid-grep-4k-rtk-err-cat-v1`, `grep` (blinded as `method_A` / `method_B`) |
| Items | 32 absolute + 16 pairwise = 48 |
| Batch ID | `e9_v1_3_hybrid_vs_grep_human_001` |
| Reviewer ID format | `human_a`, `human_b`, … (NOT model names) |

## Anti-leakage rules

The reviewer **may** see:

- `case_id`, `repo`, `workflow_name`, `job_name`, `framework`
- a short ground-truth summary (1–3 sentences)
- one short raw-log evidence excerpt when strictly necessary
- the diagnosis under review (or both diagnoses for pairwise items)

The reviewer **must not** see:

- the context method name (`hybrid-...` / `grep` / `raw` / `tail` / `rtk-*` / `llm-summary-*`)
- token counts, costs, or rankings
- the diagnosis automatic scores (sv1, sv1.1, category_match, etc.)
- E5 / E6 / E7 / E8 conclusions
- `required_signals`, `evidence_spans`, the full `ground_truth.json`

The hidden method map lives **only** in
`review/batches/e9_v1_3_hybrid_vs_grep_human_001/manifest.json`.

## Reviewer ID rule

Use a strictly non-model identifier. Acceptable:
`reviewer_human_a.jsonl`, `reviewer_human_b.jsonl`,
`reviewer_$(your_initials).jsonl`.

**Not acceptable:** `reviewer_claude-*.jsonl`,
`reviewer_gpt-*.jsonl`, `reviewer_*-expert.jsonl`. The label validator
rejects forbidden method names in `notes` / `reason` and the analyzer
will treat any model-shaped reviewer ID as suspicious.

## Acceptance criteria

The plan defines five gates (A–E):

- **A — batch creation:** ✅ Already done. 48 items, blinded, randomized A/B,
  manifest records protocol-lock SHA. (See acceptance script in this repo.)
- **B — human labels:** at least one human reviewer's label file exists,
  passes `tools/validate_human_review_labels.py`, and contains 32 absolute +
  16 pairwise rows. **Pending.**
- **C — analysis:** `tools/analyze_human_review.py` produces the standard
  E9 metrics (overall_usefulness mean, pairwise win rate, sv1.1 correlation,
  human/auto winner agreement, disagreement list, IRR if applicable).
  **Pending.**
- **D — report:** `reports/experiments/e9_human_verified_v1_3_review.md` plus an alias
  copy of the analyze output as
  `results/e9_human_verified_v1_3_review.json`. **Pending.**
- **E — public-report update:** v1.3 technical report / one-pager /
  limitations doc / README updated with the E9 outcome. **Pending.**

## Decision rules (verbatim from the plan)

The E9 report must pick exactly one verdict:

```text
CONFIRM_HEADLINE
  human pairwise hybrid >= grep
  OR human overall_usefulness hybrid >= grep - 0.25 (on 0-4 scale)
  AND sv1.1 correlation with overall usefulness >= 0.5
  AND no systematic human rejection of hybrid diagnoses

WEAKEN_HEADLINE
  human reviewers clearly prefer grep BUT hybrid is still close and much cheaper

REVISE_EVALUATOR
  sv1.1 correlation with human usefulness < 0.4
  OR human/auto winner agreement < 0.5

REVIEW_INCONCLUSIVE
  too many ties / poor agreement / labels inconsistent / sample too small
```

If the verdict is `REVIEW_INCONCLUSIVE`, the v1.3 public technical
report's "expert-model review only" caveat **stays** until a second
reviewer or larger sample lands.

## Pipeline

```bash
# 1. (already done) build the batch:
#    review/batches/e9_v1_3_hybrid_vs_grep_human_001/

# 2. Human reviewer fills labels into:
#    review/batches/e9_v1_3_hybrid_vs_grep_human_001/labels/reviewer_human_a.jsonl
#    See docs/review/e9_reviewer_instructions.md for the rubric and JSON shape.

# 3. Validate labels (no method names in notes, scores in [0,4], etc.):
python3 tools/validate_human_review_labels.py \
  --batch-id e9_v1_3_hybrid_vs_grep_human_001

# 4. Compute the E9 metrics:
python3 tools/analyze_human_review.py \
  --batch-id e9_v1_3_hybrid_vs_grep_human_001

# 5. Render the E9 report (with verdict):
python3 tools/render_human_review_report.py \
  --batch-id e9_v1_3_hybrid_vs_grep_human_001
```

The existing M11 review tools support every step from #3 onward — there
is no E9-specific tooling beyond this protocol doc and the merged batch
that has already been built.

## Public-report updates after E9

Per the plan §"Public-report update after E9":

| Verdict | What to change in the public report |
|---|---|
| `CONFIRM_HEADLINE` | Replace the "expert-model review only" caveat with: *"sv1.1 was originally calibrated by expert-model review and later spot-checked / verified by human review on the v1.3 hybrid-vs-grep comparison."* |
| `WEAKEN_HEADLINE` | State that automatic sv1.1 ranked hybrid #1, but human review found grep preferable or tied. |
| `REVISE_EVALUATOR` | Mark scores as provisional; consider keeping the report internal until evaluator v2. |
| `REVIEW_INCONCLUSIVE` | Leave the v1.3 caveat as-is and queue a second reviewer or larger sample. |
