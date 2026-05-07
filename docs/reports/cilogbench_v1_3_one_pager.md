# CILogBench v1.3 — one-pager

> **Disclosure:** sv1.1 was originally calibrated by an LLM-as-judge
> reviewer (E2/E2b: `claude-opus-4-7-expert`) and later spot-checked by
> AI-assisted human review (E9: 1 reviewer, project author of the hybrid
> baseline, verified all 48 items of a ChatGPT-generated draft). This is
> *not* independent human review. Results are directional, not statistical.
> See [`cilogbench_v1_3_technical_report.md`](cilogbench_v1_3_technical_report.md)
> §8b and `reports/e9_human_verified_v1_3_review.md` for details.

> 🚨 **v2 generalization caveat (added 2026-05-07, refreshed at the
> 12-case v2-checkpoint-12 state):**
> The hybrid-vs-grep "matched on quality at ~⅓ token cost" headline below
> **does not generalize on the v2 corpus.** Across the 12 v2 cases
> (`v2/dev` 3 + `v2/holdout` 5 + `v2/stress` 4), hybrid sv1.1 falls:
>
> - Sonnet 4.6: 0.7713 → 0.4353, Δ **−0.34** (rank #1 → **#4**)
> - Haiku 4.5: 0.7150 → 0.4302, Δ **−0.28** (rank #1 → **#4**)
>
> The cost match holds (~95% reduction); the quality match does not.
> Root cause: the 4k-token threshold inside the hybrid was tuned on the
> same v1.3 corpus that scored it (see
> [`cilogbench_v1_3_limitations.md`](cilogbench_v1_3_limitations.md) §9).
>
> The 12-case refresh surfaced two further findings:
>
> 1. **Method-level (robust):** the two new v2/stress cases reveal a
>    previously-unseen grep blindspot. When the regex
>    `error|failed|...|##[error]` matches *too widely* — rust's
>    31k-line log produces 161k tokens of grep context, nodejs's
>    10k-line log produces 359k tokens — Sonnet/Haiku abstain on the
>    inflated context (sv1.1 = 0.0). Hybrid's 4k-token threshold
>    correctly avoids grep's blowup but inherits rtk-err-cat's
>    collapse on the same density-driven blindspots (rtk-err-cat
>    also produces ~320k tokens on nodejs).
> 2. **Macro-level (caveated):** at the 12-case macro, tail unseats
>    grep as v2 #1 (Sonnet 0.68 vs 0.59; Haiku 0.63 vs 0.49). But
>    that gap is partly a v2/stress sampling artifact: the bucket
>    is currently **4/4 late** and tail's bounded 200-line window is
>    structurally advantaged by late signals. On the non-stress
>    portion (v2/dev + v2/holdout, 8 cases, mixed signal_position)
>    tail and grep are tied within 0.03. The "tail unseats grep"
>    finding should be re-checked when v2/stress acquires a
>    middle/scattered/early case (see
>    [`reports/v2_split_balance.md`](../../reports/v2_split_balance.md)
>    §3 for the sampling decomposition).
>
> Earlier 8-case framing read "rank #1 → #6" and 10-case read "rank
> #1 → #3-4"; the 12-case refresh stabilizes hybrid at **rank #4
> unanimous**.
>
> The robust core finding is unchanged across all three refreshes:
> hybrid loses ≥0.25 sv1.1 cross-debugger, falls out of the top tier,
> and the v1.3 "hybrid stays #1 across two debuggers" model-stability
> claim does not survive distribution shift. The "grep is the v2
> winner" sub-claim is now superseded by the 12-case state.
>
> Full v2 results: [`reports/e10_v2_generalization_partial.md`](../../reports/e10_v2_generalization_partial.md)
> (canonical narrative with 8-case → 10-case → 12-case refreshes in
> §3, §3b, §3c). All v1.3 numbers below are still correct *on v1.3*;
> this caveat qualifies their generalization, not their v1.3 validity.

## Problem

After a CI failure log is compressed, summarized, filtered, or searched,
**does a coding agent still have enough evidence to identify the true root
cause?** Aggressive token compression often deletes the actual error;
LLM summaries can be concise but costly and lossy.

## Benchmark

CILogBench is **not** a CI-log compressor. It is a benchmark that runs:

```text
raw CI log
  → context method        (one of 8 locked baselines)
  → fixed debugger        (a real LLM, held fixed)
  → diagnosis JSON
  → deterministic evaluator + per-case scoring
```

The current frozen protocol is `cilogbench-v1.3` — 16 hand-curated cases
(dev 5 + holdout 5 + stress 6), 8 locked context-provider baselines, primary
score `diagnosis_score_v1_1` (calibrated against an expert-model reviewer in
E2b).

## Methods

| Method | Type |
|---|---|
| `raw` | full log |
| `tail-200` | last 200 lines |
| `grep` | regex over `error|failed|...|##[error]` ±3/8 lines |
| `rtk-read` / `rtk-log` / `rtk-err-cat` | three RTK context modes |
| `llm-summary-v1-mock` | infrastructure/control baseline — deterministic mock of the v1 summarizer pipeline; **not** a real LLM-summary result |
| `hybrid-grep-4k-rtk-err-cat-v1` | router: `grep` if it fits 4k tokens, else `rtk-err-cat` |

`llm-summary-v1-haiku` (real Haiku-summarized context) was tested but
**deliberately excluded from the v1.3 baseline lock** because its
quality-cost trade-off was uncompetitive at standard budgets (E3, E4).

## Headline result

A simple deterministic hybrid strategy **matched grep on diagnosis quality
at roughly one third of `grep`'s tokens** on this 16-case corpus, and
**ranked #1 by automatic sv1.1 under both tested debuggers**:

| Debugger | hybrid sv1.1 | grep sv1.1 | hybrid total tok | grep total tok |
|---|---:|---:|---:|---:|
| Haiku 4.5 (E5) | **0.715** | 0.675 | 4.9k | 15.7k |
| Sonnet 4.6 (E6) | **0.771** | 0.770 | 5.0k | 15.9k |

Top-3 method ranks under sv1.1 were identical across debuggers
(`hybrid > grep > tail`). AI-assisted human review (E9) preferred grep
8-to-2 in head-to-head pairs (with 6 ties) while rating both methods
inside a tie band on absolute usefulness (means 3.875 vs 3.938 on 0–4).
The cost gap is unchanged.

## What surprised us

- **The simplest filter wins among single-method baselines.** A trivial
  regex (`grep`) outperforms three RTK modes and a real LLM summary on
  diagnosis quality.
- **An offline budget-frontier analysis predicted the real run almost
  exactly.** E4 predicted hybrid macro sv1.1 = 0.723; E5 measured 0.715
  (Δ = −0.008).
- **A stronger debugger narrows the *quality* gap but not the *cost* gap.**
  Sonnet closed hybrid's quality lead over grep to ~0pp, but the 3× cost
  ratio held.
- **Real LLM summary was *stable* but not *competitive*.** It had the
  second-smallest cross-split sv1.1 gap of any method (0.121) and 0%
  confident-error rate, but cost ~6× more total pipeline tokens than `grep`
  while scoring lower.
- **Human pairwise can disagree with sv1.1 even inside a tie band.** E9's
  AI-assisted human review preferred grep 8-to-2 in forced-choice pairs
  while rating both methods ≈ tied on absolute usefulness — hybrid's
  compactness sometimes loses specific quotable details (test names,
  file:line) that the reader values.

## Limitations

- 16 cases. Treat results as directional.
- sv1.1 calibrated by expert-model review (E2/E2b) + spot-checked by
  AI-assisted human review (E9, 1 reviewer = project author). Not
  independent human review and not inter-rater-validated.
- Two debugger models, one summarizer, one summary prompt.
- One MCP / search-agent baseline exists (E7) but lost on quality + cost;
  no search-fallback policy beat hybrid (E8). Search-agent track paused.
- RTK output is version-specific; the protocol records the version used.

## Next work

In priority order:

1. **A second independent human reviewer on the E9 batch** — only way to
   compute real inter-rater agreement and lift the project-bias caveat
   on the current single-reviewer pass.
2. **Larger corpus across more ecosystems** — biggest constraint on every
   claim. Would also widen score variance and let human-vs-sv1.1
   correlation be computed cleanly.
3. Third debugger model (Opus 4.7, GPT-class, open-weights).
4. Additional hybrid variants on a larger corpus.
5. Search-agent track is paused (E7 KEEP_AS_EXPLORATORY, E8
   STOP_SEARCH_TRACK); revisit only with a different agent prompt or
   model family.

## Where to read more

- Full technical report: `docs/reports/cilogbench_v1_3_technical_report.md`
- Limitations: `docs/reports/cilogbench_v1_3_limitations.md`
- Frozen protocol: `protocols/cilogbench-v1.3.lock.json`
- Per-experiment reports: `reports/e{2b,3,4,5}_*`,
  `reports/e6_second_debugger_cilogbench_v1_3_real-debugger-v2.md`,
  `reports/e7_mcp_search_agent_cilogbench_v1_3_mcp-search-agent-v1-sonnet.md`,
  `reports/e8_hybrid_first_search_fallback_cilogbench_v1_3.md`,
  `reports/e9_human_verified_v1_3_review.md`
