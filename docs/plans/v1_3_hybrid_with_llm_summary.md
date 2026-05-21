# Plan — hybrid + LLM-summary fallback router

**Status**: draft plan, not committed
**Related review item**: #12 (current hybrids don't include
LLM-summary as a fallback; obvious next step)
**Estimated work**: 2–4 hours engineer time + ~$5–10 API spend
**Estimated calendar time**: 1 day

## Why

The current hybrid routers (`hybrid-grep-120k-rtk-tail`,
`hybrid-grep-120k-tail`, `hybrid-grep-4k-rtk-err-cat`) all route
between deterministic context methods only:

| Threshold | Primary | Fallback |
|---|---|---|
| 120k tokens | grep | tail-200 |
| 120k tokens | grep | rtk-err-cat (if rtk-input-not-truncated) else tail-200 |
| 4k tokens | grep | rtk-err-cat |

The LLM-summary methods (haiku + gpt-5-mini) hit different parts of
the cost-quality frontier than the deterministic methods. They're
expensive but produce a near-perfect summary on most cases. The
obvious next step is a hybrid that routes:

- Small logs (< some threshold) → `grep` (cheap, exact, fast)
- Medium logs → `grep` if it fits the token budget
- Huge logs → `llm-summary-v1-gpt-5-mini` (expensive but high quality)

This puts LLM-summary in the position where it's most cost-effective
(only when cheaper methods can't fit) and lets the cheap methods
handle everything else.

## What

### Variant 1: `hybrid-grep-120k-llm-summary-v1` (recommended)

```text
For each case:
    grep_tokens = estimate_tokens(grep_output)
    if grep_tokens <= 120_000:
        select grep
    elif llm_summary_gpt5mini is available:
        select llm-summary-v1-gpt-5-mini   # large-log fallback
    elif tail_200 is available:
        select tail-200                    # belt-and-suspenders
    else:
        record provider_error              # do not silently fall back to raw
```

This mirrors the v3 hybrid's structure (primary + fallback +
ultimate fallback) but uses LLM-summary as the middle tier instead
of rtk-err-cat.

### Variant 2: `hybrid-llm-summary-primary-v1`

```text
For each case:
    select llm-summary-v1-gpt-5-mini
    if grep fits in 4k tokens:
        # also send grep alongside summary for evidence verification
        select hybrid(grep_4k + summary)
```

This treats LLM-summary as primary on every case, with grep
augmentation for small logs. More expensive but tests the
"summary is always better than nothing" hypothesis.

### Variant 3: `hybrid-grep-summary-router-v1` (most aggressive)

```text
For each case:
    if grep_fits_4k:
        select grep
    elif log_byte_size > 1_000_000 and gpt5mini-summary available:
        select gpt5mini-summary
    elif grep_fits_120k:
        select grep
    else:
        select tail-200
```

Three-tier router with explicit size cutoffs at both 4k and 1MB.

## Implementation

### Phase A — config + runner (~1 hour)

1. **New config**: `configs/baselines/hybrid-grep-120k-llm-summary-v1.json`
   - Same shape as existing hybrid configs
   - `router_logic` field describes the if/elif chain above
   - `dependencies` field lists `grep`, `llm-summary-v1-gpt-5-mini`,
     `tail-200`
2. **Runner**: existing `tools/run_hybrid_router_baseline.py` handles
   per-case routing. Need to extend it to accept LLM-summary
   manifests as dependencies (currently only accepts deterministic
   `*.jsonl` files). 1 file, ~20-30 LOC.

### Phase B — backfill (~5 min compute, $0 if cache-hit)

The hybrid runner doesn't call any LLM — it picks per-case from
existing manifests. Since both `grep` and `llm-summary-v1-gpt-5-mini`
already have manifests for all 35 cases, the hybrid manifest is
generated deterministically from those existing artifacts.

Total cost: $0 (no new LLM calls). The hybrid manifest writes the
chosen-per-case context-method into the row's metadata, and the
existing diagnoser runs on the chosen context.

### Phase C — diagnosis (~$15 if all 4 diagnosers)

Run the 4 existing diagnosers on the new hybrid's contexts (35
cases × 4 diagnosers = 140 calls). Mostly free via Claude OAuth;
~$3 for v3 and ~$5–10 for agent_v1.

### Phase D — evaluation + leaderboard

1. Eval as usual — `tools/evaluate_diagnosis.py`.
2. Add the new hybrid to the headline + agent-loop tables.
3. Analysis: does the new hybrid Pareto-dominate the v3 hybrid
   (`hybrid-grep-120k-rtk-tail`)? Hypothesis: yes on agent-loop
   (because LLM-summary as the large-log fallback uses 0.37
   tools/case vs rtk-err-cat's 1.66), maybe yes on single-shot.

## Expected outcome

Best-case scenario (the hybrid Pareto-dominates):
- Single-shot: ~0.67-0.68 (matches or slightly beats current top-2)
- Agent-loop: ~0.75-0.76 (beats current best of 0.749)
- Cost: $0.03-$0.08/case (cheaper than pure LLM-summary because
  most cases route to grep)

Worst-case scenario (the hybrid is dominated by simpler methods):
- The 120k-token threshold rarely fires (most logs fit in grep at
  4k tokens — see the v3 hybrid's route stats). So the LLM-summary
  fallback rarely kicks in, and the hybrid behaves ≈ identical to
  the v3 hybrid.
- This would mean LLM-summary's win was concentrated on huge logs
  (which the existing hybrid already handles via rtk-err-cat or
  tail-200), so routing it as a fallback doesn't change much.

Either outcome is informative.

## Acceptance criteria

- [ ] `configs/baselines/hybrid-grep-120k-llm-summary-v1.json`
      committed
- [ ] `results/<split>/hybrid-grep-120k-llm-summary-v1.jsonl` for
      all 6 splits, total 35 cases
- [ ] `routes.jsonl` companion file logging per-case routing
      decisions (so we can audit "how often did the fallback fire?")
- [ ] All 4 diagnosers run on the new hybrid's contexts
- [ ] Leaderboard updated with the new hybrid's row
- [ ] All 4 release gates + 157 tests pass
- [ ] `RELEASE_NOTES_v1_3.md` (or appropriate version) documents
      the new hybrid + the routing-decision distribution

## Open questions for user

1. **Which variant?** I recommend Variant 1 (`hybrid-grep-120k-llm-
   summary-v1`) as the obvious next step — minimal scope change vs
   the existing v3 hybrid. Variant 2 / 3 are interesting but riskier
   on cost and we'd need to argue the case for them.
2. **gpt-5-mini-summary or haiku-summary as the fallback?** v1.2
   showed gpt-5-mini-summary scores higher AND costs 10× less, so
   gpt-5-mini is the clear pick for a fallback. Documenting this in
   the plan so we don't re-litigate it.
3. **Should the hybrid also include `llm-summary-v1-haiku` as a
   second-tier fallback?** Could route: grep → gpt5mini-summary
   (if grep too big) → haiku-summary (if gpt5mini-summary also too
   big or refused). Probably overkill; one fallback tier is
   usually enough.

## Out of scope for this plan

- A "router agent" that picks methods dynamically per case via an
  LLM (that's covered in
  [`v1_3_cost_ranking_and_dynamic_agent.md`](v1_3_cost_ranking_and_dynamic_agent.md)
  as the 7-B agent)
- A hybrid that combines outputs of multiple methods into a single
  augmented context (e.g. `grep_top_50 + llm_summary` concatenated)
  — different design space, separate plan
