# LogDx-CI Reports

Technical reports and per-experiment writeups. Top-level files here are
the ones cited from public docs (homepage, leaderboard, CITATION,
release notes). Historical experiment artifacts have been moved to
[`legacy/`](legacy/) for provenance.

## Headline report

- [`e10_v2_generalization_partial.md`](e10_v2_generalization_partial.md)
  — **the technical report**. Headline finding, methodology, full
  per-method per-debugger breakdown, caveats. This is what to cite.

## Calibration & score methodology

- [`experiments/e2_calibration_memo.md`](experiments/e2_calibration_memo.md) — How
  `diagnosis_score_v1_1` was calibrated (weight selection, validation).
- [`experiments/e2b_score_calibration_v1_1.md`](experiments/e2b_score_calibration_v1_1.md) —
  v1.1 score-formula calibration update.

## Per-experiment writeups (v1.2-load-bearing)

- [`experiments/e3_real_llm_summary_cilogbench_v1_2_haiku.md`](experiments/e3_real_llm_summary_cilogbench_v1_2_haiku.md)
  — Real Anthropic Haiku map-reduce summarizer (the `llm-summary-v1-haiku`
  baseline).
- [`experiments/e4_summary_failure_attribution_cilogbench_v1_2.md`](experiments/e4_summary_failure_attribution_cilogbench_v1_2.md)
  — Where the LLM-summary baseline loses points + failure-mode analysis.
- [`experiments/e5_hybrid_grep_fallback_cilogbench_v1_2.md`](experiments/e5_hybrid_grep_fallback_cilogbench_v1_2.md)
  — Hybrid router design (the 4k-threshold prototype, replaced by 120k
  in v1.2).
- [`experiments/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md`](experiments/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md)
  — Cross-debugger generalization (Sonnet 4.6 second debugger).
- [`experiments/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`](experiments/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md)
  — MCP search-agent variant (precursor to `real-agent-v1`).
- [`experiments/e8_hybrid_first_search_fallback_cilogbench_v1_3.md`](experiments/e8_hybrid_first_search_fallback_cilogbench_v1_3.md)
  — Hybrid-then-search fallback routing variant.
- [`experiments/e9_cross_model_expert_style_review.md`](experiments/e9_cross_model_expert_style_review.md)
  — Cross-model expert-style review pass.
- [`experiments/e9_human_verified_v1_3_review.md`](experiments/e9_human_verified_v1_3_review.md)
  — Human-verified review of v1.3 prototype subset.

## Corpus / split analysis

- [`experiments/split_balance.md`](experiments/split_balance.md) — Per-split balance check
  (failure-category and ecosystem distribution).
- [`experiments/v2_split_balance.md`](experiments/v2_split_balance.md) — v2 corpus split balance.
- [`experiments/cilogbench_v1_3_freeze_memo.md`](experiments/cilogbench_v1_3_freeze_memo.md) —
  v1.3 prototype-corpus freeze memo (predates the v1.0 rebrand from
  "CILogBench" to "LogDx-CI").

## Historical artifacts

[`legacy/`](legacy/) holds 35+ per-experiment iteration writeups from
the v1.1 / v1.3 prototype phases (per-split diagnosis evals, signal
recall analyses, contamination checks, mock-debugger writeups,
predecessor-of-e10 phase-3 writeups). Kept for provenance and
historical reproducibility; not required for understanding the v1.2
release. The published v1.2 numbers can be reproduced end-to-end
without them (see [`../RELEASE_NOTES_v1_2.md`](../RELEASE_NOTES_v1_2.md)).
