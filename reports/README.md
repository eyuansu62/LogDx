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

- [`e2_calibration_memo.md`](e2_calibration_memo.md) — How
  `diagnosis_score_v1_1` was calibrated (weight selection, validation).
- [`e2b_score_calibration_v1_1.md`](e2b_score_calibration_v1_1.md) —
  v1.1 score-formula calibration update.

## Per-experiment writeups (v1.2-load-bearing)

- [`e3_real_llm_summary_cilogbench_v1_2_haiku.md`](e3_real_llm_summary_cilogbench_v1_2_haiku.md)
  — Real Anthropic Haiku map-reduce summarizer (the `llm-summary-v1-haiku`
  baseline).
- [`e4_summary_failure_attribution_cilogbench_v1_2.md`](e4_summary_failure_attribution_cilogbench_v1_2.md)
  — Where the LLM-summary baseline loses points + failure-mode analysis.
- [`e5_hybrid_grep_fallback_cilogbench_v1_2.md`](e5_hybrid_grep_fallback_cilogbench_v1_2.md)
  — Hybrid router design (the 4k-threshold prototype, replaced by 120k
  in v1.2).
- [`e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md`](e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md)
  — Cross-debugger generalization (Sonnet 4.6 second debugger).
- [`e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`](e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md)
  — MCP search-agent variant (precursor to `real-agent-v1`).
- [`e8_hybrid_first_search_fallback_cilogbench_v1_3.md`](e8_hybrid_first_search_fallback_cilogbench_v1_3.md)
  — Hybrid-then-search fallback routing variant.
- [`e9_cross_model_expert_style_review.md`](e9_cross_model_expert_style_review.md)
  — Cross-model expert-style review pass.
- [`e9_human_verified_v1_3_review.md`](e9_human_verified_v1_3_review.md)
  — Human-verified review of v1.3 prototype subset.

## Corpus / split analysis

- [`split_balance.md`](split_balance.md) — Per-split balance check
  (failure-category and ecosystem distribution).
- [`v2_split_balance.md`](v2_split_balance.md) — v2 corpus split balance.
- [`dev_privacy_audit.md`](dev_privacy_audit.md) — Per-case privacy-audit
  summary for the `dev` split.
- [`cilogbench_v1_3_freeze_memo.md`](cilogbench_v1_3_freeze_memo.md) —
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
