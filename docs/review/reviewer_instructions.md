# Reviewer instructions

You are evaluating a diagnosis produced for a CI failure. Your job is to
score whether the diagnosis is correct, evidence-backed, and useful —
without trying to figure out which context method produced it.

## What you have

For each review item:

- **Case metadata** — repo, workflow, job, framework.
- **A short ground-truth summary** — 1–3 sentences in plain English.
- **(Optional) a short evidence excerpt** — a few raw-log lines.
- **One diagnosis** (absolute mode) OR **two diagnoses labeled A and B**
  (pairwise mode). A/B order is randomized per item.

## What you score (absolute mode)

Six 0–4 scales plus one categorical:

- **root_cause_correctness**: does the named cause match the real one?
- **evidence_support**: does the cited evidence actually support the
  cause? (If the diagnosis quotes lines, do they come from the case?)
- **localization_quality**: does the diagnosis point at the right
  file / test / step?
- **actionability**: could an engineer start fixing the bug given this
  diagnosis?
- **hallucination_severity** (higher = worse): did the diagnosis
  invent things? 0 = none; 1 = one minor; 2 = several minor; 3 = one
  major invented claim; 4 = multiple major invented claims.
- **overall_usefulness**: the single number you'd quote to a
  colleague.

Plus:

- **abstention_appropriateness**: `correct_abstention` if the
  diagnosis said `unknown` and the evidence genuinely doesn't support
  a call; `inappropriate_abstention` if it said `unknown` when the
  evidence clearly supports a specific cause; `not_applicable`
  otherwise.

0–4 anchor table:

| score | meaning |
|---|---|
| 0 | absent or wrong |
| 1 | poor |
| 2 | partial |
| 3 | good |
| 4 | excellent |

## What you choose (pairwise mode)

Pick one of: `A`, `B`, `tie`, `both_bad`, `insufficient_information`.
Write one sentence in `reason` explaining your choice. Do not speculate
about which tool produced which diagnosis.

## Blinding rules

- Do not open any file outside the provided excerpt.
- Do not try to guess the method. If you do, do not let it influence
  your score.
- Do not mention method names (raw, grep, rtk-*, llm-summary-*) in
  `notes` or `reason`. They will be flagged by the validator.

## Writing `notes`

One short line per item, only when a score is especially high (≥3) or
low (≤1). Focus on the evidence: "quotes a line that doesn't appear in
the excerpt", "names the wrong test but points to the right file",
etc.

## How to label

Put labels in:

```
review/batches/<batch_id>/labels/reviewer_<your_id>.jsonl
```

One JSON line per review item you score. Minimal absolute example:

```json
{"review_item_id":"hr-001","reviewer_id":"reviewer_1","label_type":"absolute","root_cause_correctness":3,"evidence_support":2,"localization_quality":3,"actionability":3,"hallucination_severity":0,"abstention_appropriateness":"not_applicable","overall_usefulness":3,"notes":"correct cause, evidence is thin","created_at":"2026-04-24T00:00:00Z"}
```

Minimal pairwise example:

```json
{"review_item_id":"pair-001","reviewer_id":"reviewer_1","label_type":"pairwise","winner":"A","reason":"A names the failing test; B only says the job failed.","both_bad":false,"tie":false,"insufficient_information":false,"created_at":"2026-04-24T00:00:00Z"}
```

## After labeling

1. `python tools/validate_human_review_labels.py --batch-id <id>`
2. `python tools/analyze_human_review.py --batch-id <id>`
3. `python tools/render_human_review_report.py --batch-id <id>`

You do not need to run these — the benchmark maintainer will. But
running them locally is a good self-check.
