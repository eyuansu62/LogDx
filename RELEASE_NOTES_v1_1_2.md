# LogDx-CI v1.1.2 — Release Notes

**Tag**: `v1.1.2`
**Date**: 2026-05-20
**Type**: Polish / hygiene release (no protocol lock changes; no
ranking changes; no new diagnosis runs)

## TL;DR

A batch of low-impact polish items from the post-v1.1.1 project
review. No new data, no schema bumps, no ranking changes. Tightens
the published artifacts so the v1.1.1 numbers are easier for an
outside reviewer to trust.

## Changes

### 1. Frozen v1.1.1 protocol lock

New file: `protocols/logdx-ci-v1.1.1.lock.json` (27 hashes — 10
schemas, 4 prompts, 4 evaluators, 9 hybrid-baseline configs — over
35 cases × 6 splits).

Previously the v1.1.1 release didn't ship its own lock; downstream
reproducibility relied on the rolling `v2-partial-2026-05-20` lock.
Future schema/evaluator drift can no longer silently invalidate
v1.1.1's published numbers — `tools/validate_protocol_lock.py
--protocol protocols/logdx-ci-v1.1.1.lock.json` is now the canonical
reproducibility anchor for the v1.1.1 release.

### 2. Mock moved out of leaderboard tables

The legacy `llm-summary-v1-mock` row has been removed from both the
single-shot headline table (`docs/leaderboard.md`) and the homepage
(`docs/index.md`) and the agent-loop table. Its retained numbers
(0.328 / 0.715 / 0.133 conf_err / 432k tokens) now live in a
dedicated [`## Appendix: legacy baselines`](docs/leaderboard.md#appendix-legacy-baselines)
section that explains why the mock is kept (CI smoke test, lower-
bound data point, v1.0 reproducibility) and is not a current
recommendation.

### 3. chunk_lines=100 caveat promoted to headline-area footnote

The three cases that re-chunked at `chunk_lines=100` (nodejs and
the two pytest-sklearn stress cases) are now disclosed in a
footnote directly under the headline ranking table on
`docs/leaderboard.md` and `docs/index.md`. Previously the
disclosure was buried in a v1.1 promotion section near the bottom
of the leaderboard page.

### 4. v1.3 historical reports got deprecation banners

Added prominent top-of-doc banners to:
- `docs/protocol/cilogbench_v1_3.md`
- `docs/reports/cilogbench_v1_3_one_pager.md`
- `docs/reports/cilogbench_v1_3_technical_report.md`

Each banner explains that the v1.3 verdict on
`llm-summary-v1-haiku` ("not competitive with grep / hybrid") has
been reversed by v1.1.1's 35-case × 4-diagnoser backfill and links
to the live leaderboard. v1.3's lock file stays frozen for
reproducibility; the live ranking has moved on.

### 5. USD cost reporting

Pinned provider list prices in `configs/pricing/snapshot_2026_05_20.json`
(Anthropic Haiku 4.5 / Sonnet 4.6, OpenAI gpt-5-mini). New script
`tools/compute_usd_costs.py` computes per-method per-case dollar
cost from real per-call API usage (reducer side) plus eval-manifest
macro token counts (diagnoser side, treated identically across all
methods × families).

A new "USD cost" table now lives in `docs/leaderboard.md` between
the token-cost-breakdown table and the agent-loop section. Highlight:

- Top-2 hybrids: ~$0.03/case end-to-end
- `tail-200`: $0.012/case (cheaper but ranks 5)
- `raw` / `rtk-read`: ~$0.39/case (the diagnoser-side cost
  ceiling without a reducer)
- `llm-summary-v1-haiku`: $1.76/case (the reducer dominates;
  diagnoser side is only $0.006)

The pricing snapshot file documents the caveat that list prices
change; re-run `tools/compute_usd_costs.py --pricing <new-snapshot>`
against a fresh snapshot for current numbers.

### 6. Protocol lock filename cleanup

The two-namespace mess (`protocols/cilogbench-*.lock.json` from
pre-rebrand E1-E9 milestones + `protocols/logdx-ci-*.lock.json`
post-rebrand) has been resolved. The 10 `cilogbench-*` locks moved
to `protocols/legacy/`; all references in `tools/render_e*.py`,
`tools/analyze_*.py`, and historical v1.3 docs were updated to the
new paths.

`protocols/README.md` documents the current vs legacy layout and
the convention for new releases (`logdx-ci-vX.Y[.Z]`).

### 7. HuggingFace dataset drift gate

New file: `huggingface/corpus_fingerprint.json` (sha256 over every
per-case file × 35 cases). New script
`tools/validate_corpus_fingerprint.py` walks cases/, recomputes the
fingerprint, and fails CI if it doesn't match the committed file.

Workflow: after any cases/ change, the committer must (1) re-run
`huggingface/upload.sh` to push to HF, and (2) run
`tools/validate_corpus_fingerprint.py --update` to refresh the
fingerprint. The two steps are wired together so the repo-side
fingerprint can't drift from the HF mirror unintentionally.

This gate is now part of the CI release-gate batch in
`.github/workflows/ci.yml`.

## What did NOT change

- **Rankings**: zero changes to any leaderboard row. Same `diagnosis
  _score_v1_1`, same `confident_error_rate_v1_1`, same `total_tokens`.
- **Schemas / prompts / evaluator code**: untouched. v1.1.1 lock and
  v1.1.2 lock have identical SHA256 fingerprints across all 27
  tracked hashes (this is verified by `tools/validate_protocol_lock.py`).
- **Corpus**: same 35 cases. The corpus_fingerprint.json file just
  introduces a hash *of* the corpus; the corpus itself is unchanged.
- **Diagnoser runs**: no re-runs. All diagnosis manifests are the
  same as v1.1.1.

## CI status

All 4 release gates green:

```
✅ validate_committed_diagnosis_provider_errors.py
✅ validate_eval_manifest_consistency.py
✅ validate_diagnosis_vs_context_consistency.py
✅ validate_corpus_fingerprint.py   (NEW in v1.1.2)
✅ validate_protocol_lock.py   (against logdx-ci-v2-partial-2026-05-20)
```

`tools/tests/test_diagnosis_cache_key.py`: 157/157 PASS.

## Acknowledgements

The post-v1.1.1 review surfaced 13 candidate items. v1.1.2 lands the
7 lowest-risk ones (no data changes). 6 deferred items — confidence
intervals, self-call bias measurement, USD-integrated ranking, new
model families, hybrid+LLM-summary router, and independent
reproduction — are tracked in `ROADMAP.md` for v1.2 / v2.
