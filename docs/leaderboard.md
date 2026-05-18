---
title: "Leaderboard"
description: "Method × debugger leaderboard for LogDx-CI v1.0 (35 cases)."
---

# LogDx-CI Leaderboard

[← Home](index.html) · [Citation](cite.html) ·
[Technical report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

All scores are case-count-weighted macro `diagnosis_score_v1_1`
aggregated across the **35-case v1.0 corpus** (3 splits: `dev`,
`holdout`, `stress`). The score formula (a calibrated linear
combination of category accuracy, signal-mention recall, file/test
recall, must-mention coverage, valid-evidence-quote rate, with
forbidden-claim and confident-error penalties) is documented in
[`docs/evaluation/diagnosis_eval_v1.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/evaluation/diagnosis_eval_v1.md).

## Overall (35-case corpus, 3 debugger families)

Sorted by overall mean across the three debugger families.

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Overall |
|----:|--------|----------:|----------:|----------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | 0.624 | 0.679 | 0.706 | **0.670** |
| 2 | `hybrid-grep-120k-tail`     | 0.610 | 0.730 | 0.658 | **0.666** |
| 3 | `grep`                      | 0.578 | 0.684 | 0.655 | **0.639** |
| 4 | `tail-200`                  | 0.595 | 0.624 | 0.623 | **0.614** |
| 5 | `hybrid-grep-4k-rtk-err-cat`<br/><sub>*(earlier 4k-threshold hybrid; replaced — see report)*</sub> | 0.552 | 0.597 | 0.571 | **0.573** |
| 6 | `rtk-err-cat`               | 0.455 | 0.488 | 0.467 | **0.470** |
| 7 | `raw`                       | 0.324 | 0.368 | 0.367 | **0.353** |
| 8 | `rtk-read`                  | 0.329 | 0.369 | 0.349 | **0.349** |
| 9 | `llm-summary-v1-mock`       | 0.343 | 0.348 | 0.294 | **0.328** |
| 10 | `rtk-log`                  | 0.238 | 0.262 | 0.249 | **0.249** |

## Headline cross-family agreement

The **top-3** under each debugger family separately:

| Family | Top 3 |
|--------|-------|
| Claude Haiku 4.5 | `hybrid-grep-120k-rtk-tail`, `hybrid-grep-120k-tail`, `tail-200` |
| Claude Sonnet 4.6 | `hybrid-grep-120k-tail`, `grep`, `hybrid-grep-120k-rtk-tail` |
| OpenAI gpt-5-mini | `hybrid-grep-120k-rtk-tail`, `hybrid-grep-120k-tail`, `grep` |

**∩ across all 3 families:**
`{hybrid-grep-120k-rtk-tail, hybrid-grep-120k-tail}` —
**both 120k-threshold hybrid routers**, beating every non-hybrid
single-method baseline on at least one family and on the overall
mean.

The **bottom-4 set** also agrees across all three families:
`{raw, rtk-read, rtk-log, llm-summary-v1-mock}` — context that's
either too large (raw / rtk-read on big logs) or too lossy
(rtk-log / mock summary) for the LLM to identify root causes.

## Methodology evolution

`hybrid-grep-4k-rtk-err-cat` (rank 5 overall) was an earlier hybrid
designed in the prototype phase, tuned at a 4k-token primary
threshold. Its successors `hybrid-grep-120k-tail` and
`hybrid-grep-120k-rtk-tail` use a 120k-token threshold with
explicit `rtk_input_truncated` gating and clear the earlier hybrid
by **~10 percentage points** on the 35-case corpus.

See the [technical report §3](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#3-headline-result--full-table)
for the prototype-vs-formal corpus analysis that motivated the
threshold change.

## A note on `llm-summary-v1-haiku`

A real Anthropic Haiku summarizer (`llm-summary-v1-haiku`) was run
during prototyping on a 16-case subset but **not** re-run on the
full 35-case corpus, so it's not on the headline leaderboard. Its
subset score is 0.490 on Haiku-as-debugger; Sonnet and gpt-5-mini
aren't scored against it (would have required a paid re-run). See
the report §3 for context.

## How to reproduce a number

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# rebuild the .cache/diagnosis/ tree from canonical manifests (one-time)
python3 tools/migrate_cache_keys_codex_2026_06_08.py

# re-run an eval block (deterministic; uses cached diagnoses)
python3 tools/evaluate_diagnosis.py \
    --split v2/dev --diagnoser real-debugger-v3

# the file lands at results/v2/dev/eval_diagnosis_real-debugger-v3.json
# and the per-method macro scores match the breakdown in §3 of the
# technical report.
```

The on-disk split names (`dev`, `holdout`, `stress`,
`v2/dev`, `v2/holdout`, `v2/stress`) reflect two methodology-
development waves during prototyping; both are merged into the
v1.0 corpus. See [the release notes](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#a-note-on-internal-naming)
for the mapping.

For a **fresh** re-run that hits the OpenAI / Anthropic APIs (not
just cache replay), see the
[reproducibility section in RELEASE_NOTES.md](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#reproducibility).

## 20 historical exclusions

The eval injects zero-score abstention rows for 20 (split,
diagnoser, method, case) tuples documented in
[`configs/historical_provider_error_exclusions.json`](https://github.com/eyuansu62/LogDx/blob/main/configs/historical_provider_error_exclusions.json).
These correspond to transient model / CLI / API failures during the
2026-04..05 prototype sweeps that were removed by the 2026-06-09 /
2026-06-10 cleanups. Without injection the eval denominator would
artificially shrink, inflating the macro means. The
`validate_eval_manifest_consistency.py` release gate verifies that
every excluded eval row has `diagnosis_success=False` + zeroed
score fields.

## Method references

Methods in the leaderboard are implemented as follows. Methods with
external dependencies are linked to their upstream projects.

| Method | Implementation |
|--------|----------------|
| `raw` | full log handed to the model |
| `tail-200` | last 200 lines |
| `grep` | regex-filtered failure-pattern lines + 3/8 context, see [`docs/methods/diagnosis.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/methods/diagnosis.md) |
| `rtk-read`, `rtk-log`, `rtk-err-cat` | three modes of **[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)** by rtk-ai. See [`docs/methods/rtk.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/methods/rtk.md) for setup. |
| `llm-summary-v1-mock` | mock summarizer (deterministic stub; the corresponding real-Haiku run is `llm-summary-v1-haiku`, prototype-only) |
| `hybrid-grep-4k-rtk-err-cat` | earlier 4k-threshold hybrid using grep primary + rtk-err-cat fallback (replaced by the 120k hybrids) |
| `hybrid-grep-120k-tail` | grep ≤ 120k tokens else tail-200 |
| `hybrid-grep-120k-rtk-tail` | grep ≤ 120k tokens else rtk-err-cat (if not truncated and ≤ 120k) else tail-200 |

[← Home](index.html) · [Citation](cite.html)
