# CILogBench v1.3 — Limitations

This document is the explicit list of caveats that should be read before
quoting any number from the v1.3 technical report or one-pager. It is
deliberately blunt: every limitation here is a real reason to discount
specific kinds of claims.

## 1. Sample size: 16 cases

The benchmark contains 5 dev + 5 holdout + 6 stress = **16 cases total**.

- All sv1.1 numbers are directional, not statistical.
- A single misclassified case can move a per-method macro by ~0.06 sv1.1.
- "Macro across 3 splits" is a 3-point average; do not infer significance
  from sub-percentage-point margins (e.g. hybrid vs grep at +0.001 under
  Sonnet).

The corpus was sized for a research-prototype calibration loop, not a
public leaderboard. Larger-corpus replication is the most-leveraged
follow-up.

## 2. Calibration via expert-model review (not human review)

The primary score `diagnosis_score_v1_1` was calibrated in E2/E2b against
50 review labels (20 absolute + 30 pairwise) produced by an LLM-as-judge
reviewer (`claude-opus-4-7-expert`). The reviewer was prompted to act as a
domain expert; the labels were validated for blinding (no method names
visible) and stored under `review/batches/e2-real-debugger-v1-holdout-001/`.

But:

- The reviewer is a model, not an unaffiliated human.
- The reviewer is from the same model family (Anthropic Claude) as both
  debuggers being scored. This is a *correlated* expert.
- Spearman = 0.839 between reviewer `overall_usefulness` and sv1.1 is
  encouraging but is a model-on-model correlation, not a model-vs-human
  correlation.

A real human-verified pass on a sample of the E2 batch is the highest-
priority follow-up listed in the technical report. **E9 partially closed
this gap on 2026-05-06 (see Update §2.1 below)**, but the canonical
calibration step — independent human review — has still not been run.

### 2.1. Update (2026-05): cross-model spot-check + AI-assisted human review

Two additional review passes ran on the same 48-item v1.3 hybrid-vs-grep
batch (16 cases × 2 methods × (1 absolute + 1 pairwise)):

**(a) Cross-model expert-style spot-check (ChatGPT, 2026-05-05).** A
second LLM-as-judge from a different model family. Findings:

- Reproduced the E2b finding that sv1.1 fixes sv1's confident-error
  false positives: 0 / 8 of `confident_error` (v1) flags were confirmed
  by the cross-model reviewer; 0 of 0 `confident_error_v1_1` flags
  needed confirmation.
- Rated hybrid and grep diagnoses as effectively tied on overall
  usefulness (means 3.875 vs 3.938 on 0–4 scale; very tight clusters at
  the top of the scale).
- Pairwise judgments leaned toward `grep` (8 wins vs 2 for hybrid out
  of 16 items, with 6 ties).

This remains expert-model review across two model families (Claude Opus
in E2 and ChatGPT in this pass), **not** human review. See
`reports/legacy/e9_cross_model_expert_style_review.md` for the full memo.

**(b) AI-assisted human review (E9, 2026-05-06).** A single human
reviewer (the project author of `hybrid-grep-4k-rtk-err-cat-v1`) worked
from the ChatGPT draft above, inspected each of the 48 items, and
accepted all 48 rows verbatim after item-by-item verification. Findings
match the cross-model pass numerically because the human chose not to
override. Verdict per the E9 plan: **`WEAKEN_HEADLINE`** — the v1.3
technical report's headline phrasing was changed from "matched or beat
grep" to "matched grep on quality at ~⅓ the token cost," with the
8-to-2 pairwise grep lean noted explicitly. See
`reports/legacy/e9_human_verified_v1_3_review.md` for the full memo.

Caveats that **remain unfixed** by this E9 pass:

- **Single reviewer**, who is the project author. Project-bias caveat
  applies even though the reviewer worked from a third-party LLM draft.
- **No genuine inter-rater agreement** is computable from this batch —
  the second labels file (`reviewer_chatgpt_draft.jsonl`) is the source
  the human verified, not an independent review.
- **AI-assisted, not independent.** A reviewer starting from blank
  could produce different scores; this is a documented limitation.
- **Score compression**: 29 of 32 absolute scores were 4, so the
  Spearman of `overall_usefulness` vs `sv1.1` (−0.46) is dominated by
  tie-breaking noise, not a meaningful negative signal.

The strongest possible follow-up remains a fully independent second
human reviewer on the same E9 batch. The batch + the labeling UI
(`review/batches/e9_v1_3_hybrid_vs_grep_human_001/review_ui_human_a.html`)
are ready to copy and re-label.

## 3. Two debugger models only

E1 + E5 used `real-debugger-v1` (Claude Haiku 4.5). E6 added
`real-debugger-v2` (Claude Sonnet 4.6). Both were invoked via the same
shim against the same prompt (`prompts/debugger_v1.md`).

Not tested in v1.3:

- Claude Opus 4.7
- OpenAI GPT-class models
- Open models (Llama / Qwen / DeepSeek)
- A second-prompt control (e.g. `debugger_v2.md`)

The model-stability claim ("hybrid stays #1 across two debuggers") is
narrow: it specifically means *Haiku 4.5* and *Sonnet 4.6* with *one
prompt*. Three-model replication is listed in §15 of the technical report
as future work.

## 4. One real summarizer model and one summary prompt

`llm-summary-v1-haiku` is one model (Haiku 4.5) on one map/reduce prompt
pair (`prompts/llm_summary_v1_map.md` + `..._reduce.md`). The E3 / E4 /
E5 / E6 conclusions about "real summary" are scoped to that pair.

In particular, the technical report does **not** support:

- "LLM summaries are bad in general."
- "Sonnet/Opus summarizers would not change the result."

Both were considered in E4's analysis as Option A ("stronger summarizer")
and explicitly held for future work.

## 5. Small and hand-annotated corpus

Cases were curated by hand from GitHub Actions logs the project's authors
had access to. Each case has a `ground_truth.json` with required signals
(verbatim text snippets), evidence-line spans, must-mention / must-not-
claim phrases, and an expected category.

Risks:

- Annotation bias: cases that were easy to annotate may be over-represented.
- Ecosystem skew: heavy on JavaScript / Python / Rust; lacks Java/Maven,
  Go, C/C++, .NET, Buildkite/CircleCI examples.
- Failure-mode skew: build / test-assertion / permission failures are
  well-represented; long-running flaky / runner-side / heisenbug failures
  less so.

E4 reports `evaluator_possible_undercount` for 1/16 cases and `mixed`
attribution for 1/16, which is consistent with annotation noise of a few
percent.

## 6. Deterministic scoring is a proxy

`diagnosis_score_v1_1` is a calibrated linear composite over per-case
literal-match metrics:

```text
0.25 × category_match_score_v1_1
0.30 × critical_signal_mention_recall
0.20 × must_mention_coverage
0.10 × relevant_file_recall
0.10 × relevant_test_recall
0.05 × valid_evidence_quote_rate
−0.25 × forbidden_claim_violations    (if any)
−0.25 × confident_error_v1_1          (if true)
```

This is a **proxy** for diagnosis usefulness, not a guarantee. Specific
known failure modes:

- Paraphrased correct diagnoses are under-counted by literal-match metrics.
- Over-quoting valid evidence can inflate `valid_evidence_quote_rate`
  without improving usefulness.
- The category compatibility table is hand-built; partial matches that
  aren't on the table score 0.

The E2/E2b calibration explicitly addressed the worst of these, but the
score is still a proxy.

## 7. No MCP / search-agent baseline

v1.3 contains no context method that performs retrieval / multi-step
search over the raw log. Every locked baseline produces a static context
in one shot.

This is a significant qualitative gap — the benchmark cannot speak to
agent-style strategies that *interact* with the log. MCP / search-agent
addition is listed as priority 2 in §15 of the technical report.

## 8. RTK version-specific results

`rtk-read`, `rtk-log`, and `rtk-err-cat` are produced by an external tool
([RTK](https://github.com/rtk-ai/rtk)). RTK output formats can shift
between versions. The protocol records the RTK version and command metadata
used here (in the corresponding baseline entries of
`protocols/legacy/cilogbench-v1.3.lock.json`), but does **not** vendor a binary or
cryptographically pin one. A future RTK release may produce materially
different contexts on the same case.

The technical report does **not** support claims like "RTK is worse than
grep in general" — only that *the version of `rtk-log` / `rtk-err-cat` /
`rtk-read` locked into v1.3* underperformed `grep` on this corpus.

## 9. Hybrid threshold selected from prior analysis

The 4k-token threshold inside `hybrid-grep-4k-rtk-err-cat-v1` was chosen
in E4's offline budget-frontier sweep on the same case set later used to
score the hybrid in E5. This is a deliberate choice (the per-case router
itself is anti-leakage clean), but it does mean E5 / E6 numbers should be
read as **confirming the offline pick**, not as **independent
re-discovery**.

A larger-corpus replication that re-tunes the threshold on a separate
training subset would harden this claim.

## 10. Pricing and cost numbers are informational

Per-token costs for Haiku 4.5 and Sonnet 4.6 change over time. The cost
tables in the technical report and per-experiment reports are derived
from token counts and the API's `total_cost_usd` field at run time, not
from a fixed price list. Treat dollar / token numbers as **point-in-time
informational**, not benchmark-grade.

## 11. Provider-error events are real and recorded

A small number of `provider_error` rows appear across the run history:

- E1/E3: 2-3 cases on `cargo-tokio-001` raw/rtk-read (context-too-large
  on Haiku).
- E3: 2 cases on `pytest-sklearn-stress-*` (reduce-stage `claude` CLI
  exit 1 with empty stderr).
- E6: 9 cases at protocol-run end (likely Sonnet rate-window pattern,
  recovered cleanly on sequential retry).

These were recorded as explicit `provider_error` rows and surfaced in the
relevant per-experiment reports. They were *not* silently re-routed to a
different method — that would have leaked information.

## 12. The benchmark is not a leaderboard

CILogBench v1.3 is one corpus, two debuggers, one calibration source. It
should not be quoted as "the answer" for CI debugging context strategy in
any agent. It is a **starting point** for honest comparison, with the
above limitations all on the table.
