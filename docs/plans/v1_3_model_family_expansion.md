# Plan — v1.3 model-family expansion

**Status**: draft plan, not committed
**Related review item**: #6 (3-family cross-check is really only 2-vendor)
**Estimated work**: 4–8 hours engineer time + ~$30-80 API spend
**Estimated calendar time**: 1–2 days (mostly waiting on parallel runs)

## Why

The v1.2 leaderboard advertises "3 model families" but is really only
**2 vendors** — Anthropic (Haiku 4.5 + Sonnet 4.6) and OpenAI
(gpt-5-mini). Adding Gemini / Llama / Mistral / DeepSeek would actually
let us argue cross-family generalization. Reviewer #2 is going to ask
about this; reviewer #1 probably already did.

Also: the v1.2 self-call-bias falsification is currently based on 1
cross-pair (Anthropic-summary → OpenAI-debugger and vice versa).
Adding a 3rd vendor with its own summarizer + debugger gives a real
3×3 cross-pair matrix and lets us claim "summary quality is
vendor-independent" with confidence.

## What

Add **1 new debugger family** (priority order, pick at least one):

1. **`real-debugger-v4` (Google Gemini)** — best cross-family signal
   because Gemini is a different architecture (different tokenizer,
   different RLHF, different scratchpad). Gemini 2.5 Pro or 2.5 Flash
   are the candidates.
2. **`real-debugger-v5` (Meta Llama)** — open-source comparison;
   Llama 4.x via Bedrock or Together. Different RLHF, no proprietary
   safety training.
3. **`real-debugger-v6` (DeepSeek)** — Chinese-vendor, reasoning model.
   Cheapest of the lot per token.

And **1 new summarizer family** (parallel to debugger choice):

- If we add Gemini debugger → also add `llm-summary-v1-gemini`
- This makes the cross-pair matrix 3×3 (Anthropic, OpenAI, Google)

## Specific plan if we pick **Gemini** first

### Phase A — shims (no API spend, ~2 hrs)

- `examples/diagnosis_shim_gemini.py` — model on
  `examples/diagnosis_shim_openai.py` but using
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent`.
  Reuse the same FORBIDDEN_KEYS guard, secret-redaction helpers,
  and the JSON parse retry from the v1.2 OpenAI shim.
- `examples/summary_shim_gemini.py` — mirror of
  `summary_shim_openai.py` for the map-reduce calls.
- `configs/diagnosers/real-debugger-v4.json` — model config with
  pinned snapshot, max output tokens, no temperature for reasoning
  models, expected_resolved_model.
- `configs/pricing/snapshot_2026_05_20.json` — add Gemini pricing
  (`gemini-2.5-pro` is ~$1.25/MTok input / $10/MTok output as of
  this writing — verify before pinning).

### Phase B — smoke test on dev (~$0.50)

- Run gemini-summary reducer on `dev` (5 cases). Expect ~$0.10.
- Run all 4 existing diagnosers + the new gemini diagnoser on the
  10 LLM-summary contexts × 5 cases (5 methods × 5 diagnosers × 5
  cases = 125 calls). Expect ~$0.40.
- Verify the new gemini diagnoser produces valid JSON consistently
  (gpt-5-mini's reasoning-model JSON instability is a real risk; if
  gemini-2.5-pro has the same issue, add the retry loop preemptively).

### Phase C — full corpus (~$15–40)

- Reducer: gemini-summary on all 35 cases, all 6 splits. Expected
  ~$3–10.
- Diagnoser: new gemini debugger on all 35 cases × all existing
  context methods (raw, tail-200, grep, rtk-*, hybrids, the 3
  llm-summary variants). Expected ~$15–30.
- Existing 4 diagnosers on `llm-summary-v1-gemini` contexts (140
  more diagnosis calls). Cached for Haiku/Sonnet via OAuth; ~$3–5
  for v3 (OpenAI) and ~$5–8 for agent_v1.

### Phase D — leaderboard + analysis

- Add "Gemini 2.5 Pro" column to the headline table (4 columns now:
  Haiku, Sonnet, gpt-5-mini, Gemini). Re-rank by 4-family overall mean.
- Add `llm-summary-v1-gemini` as a new context-method row.
- Update the "v1.2 cross-family LLM-summary" section to extend to a
  3×3 cross-pair matrix.
- New analysis doc: `docs/analysis/cross-vendor-generalization.md` —
  is the v1.0/v1.1 finding ("hybrids win across families") robust to
  a 3rd vendor? Or does it crack?

## Acceptance criteria

- [ ] All 4 release gates pass with new manifests
- [ ] All 157 cache-key tests pass
- [ ] No new provider_error rows (or all categorized as transient
      with retry; reasoning-model JSON instability handled like
      v1.2 fixed it for gpt-5-mini)
- [ ] Leaderboard description updated from "3 model families
      (Haiku, Sonnet, gpt-5-mini)" to "4 model families across 3
      vendors"
- [ ] `protocols/logdx-ci-v1.3.lock.json` frozen
- [ ] `RELEASE_NOTES_v1_3.md` documents the cross-vendor result

## Open questions for user

1. **Which third vendor?** Gemini is cleanest cross-family signal (3rd
   completely different architecture). Llama is the open-source story
   (anyone can re-host). DeepSeek is cheapest. Pick one.
2. **Which Gemini model?** 2.5 Pro is more capable (~$1.25/$10);
   2.5 Flash is cheaper (~$0.30/$2.50) and faster but maybe weaker
   on reasoning. v1.2 used the smaller `gpt-5-mini` so 2.5 Flash is
   the apples-to-apples choice; 2.5 Pro is the apples-to-Sonnet
   choice.
3. **Should the summarizer match the debugger?** If we add Gemini
   debugger, we get a "free" Gemini summarizer by following the
   v1.2 pattern. Or we could add ONLY a debugger first (lower cost,
   tests "does the leaderboard rank stay the same when seen through
   a Gemini lens") and defer the cross-summary check to v1.4.

## Out of scope for this plan

- Llama 4.x via Together / Replicate (separate plan if user wants
  open-source story)
- DeepSeek R1 / V3 (separate plan; geo / data-residency concerns)
- USD pricing snapshot maintenance (already automated by
  `tools/compute_usd_costs.py`)
