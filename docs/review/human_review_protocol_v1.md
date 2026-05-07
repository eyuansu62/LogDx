# Human review protocol v1 (M11)

M11 adds blinded human review to calibrate CILogBench's deterministic
diagnosis metrics against expert judgment. It is NOT for adding new
methods or tuning prompts.

## What M11 measures

For a fixed diagnoser run under a frozen protocol:

- does each method's diagnosis feel correct, evidence-backed, and
  actionable to a domain reviewer who sees the diagnosis but not the
  method identity?
- do deterministic metrics (category accuracy, critical-signal
  mention, forbidden claims, valid-evidence-quote rate,
  diagnosis_score_v1) track the reviewer's judgment, or do they
  diverge?

## Two review modes

- **Absolute rubric** — per diagnosis, reviewer scores 7 axes on 0–4.
- **Pairwise** — two diagnoses for the same case shown side-by-side
  with randomized A/B order; reviewer picks A / B / tie / both bad /
  insufficient info.

Both modes hide method identity in the reviewer-facing files. Hidden
mappings live only in the batch `manifest.json`.

## Initial recommended scope

- **Diagnoser:** one real fixed debugger from M10 (or the stub during
  infrastructure validation).
- **Cases:** the 5 holdout cases from `cases/holdout/`.
- **Methods:** `raw`, `grep`, `rtk-err-cat`, `rtk-log` (add
  `llm-summary-v1-<slug>` when a real summarizer exists).

Start small; a 5×4 = 20-item absolute batch is enough for a first
calibration pass. Pairwise on the same 5 cases with 4C2=6 pairs gives
another 30 items.

## Blinding rules

Reviewers MAY see:

- case metadata (repo, workflow_name, job_name, framework)
- a short ground-truth summary (1–3 sentences)
- a tiny raw-log evidence excerpt when strictly necessary
- the diagnosis being scored

Reviewers must NOT see:

- the context method name (`raw` / `grep` / `rtk-*` / `llm-summary-*`)
- method brand or token counts
- any previously computed benchmark metric
- the full `ground_truth.json` (it gives away too much)

## Label schema (0–4 absolute)

| score | meaning |
|---|---|
| 0 | absent or wrong |
| 1 | poor |
| 2 | partial |
| 3 | good |
| 4 | excellent |

Axes:

- `root_cause_correctness` — does the named cause match the real cause?
- `evidence_support` — does the cited evidence actually support the
  cause?
- `localization_quality` — does the diagnosis point at the right
  file/test/step?
- `actionability` — can an engineer act on the suggested fix?
- `hallucination_severity` — **higher = worse**: 0 = nothing
  unsupported; 4 = multiple invented facts.
- `overall_usefulness` — the single number you would tell someone
  else.

Plus a categorical `abstention_appropriateness` with values
`correct_abstention`, `inappropriate_abstention`, or `not_applicable`.

## Ground rules for reviewers

1. Score only from what you see. Do not open the raw log unless the
   item explicitly provides an excerpt.
2. Do not try to guess the method. If you do guess, do not let it
   influence the score.
3. Prefer partial credit over all-or-nothing. A correct-but-vague
   diagnosis is a 2 or 3 on actionability, not a 0.
4. Hallucination severity is independent of correctness. A confident
   invented fact is severe even if the cause was also correct.
5. Write one-line `notes` for anything that caused a score above 2 or
   below 2. Do not name methods in notes.

## Workflow

1. `python tools/build_human_review_set.py --protocol ... --split
   holdout --diagnoser <name> --methods raw,grep,rtk-err-cat,rtk-log
   --batch-id holdout-<name>-001 --mode both`
2. Reviewers open `review/batches/<batch_id>/items.jsonl` and write
   labels to `review/batches/<batch_id>/labels/reviewer_<id>.jsonl`.
3. `python tools/validate_human_review_labels.py --batch-id ...`
4. `python tools/analyze_human_review.py --batch-id ...`
5. `python tools/render_human_review_report.py --batch-id ...`

## Correlation with deterministic metrics

The analysis joins reviewer labels with
`results/<split>/eval_diagnosis_<diagnoser>.json`:

- `category_accuracy` ↔ `root_cause_correctness`
- `critical_signal_mention_recall` ↔ `evidence_support`
- `valid_evidence_quote_rate` ↔ `evidence_support`
- `forbidden_claim_violations` ↔ `hallucination_severity`
- `diagnosis_score_v1` ↔ `overall_usefulness`

Report Spearman correlation for ordinal pairs, raw agreement for
categorical ones. With tiny samples, call these "directional" only.

## What M11 does NOT change

- The benchmark protocol lock.
- Deterministic scoring code.
- Method-specific prompts.
- Annotations (unless M11 surfaces an annotation bug; then go through
  `docs/protocol/annotation_freeze_policy.md`).

## Honest use

M11 gives CILogBench a calibration check. It does NOT convert the
benchmark into a human-evaluated leaderboard. Report human results
alongside, not in place of, deterministic metrics.
