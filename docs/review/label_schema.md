# Human review label schema (M11)

## Files

```
schemas/human_review_item.schema.json     per-item contract (reviewer input)
schemas/human_review_label.schema.json    per-label contract (reviewer output)
schemas/human_review_report.schema.json   analysis output contract
```

## Absolute label required fields

```
review_item_id  string
reviewer_id     string
label_type      "absolute"

root_cause_correctness      integer 0..4
evidence_support            integer 0..4
localization_quality        integer 0..4
actionability               integer 0..4
hallucination_severity      integer 0..4   (higher = worse)
overall_usefulness          integer 0..4
abstention_appropriateness  "correct_abstention" | "inappropriate_abstention" | "not_applicable"
```

Optional: `notes`, `created_at`.

## Pairwise label required fields

```
review_item_id  string
reviewer_id     string
label_type      "pairwise"
```

Plus at least one of:

```
winner     "A" | "B"
tie        true
both_bad   true
insufficient_information true
```

Optional: `reason`, `notes`, `created_at`.

## File layout

```
review/batches/<batch_id>/
  items.jsonl                 — reviewer-facing items (blinded)
  manifest.json               — hidden method map + batch metadata
  labels/
    reviewer_<id>.jsonl       — one label row per item scored
```

## Validation

`tools/validate_human_review_labels.py --batch-id <id>` checks:

1. Every label row has the required fields for its label_type.
2. All integer scores are in [0, 4].
3. Every `review_item_id` exists in `items.jsonl`.
4. No method name (`raw`, `grep`, `rtk-read`, `rtk-log`,
   `rtk-err-cat`, `llm-summary-v1`) appears in `notes` or `reason`.
   This is an anti-unblinding guard — if a reviewer sneaks a method
   name in, the label is rejected so the batch cannot be analyzed.
5. Unknown fields are allowed but are ignored during analysis.

## Analysis output

`tools/analyze_human_review.py --batch-id <id>` computes and writes
`results/human_review_<batch_id>.json` per
`schemas/human_review_report.schema.json`:

- Per-method mean of each 0–4 axis.
- Per-method pairwise W/L/T counts.
- Correlation of human axes with deterministic metrics
  (`category_accuracy`, `critical_signal_mention_recall`,
  `valid_evidence_quote_rate`, `forbidden_claim_violations`,
  `diagnosis_score_v1`).
- Top N disagreements between human `overall_usefulness` and
  `diagnosis_score_v1`.
- Reviewer-pair agreement when ≥2 reviewers labeled the same item
  (raw agreement + Spearman for ordinal axes).

## Anti-unblinding guard

The validator rejects labels containing any case-insensitive substring
matching the locked method names. When a reviewer needs to write a
legitimate note that happens to include a forbidden word (rare), they
should paraphrase.

## Rubric discipline

- Hallucination severity is independent of correctness. A fully
  correct diagnosis that adds one invented detail is still severity=1.
- Partial credit is the default. A 0 or 4 on an axis should have a
  reason in `notes`.
- `abstention_appropriateness` is only `not_applicable` when the
  diagnoser did not abstain. If it abstained correctly, say so.
