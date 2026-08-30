# Proposed upstream text

## Recommendation

**PR. Do not open it automatically.**

Local packaging is authorized. Publication is not: do not push, create an
issue, or open a PR until the user explicitly approves that action.

## Proposed PR title

Add a model-pinned Copilot diagnoser and deterministic Drain3 baseline

## Proposed PR body

### Summary

This change adds zero-tool GitHub Copilot CLI and SDK diagnosis backends and
one corpus-wide Drain3 `0.9.11` context provider. It keeps all new results
separate from frozen v1.2 artifacts.

The compatibility study ran Luna, Terra, and Sol over the frozen 35 cases and
eight context methods. Each model produced 280 rows. Every one of the 253
successful calls per model recorded the requested model as the resolved model.
The remaining 27 rows per model are explicit unsupported-context results.

### Findings

- Aggregate reducer ranks remained similar to the averaged frozen
  real-debugger-v1/v2/v3 panel under compatibility limits. Spearman rho was
  1.0000 for Luna, 0.9286 for Terra, and 0.9643 for Sol. On the 17 cases accepted
  by both raw modes, exploratory correlations fell to 0.5714, 0.4643, and
  0.3214. Capacity failures and case selection affect the full-corpus ordering.
- Hybrid RTK-tail v3 had the highest mean score on each model. Pairwise
  intervals among the stronger reducers often overlap zero, so this PR does not
  declare a new winner.
- Compatibility raw context scored 0.3513 on average and had a 51.43% error
  rate. Reduction remains necessary on this transport.
- The pinned Drain3 template-only configuration preserved 0.8750 of required
  signals and 0.8632 of critical signals
  at 0.5338 byte reduction. It missed 22 critical signals. Its downstream mean
  score was 0.5903. It did not create a new point on the pooled recorded
  downstream score/cost frontier. This is not a general result about Drain3,
  nor proof of statistically worse diagnosis quality than hybrid.
- GPT-5 Mini was excluded because resolved identity could not be proved.
- Native raw accepted 31 cases versus 17 in compatibility mode. Its
  full-corpus mean score was 0.6155 versus 0.3513; all positive aggregate gain
  came from the 14 newly accepted cases. On the same 17 accepted raw inputs,
  native scores were lower on average for each model.
- Reduction remained economically useful on this corpus. Hybrid v3 scored
  0.6620 and accepted all cases. Native recorded downstream cost was about
  6.7 times the hybrid cost. Native-versus-hybrid quality intervals overlap zero.
- Four cases per model exceeded the 921,000-token safe prompt cap. The largest
  successful counted prompt was 693,398 tokens, not one million tokens.

### Engineering

- Bind model, reasoning, context mode/cap, prompt, adapter, config, and reduced
  context identity into cache validation.
- Deny tools and custom instructions, isolate Copilot home, redact errors, and
  validate prompt-time model identity.
- Add adapter tests for success, malformed output, provider failure, redaction,
  unsupported models, context limits, and identity mismatch.
- Validate native session, prompt-time, and usage-model identity, the
  `long_context` tier, the 922,000-token provider limit, and zero tool use.
- Add one pinned Drain3 configuration, deterministic output, privacy audits,
  static signal scoring, and downstream evaluation.
- Add Spearman, paired 10,000-sample bootstrap, token, latency, error, and cost
  analysis artifacts.
- Separate model-call latency from adapter end-to-end latency, and successful
  calls from rejected rows. Record observation counts and accepted-case
  comparisons with exact case lists. Reject missing paired comparison rows.

### Reproduction and cost

The upstream checkout base SHA is `fc957f0d0d0082019606cc20b8fb545683a03b44`.
The local study adds the adapters, analysis, and results in this change; the
adapter hashes and runtime versions are recorded in the report and manifests.
The frozen v1.2 SHA is `99591c1471118c95155976346df72f520a05f100`.
The run used Copilot CLI `1.0.82`, Copilot SDK `1.0.11` with bundled runtime
`1.0.79`, and Python `3.14.6`.

Canonical compatibility and native artifacts recorded 37,419,822 prompt tokens
and 320,990 completion tokens. Their observable token price was
`$86.59661195` before any included plan credits. The earlier `$87.27`
execution estimate is unverified because probe/retry usage is incomplete; it
is not a verified account charge. These costs cover downstream diagnosis,
not preparation of the frozen LLM summaries or local reducer computation.
Sol used the promotional price available on 2026-08-30.

### Limits

The compatibility CLI uses its serving system prompt; the native SDK replaces
that prompt. Runtime versions also differ. This is not an isolated causal
test of context size, nor a test of actual one-million-token inputs. The
scoring is a benchmark composite, not diagnosis accuracy. The 17-case subset
analysis is exploratory and its intervals are not adjusted for multiple
comparisons. Two compatibility contexts below the normal
cap failed after prompt overhead and are recorded as unsupported. Four native
raw cases exceeded the safe prompt cap. One malformed native response was
retried, and the failed call's exact usage was not exposed.

A matched SDK control would be needed before claiming a context-size-only
effect. No new paid runs are needed for the descriptive claims in this PR.

Saved Drain3 contexts preserve 11 trailing separators for empty templates.
The full staged whitespace check flags these data lines; they are retained
to preserve the exact evaluated inputs. Source/documentation whitespace is clean.

### Checklist

- [x] Frozen corpus and v1.2 artifacts unchanged
- [x] 157 cache tests and 10 hybrid tests pass locally
- [x] 29 Copilot/statistics tests and 3 Drain3 tests pass locally
- [x] Existing validators pass
- [x] Corpus fingerprint and protocol lock pass
- [x] No credentials found in new artifacts
- [x] Six statistics files reproduce byte for byte; summary and subset counts agree
- [x] No upstream PR, issue, push, or deployment created
- [ ] Hosted CI at the eventual published commit (not run; no push authorized)
