# E9 reviewer instructions

You are the human reviewer for the **E9** review pass on CILogBench.
Your job is to score CI-failure diagnoses against ground truth, with
the diagnosing method **hidden** from you. Plan to spend ~1–2 minutes
per item; the full batch is 48 items.

## What you have

The batch lives at:

```text
review/batches/e9_v1_3_hybrid_vs_grep_human_001/
  items.jsonl              # one JSON object per review item
  manifest.json            # batch metadata (DO NOT OPEN — it reveals method names)
  labels/                  # write your output here
```

For each item you'll see:

- `review_item_id` — `abs-NNNN` for absolute, `pair-NNNN` for pairwise
- `case_id`, repo / workflow / job / framework metadata
- a short **ground-truth summary** of the actual failure (1–3 sentences)
- optionally, a **required-evidence excerpt** from the raw log
- one diagnosis (absolute mode) or two diagnoses labeled `method_A` /
  `method_B` (pairwise mode; A/B order is randomized per item)

What you **do not** have, and must **not** look up:

- the context method that produced each diagnosis (do NOT open
  `manifest.json`)
- automatic scores (`sv1`, `sv1.1`, `category_match_score_v1_1`,
  `confident_error_v1_1`, etc.)
- token counts or costs
- E5 / E6 / E7 / E8 conclusions
- `required_signals`, `evidence_spans`, the full `ground_truth.json`

## What you score

### Absolute items (32 items)

For each `abs-NNNN`, score the single diagnosis on these axes — all
0–4, integer:

| Axis | 0 | 4 |
|---|---|---|
| `root_cause_correctness` | wrong cause | exactly the GT cause |
| `evidence_support` | invented quotes / no quotes | quotes back the cause |
| `localization_quality` | no useful file/test/step | exact file + line |
| `actionability` | unusable | a junior dev could fix from this |
| `hallucination_severity` | none invented | several big invented details |
| `overall_usefulness` | useless | I'd ship this diagnosis as-is |

Plus one categorical:

```text
abstention_appropriateness:
  appropriate            (diagnosis correctly said "unknown")
  not_appropriate        (diagnosis said "unknown" but evidence was clear)
  not_applicable         (diagnosis did not abstain)
```

Plus a one-line `notes` field. **Do not name the method** in your
notes — the validator rejects labels containing locked method names
(`raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`,
`llm-summary-v1*`). If you feel the urge to write "this is the rtk-log
output," you are unblinding yourself; write a paraphrase instead.

### Pairwise items (16 items)

For each `pair-NNNN`, you see two diagnoses (`method_A`, `method_B`)
for the same case. Pick exactly one of:

```text
winner: "A"
winner: "B"
tie: true                       # both equivalently good
both_bad: true                  # both clearly inadequate
insufficient_information: true  # you can't tell from the items shown
```

Use this priority order to tiebreak when one is better on some axes
and worse on others:

```text
1. correct root cause
2. evidence support
3. localization
4. actionability
5. lower hallucination
6. appropriate abstention
```

Optionally add a one-line `reason`.

## Output JSON shape

Write **one JSON object per line** to:

```text
review/batches/e9_v1_3_hybrid_vs_grep_human_001/labels/reviewer_human_a.jsonl
```

(replace `human_a` with your initials or any non-model identifier).

### Absolute label

```json
{
  "review_item_id": "abs-0001",
  "reviewer_id": "human_a",
  "label_type": "absolute",
  "root_cause_correctness": 3,
  "evidence_support": 4,
  "localization_quality": 3,
  "actionability": 3,
  "hallucination_severity": 0,
  "overall_usefulness": 3,
  "abstention_appropriateness": "not_applicable",
  "notes": "names the failing step and quotes the action's error message"
}
```

### Pairwise label

```json
{
  "review_item_id": "pair-0001",
  "reviewer_id": "human_a",
  "label_type": "pairwise",
  "winner": "B",
  "reason": "B identifies the changelog file path; A only paraphrases"
}
```

For tie / both_bad / insufficient_information:

```json
{
  "review_item_id": "pair-0002",
  "reviewer_id": "human_a",
  "label_type": "pairwise",
  "tie": true,
  "reason": "both correctly identify the merge-conflict marker"
}
```

You may include any of {winner, tie, both_bad, insufficient_information}
but not multiple winners.

## Workflow tips

1. Read the **ground-truth summary first** — it tells you what the
   "right answer" looks like for that case.
2. Then read the diagnosis (or both diagnoses) and ask yourself: *if I
   were a CI on-call who didn't know the cause, would this diagnosis
   help me fix the failure?*
3. **Do not optimize for token cost.** This review is about diagnosis
   *usefulness*. Cost is reported separately by the benchmark; your job
   is the human-judgment piece.
4. **Scores 0 or 4 should have a `notes` reason** — they are the
   strongest claims you can make. Partial credit is the default.
5. **Hallucination is independent of correctness.** A diagnosis can be
   correct *and* invent details (e.g. files that don't exist in the
   case); score `hallucination_severity` accordingly even if
   `root_cause_correctness` is high.
6. If a diagnosis quotes evidence that doesn't appear in the
   ground-truth summary or excerpt, that's a hallucination signal —
   but verify against the case's `raw.log` only when strictly
   necessary, and never copy the evidence text into your `notes`.

## When you're done

Run:

```bash
python3 tools/validate_human_review_labels.py \
  --batch-id e9_v1_3_hybrid_vs_grep_human_001
```

If it reports `0 issues`, you're good. The next steps
(`analyze_human_review.py` + `render_human_review_report.py`) produce
the E9 report; see `docs/review/e9_human_verified_review_protocol.md`
for the full pipeline.
