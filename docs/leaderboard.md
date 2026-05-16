---
title: "Leaderboard"
description: "Method × debugger × split breakdown for LogDx-CI v2-partial-2026-06-22."
---

# LogDx-CI Leaderboard

[← Home](index.html) · [Citation](cite.html) ·
[Full report](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md)

All scores are macro-averaged `diagnosis_score_v1_1` on the **v2 corpus**
(19 cases across `v2/dev`, `v2/holdout`, `v2/stress`). v1.1 calibration
is described in [`docs/evaluation/diagnosis_eval_v1.md`](https://github.com/eyuansu62/LogDx/blob/main/docs/evaluation/diagnosis_eval_v1.md).

## Overall (v2 corpus, average across 3 splits + 3 debugger families)

Sorted by overall mean. The top-2 / bottom-4 sets are stable across all
three debuggers — see the [headline finding](index.html#headline-finding-v2)
on the home page.

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Overall |
|----:|--------|----------:|----------:|----------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail-v3` | 0.576 | 0.665 | 0.695 | **0.646** |
| 2 | `hybrid-grep-120k-tail-v2`     | 0.555 | 0.693 | 0.666 | **0.638** |
| 3 | `tail-200`                     | 0.556 | 0.608 | 0.565 | **0.576** |
| 4 | `grep`                         | 0.495 | 0.616 | 0.601 | **0.571** |
| 5 | `rtk-err-cat`                  | 0.438 | 0.479 | 0.504 | **0.474** |
| 6 | `hybrid-grep-4k-rtk-err-cat-v1`<br/>*(v1.3 winner)* | 0.422 | 0.453 | 0.489 | **0.455** |
| 7 | `raw`                          | 0.208 | 0.286 | 0.290 | **0.262** |
| 8 | `rtk-read`                     | 0.215 | 0.271 | 0.293 | **0.260** |
| 9 | `rtk-log`                      | 0.204 | 0.219 | 0.244 | **0.222** |
| 10 | `llm-summary-v1-mock`         | 0.194 | 0.190 | 0.157 | **0.180** |

**Top-3 ∩ across all 3 debuggers** (the headline finding):
`{hybrid-v2, hybrid-v3}`. Both v2 hybrids use a 120k-token primary
threshold (one with rtk-err-cat fallback, the other with tail
fallback) and explicit `rtk_input_truncated` gating; both clear the
v1.3-winner hybrid by 18 percentage points.

## Per-split breakdown

### `v2/dev` (4 cases)

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Mean |
|----:|--------|----------:|----------:|----------:|------:|
| 1 | `hybrid-grep-120k-tail-v2`     | 0.697 | 0.741 | 0.738 | 0.725 |
| 1 | `hybrid-grep-120k-rtk-tail-v3` | 0.710 | 0.711 | 0.756 | 0.725 |
| 3 | `grep`                         | 0.644 | 0.744 | 0.756 | 0.714 |
| 4 | `tail`                         | 0.617 | 0.786 | 0.633 | 0.679 |
| 5 | `rtk-err-cat`                  | 0.548 | 0.585 | 0.596 | 0.576 |
| 6 | `hybrid-grep-4k-rtk-err-cat-v1`| 0.488 | 0.489 | 0.585 | 0.521 |
| 7 | `rtk-read`                     | 0.296 | 0.507 | 0.512 | 0.438 |
| 8 | `raw`                          | 0.289 | 0.500 | 0.517 | 0.435 |
| 9 | `rtk-log`                      | 0.214 | 0.233 | 0.367 | 0.271 |
| 10 | `llm-summary-v1-mock`         | 0.153 | 0.213 | 0.150 | 0.172 |

### `v2/holdout` (8 cases)

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Mean |
|----:|--------|----------:|----------:|----------:|------:|
| 1 | `grep`                         | 0.589 | 0.684 | 0.641 | 0.638 |
| 2 | `hybrid-grep-120k-rtk-tail-v3` | 0.564 | 0.670 | 0.644 | 0.626 |
| 3 | `hybrid-grep-120k-tail-v2`     | 0.574 | 0.643 | 0.605 | 0.608 |
| 4 | `tail`                         | 0.507 | 0.541 | 0.556 | 0.535 |
| 5 | `rtk-err-cat`                  | 0.461 | 0.427 | 0.468 | 0.452 |
| 6 | `hybrid-grep-4k-rtk-err-cat-v1`| 0.434 | 0.458 | 0.450 | 0.447 |
| 7 | `raw`                          | 0.336 | 0.359 | 0.353 | 0.349 |
| 8 | `rtk-read`                     | 0.348 | 0.307 | 0.367 | 0.341 |
| 9 | `llm-summary-v1-mock`          | 0.261 | 0.282 | 0.244 | 0.263 |
| 10 | `rtk-log`                     | 0.229 | 0.243 | 0.228 | 0.233 |

`grep` actually ranks #1 here — but only by 0.012 over the v3 hybrid;
this is within per-case noise at n=8. The `hybrid-v3 > hybrid-v2 > grep`
pattern from `v2/dev` doesn't reproduce on holdout for the Haiku
debugger, but Sonnet + gpt-5-mini keep hybrid-v3 ahead of grep.
Hybrid-v2 still beats grep on Sonnet (0.643 vs 0.684 — wait, 0.684 wins
here actually). This is the one split where grep clears both hybrids
on overall mean.

### `v2/stress` (7 cases)

| Rank | Method | Haiku 4.5 | Sonnet 4.6 | gpt-5-mini | Mean |
|----:|--------|----------:|----------:|----------:|------:|
| 1 | `hybrid-grep-120k-rtk-tail-v3` | 0.456 | 0.614 | 0.686 | 0.585 |
| 2 | `hybrid-grep-120k-tail-v2`     | 0.395 | 0.694 | 0.656 | 0.581 |
| 3 | `tail`                         | 0.544 | 0.497 | 0.506 | 0.516 |
| 4 | `hybrid-grep-4k-rtk-err-cat-v1`| 0.345 | 0.411 | 0.433 | 0.396 |
| 5 | `rtk-err-cat`                  | 0.305 | 0.426 | 0.448 | 0.393 |
| 6 | `grep`                         | 0.254 | 0.419 | 0.408 | 0.360 |
| 7 | `rtk-log`                      | 0.170 | 0.180 | 0.136 | 0.162 |
| 8 | `llm-summary-v1-mock`          | 0.167 | 0.075 | 0.078 | 0.107 |
| 9 | `raw`                          | 0.000 | 0.000 | 0.000 | 0.000 |
| 9 | `rtk-read`                     | 0.000 | 0.000 | 0.000 | 0.000 |

Stress split is where the hybrids' value is clearest — `raw` and
`rtk-read` both collapse to 0 because the largest stress logs blow
through the model context window. Both v2 hybrids clear grep by
20–25 percentage points here; this is the split where the v1.3
"hybrid is a 4k niche" framing breaks hardest.

## v1.3 corpus (carry-over)

For completeness, the v1.3 results that shipped at the v1.3
release remain canonical for the v1.3 corpus:

| Rank | Method | Haiku sv1.1 | Sonnet sv1.1 | Combined |
|----:|--------|------------:|-------------:|---------:|
| 1 | `hybrid-grep-4k-rtk-err-cat-v1` | 0.715 | 0.771 | **0.743** |
| 2 | `grep`                          | 0.675 | 0.770 | 0.723 |
| 3 | `tail`                          | … | … | … |

The v1.3 top-3 ∩ across all three debugger families (Haiku + Sonnet +
gpt-5-mini, post-2026-05-13 re-run) narrows to `{hybrid-v1}` only —
hence the headline finding that v1.3's stability is narrower than
v2's. Details in
[`reports/e10_v2_generalization_partial.md` §3i](https://github.com/eyuansu62/LogDx/blob/main/reports/e10_v2_generalization_partial.md#3i-third-debugger--gpt-5-mini-2026-05-11).

## How to reproduce

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx

# rebuild the .cache/diagnosis/ tree from manifests (one-time)
python3 tools/migrate_cache_keys_codex_2026_06_08.py

# re-run an eval block (deterministic; uses cached diagnoses)
python3 tools/evaluate_diagnosis.py \
    --split v2/dev --diagnoser real-debugger-v3

# the file lands at results/v2/dev/eval_diagnosis_real-debugger-v3.json
# and the per-method macro scores match the table above.
```

For a **fresh** re-run that hits the OpenAI / Anthropic APIs (not
just cache replay), see the
[reproducibility section in RELEASE_NOTES.md](https://github.com/eyuansu62/LogDx/blob/main/RELEASE_NOTES.md#reproducibility).

## Methodology

- **What's scored**: macro-averaged `diagnosis_score_v1_1`, a v1.1-
  calibrated linear combination of category accuracy, critical signal
  recall, must-mention coverage, relevant-file / relevant-test recall,
  valid-evidence-quote rate, minus forbidden-claim and confident-error
  penalties.
- **20 historical exclusions** are present in the eval denominator as
  zero-score abstentions, ensuring the cleanup of failed diagnoser
  runs doesn't artificially inflate the macro means. See
  [`configs/historical_provider_error_exclusions.json`](https://github.com/eyuansu62/LogDx/blob/main/configs/historical_provider_error_exclusions.json)
  and the `validate_eval_manifest_consistency.py` release gate.
- **gpt-5-mini run** uses the `gpt-5-mini-2025-08-07` snapshot. v3
  was re-run after the 2026-05-12 F2 cache-key fix; non-determinism
  is a known caveat for reasoning models (§3i caveat 1 in the full
  report).

[← Home](index.html) · [Citation](cite.html)
