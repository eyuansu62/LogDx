# Plan — cost-integrated ranking + agent dynamic mode benchmark

**Status**: draft plan, not committed
**Related review items**:
- #7-A (friend's question #2: does ranking factor in summarizer
  token cost?)
- #7-B (friend's question #3: how do we ensure agent uses only one
  RTK mode per session — production-realistic dynamic-mode benchmark)
**Estimated work**: 8–16 hours engineer time + ~$30 API spend
**Estimated calendar time**: 2–3 days

## Why

Two open critiques from the v1.1 reviewer:

### 7-A. Cost-integrated ranking

Today's headline ranking is pure quality (`diagnosis_score_v1_1`).
Cost shows up in a separate column and a Pareto plot. The reviewer's
point was: if you're going to RECOMMEND a method, the
recommendation has to weight cost, or you're implicitly saying
"quality at any cost" which isn't realistic.

The hybrid leaders win at ~$0.03/case. `llm-summary-v1-gpt-5-mini`
beats them in agent-loop but costs 6× more ($0.18/case). Whether
that's worth it depends on a $/quality conversion the leaderboard
doesn't currently make explicit.

### 7-B. Agent dynamic-mode benchmark

The v1.1.1 / v1.2 leaderboard scores each `(case, context_method,
diagnoser)` triple as an independent run — the diagnoser only ever
sees one context method's output per case. Real production
agents would dynamically select method per case (e.g., "this log
is small, use raw; this one is huge, use grep; this one has
structured failures, use rtk-err-cat"). The current benchmark
can't compare against that workflow.

## What

### 7-A. New leaderboard column: "cost-quality composite score"

Define `combined_score_v1` = `diagnosis_score_v1_1 - λ × log10(usd_per_case)`
with `λ` calibrated so that:
- The top 2 hybrids stay at the top (their $0.03/case + 0.67 score
  produces a high composite)
- `llm-summary-v1-gpt-5-mini` at $0.18 / 0.664 lands roughly
  comparable to the top hybrids (it's clearly worth 6× the cost
  for a +0 quality gain only if the agent-loop boost matters)
- `raw` at $0.39 / 0.35 is clearly dominated
- `rtk-log` at $0.004 / 0.25 is clearly dominated (cheap doesn't
  rescue bad)

`λ` calibration: pick the value where the rank order matches our
intuitive "should be the recommendation" judgments. Then publish
both axes plus the composite.

Alternative: weighted-Pareto-rank — compute Pareto rank under
several λ values (e.g. λ=0, 0.05, 0.1, 0.2) and publish a "robust
top-3" defined as methods that are in the top-3 under at least 3 of
4 weights. Anchors the recommendation to a span of cost-sensitivities,
not a single arbitrary λ choice.

### Implementation (7-A)

1. **Tool**: extend `tools/compute_usd_costs.py` to also emit a
   `combined_score_v1` column per method.
2. **Leaderboard**: add the column to the headline table. Choose
   either: (a) a single λ shown explicitly in the column header, or
   (b) a robust top-3 across a sweep of λ values.
3. **Analysis doc**: `docs/analysis/cost-quality-tradeoff.md` —
   present the λ sensitivity curve, show how each method's rank
   shifts as λ ranges from 0 (pure quality) to 2 (cost-dominated).
4. **Test**: `tools/tests/test_combined_score.py` — fixture-based,
   verify the formula is stable.

### 7-B. Agent dynamic-mode benchmark

The reviewer's specific question was: "how would a real production
agent — which can dynamically pick method per case — compare?"

Two ways to answer this:

#### Option 7-B-Cheap: routed-pseudo-agent

Use the existing per-case manifests + a simple oracle router:

```python
def route(case_id, available_contexts):
    # For each case, pick whichever (single-shot) method scores
    # highest on its OWN diagnosis-score-v1_1 PRE-COMPUTED.
    return max(available_contexts, key=lambda m: pre_computed_score[case_id, m])
```

This gives an **upper bound on dynamic-mode performance** — assuming
the router has perfect oracle knowledge of which method will work
best on each case. It's not a realistic agent, but it tells us
"if the agent could perfectly route, what's the ceiling?"

Cost: zero — no new LLM calls. ~30 min engineer time.

#### Option 7-B-Real: real router agent

Build a new diagnoser `real-router-v1` that:

1. Receives all 10 context-method outputs (raw, tail-200, grep,
   rtk-*, llm-summary-*, hybrids) for a single case.
2. Routes via Sonnet: "Given these 10 candidate contexts, pick the
   1 most likely to support a correct diagnosis. Output: { chosen:
   method_name, reason: string }".
3. Then passes the chosen context to the diagnoser (Sonnet via the
   existing `real-debugger-v2` shim) and gets the diagnosis.

This measures **realistic dynamic routing**. The two-stage
architecture (router + diagnoser) reflects how production agents
actually work.

Cost: ~$5–8 (35 cases × Sonnet router-call + diagnosis-call).
Engineer time: ~4 hours.

#### Recommended sequencing

1. Land 7-B-Cheap first (the oracle ceiling) — it's a free upper
   bound, motivates whether 7-B-Real is worth doing.
2. If the oracle ceiling is ~0.05+ above the current best static
   method, build 7-B-Real and see how close it gets to the ceiling.
3. If the oracle ceiling is < 0.02 above the current best static
   method, the static-method choice is robust enough that dynamic
   routing wouldn't help much — defer 7-B-Real.

### Acceptance criteria

- [ ] `combined_score_v1` column on the headline leaderboard
- [ ] Oracle-router ceiling computed and reported as a leaderboard
      reference line ("dynamic routing ceiling")
- [ ] If 7-B-Real lands: `real-router-v1` diagnoser, its own
      method × diagnoser cell in the leaderboard
- [ ] Cross-family check: does the recommended-best static method
      stay the same under cost-integrated ranking AND under oracle
      routing? If yes, the v1.0 / v1.1 recommendation is even more
      robust than the existing leaderboard claims.
- [ ] `RELEASE_NOTES_v1_3.md` documents the cost-ranking + dynamic-
      agent additions

## Open questions for user

1. **λ choice**: do you want a single λ (simpler, more arbitrary)
   or a robust top-3 across a sweep (less arbitrary, more complex
   to communicate)?
2. **7-B order**: ship 7-B-Cheap (oracle) first, then decide on
   7-B-Real? Or build both in parallel?
3. **7-B router model**: Sonnet 4.6 mirrors `real-debugger-v2`.
   Alternative: Haiku 4.5 for the router (cheaper, tests "can a
   weaker model route correctly given a strong downstream diagnoser?").
4. **Cost-ranking integration**: does this replace the existing
   "Overall" column or add alongside it? Replacing is a clean
   "leaderboard now considers cost"; adding alongside preserves
   v1.0-style purity for backward citations.

## Out of scope for this plan

- Latency-integrated ranking (separate plan; latency depends on
  provider load, harder to pin to a snapshot)
- Real-time cost adjustment (e.g. detect that gpt-5-mini just got
  cheaper and re-rank automatically)
- Real Claude Code / Codex integration (the dynamic-router we'd
  build is an experimental approximation, not a production
  integration)
