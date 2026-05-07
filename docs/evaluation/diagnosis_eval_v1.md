# diagnosis_eval_v1

Deterministic evaluation of a diagnoser's outputs against ground truth.
Implemented by `tools/evaluate_diagnosis.py`. **No LLM judge.** All
eleven metrics are computed from explicit string / list / category
comparisons.

## Why deterministic

LLM-as-judge has a known failure mode: it tends to reward verbosity,
surface plausibility, and stylistic match with its own training
distribution. CILogBench wants to be honest about downstream debugging
value, so M5's first-pass evaluator checks only what we annotated:

- Did the diagnoser get the category right?
- Did it actually mention the signals we flagged as critical?
- Did it quote lines that appear in the provided context (rather than
  inventing them)?
- Did it leak any claim we explicitly marked as wrong?

If this proxy is "too strict" for a given diagnoser, that is
information — usually meaning the annotation is incomplete or the
diagnoser paraphrases. Semantic grading arrives in a later milestone,
alongside a judge model and a human spot-check loop.

## Metrics (per case, then macro-averaged per context method)

### 1. `diagnosis_success`

Boolean. `true` when both:

- `metadata.provider_error` is `null`, AND
- at least one of `summary` / `root_cause` is non-empty.

`success_rate` = fraction true over cases.

### 2. `category_accuracy`

Exact match between `diagnosis.root_cause_category` and
`ground_truth.root_cause.category`. `unknown` never counts as correct
unless the ground truth category is also `unknown`. `N/A` when the
ground truth has no category.

A small alias table maps ground-truth names to the diagnosis enum for
categories that were renamed across milestones
(e.g. `lint_error → lint_failure`). Additions to this table must be
justified here. Current aliases:

| ground truth | diagnosis enum |
|---|---|
| `lint_error` | `lint_failure` |
| `snapshot_diff` | `test_assertion` |
| `generic_error` | `other` |

### 3. `required_signal_mention_recall`

For every signal in `ground_truth.required_signals`, check whether its
`value`, one of its `aliases`, or its `file` path appears as a literal
substring of the diagnosis *text blob* (ANSI-stripped). The blob is
`summary + root_cause + relevant_files + relevant_tests + evidence
quotes + evidence reasons + suggested_fix`.

`N/A` when `required_signals` is empty.

### 4. `critical_signal_mention_recall`

Same as #3 but restricted to `importance == "critical"` signals. `N/A`
when no critical signals exist.

### 5. `relevant_file_recall`

Fraction of `ground_truth.relevant_files` appearing (literal substring)
in the diagnosis text blob. `N/A` when `relevant_files` is empty.

### 6. `relevant_test_recall`

Same idea for `ground_truth.relevant_tests`. `N/A` when empty.

### 7. `must_mention_coverage`

Fraction of `ground_truth.expected_diagnosis.must_mention` strings
appearing in the diagnosis text blob. `N/A` when `must_mention` is
absent/empty.

### 8. `forbidden_claim_violations`

List (per case) and rate (per method) of
`ground_truth.expected_diagnosis.must_not_claim` strings that do appear
in the diagnosis text blob. This is a deterministic **hallucination
proxy**: saying `"network failure"` when the real cause is `formatting`
is tracked here.

### 9. `valid_evidence_quote_rate`

For every `diagnosis.evidence[].quote`, check whether the quote (after
ANSI strip and whitespace-run normalization) appears as a literal
substring of the **context text** (not the diagnosis blob). Quotes
shorter than 8 characters are skipped — they contribute too much noise
to the metric. `N/A` when `evidence` is empty.

A low rate flags diagnosers that make up citations. A 100% rate does
not prove the evidence is *relevant* — only that it was actually in
the context.

### 10. `abstention_rate`

A diagnosis is an abstention when either:

- `root_cause_category == "unknown"`, OR
- `confidence < 0.25`.

Abstention is not automatically bad. When the context is poor, "I
don't know" is better than a confident wrong answer. Read this metric
alongside `confident_error_rate` — a healthy diagnoser uses the
abstention channel.

### 11. `confident_error_rate`

A case is a confident error when:

- `confidence >= 0.70`, AND
- (category is wrong, OR `forbidden_claim_violations` is non-empty).

This is the key **agent-safety** metric. A high rate means the
diagnoser sounds sure while being wrong — the worst failure mode for a
downstream agent.

## Null handling

Every metric can be `null` (rendered as `N/A`). Nulls are excluded from
macro averages rather than treated as zero. This matters for
low-annotation cases: a case with no `must_mention` list should not
pull down the method's `macro_must_mention_coverage`.

## Experimental composite `diagnosis_score_v1`

Defined as:

```
diagnosis_score_v1 =
    0.25 * category_accuracy
  + 0.30 * critical_signal_mention_recall
  + 0.20 * must_mention_coverage
  + 0.10 * relevant_file_recall
  + 0.10 * relevant_test_recall
  + 0.05 * valid_evidence_quote_rate
  - 0.25 * (forbidden_claim_violation ? 1 : 0)
  - 0.25 * (confident_error ? 1 : 0)

clamp to [0, 1]
```

**Do not use this as the leaderboard.** It hides trade-offs the
individual metrics surface (an abstaining diagnoser will score lower
than a confident-wrong one even though the former is safer for some
downstream uses). Report the individual metrics first; the composite
is only useful for rough ordering during development.

## When numbers disagree

If a method has high `critical_signal_mention_recall` but low
`category_accuracy`, the context preserves the evidence but the
diagnoser picks the wrong label. That is a diagnoser problem, not a
context problem — consider a different diagnoser or a better prompt.

If a method has low `critical_signal_mention_recall` but
`diagnosis_success` remains 100% and `abstention_rate` is also low,
the diagnoser is probably hallucinating. Check
`valid_evidence_quote_rate` — a drop there confirms it.

If `forbidden_claim_violations` is nonzero *and*
`confident_error_rate` is nonzero on the same rows, the diagnoser is
confidently wrong in exactly the way the annotation anticipated. Flag
those cases during review.

## Mock diagnoser caveat

When `diagnoser == debugger-v1-mock`, every number in the report is
shaped by a small rule-based pattern scan. Use the mock to verify the
pipeline (schema, evaluator, report rendering) runs end-to-end and
produces plausible shapes. Do not quote mock numbers as evidence
about any specific context method. Real benchmarking requires a real
diagnoser wired through the `command` provider.
