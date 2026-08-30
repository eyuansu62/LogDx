# Proposed upstream text

## Recommendation

**PR. Do not open it automatically.**

Local packaging is authorized. Publication is not: do not push, create an
issue, or open a PR until the user explicitly approves that action.

## Proposed PR title

Study: model-pinned Copilot backends, long-context coverage, and Drain3 baseline

## Review guide

This is a research and tooling contribution, not a v1.3 release or a claim of
better diagnosis accuracy than v1.2. The study commit contains 1,221 changed
files; 1,197 are saved result files. Review the implementation separately from
that evidence. Later packaging changes add documentation and review fixes.

1. **Claims and limits:** read the [study report](reports/logdx_v1_3_modern_model_study.md).
   Check coverage versus quality, same-case comparisons, costs, and the
   system-prompt/runtime differences before interpreting the headline scores.
2. **Implementation:** review `examples/diagnosis_shim_copilot_*.py`,
   `tools/run_diagnosis.py`, `logdx_ci/diagnoser.py`, and
   `configs/diagnosers/copilot-*.json` for model identity, cache isolation,
   external-call opt-in, and fail-closed behavior.
3. **Baseline and analysis:** review `tools/run_drain3_baseline.py`,
   `configs/drain3/`, and `tools/analyze_v1_3_*.py`, then their focused tests.
4. **Evidence:** start with `results/v1_3/study_summary.json` and the six
   statistics files. Per-split `eval_diagnosis_copilot-*.json` files hold scored
   results; `diagnoses/copilot-*/` holds manifests and per-case responses.
   Drain3 manifests, templates, and static evaluations are under each split.
5. **Reproduction:** follow the [offline checks first](CONTRIBUTING.md#check-the-saved-statistics-without-model-calls).
   Paid examples use a separate checkout. No paid runs are needed to review
   the saved findings.

The frozen corpus, prompts, schemas, protocol locks, and historical result
files remain unchanged. Extra local files are not part of the proposed
change; share a Git commit or a Git archive, not a ZIP of the working folder.

## Proposed PR body

### Summary

This change adds tool-disabled GitHub Copilot CLI and SDK diagnosis backends and
one corpus-wide Drain3 `0.9.11` context provider. It keeps all new results
separate from frozen v1.2 artifacts.

Please review this as an experimental tooling and validation study, not a
release or an accuracy improvement. The [review guide](PR_PROPOSAL.md#review-guide)
separates implementation from saved evidence; the
[offline reproduction steps](CONTRIBUTING.md#check-the-saved-statistics-without-model-calls)
do not require model access or paid calls.

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
  `long_context` tier, and the 922,000-token provider limit. The hardened SDK
  also requires explicit zero-tool telemetry; the historical adapter's
  missing-count limitation is disclosed below.
- Add one pinned Drain3 configuration, deterministic output, privacy audits,
  static signal scoring, and downstream evaluation.
- Add Spearman, paired 10,000-sample bootstrap, token, latency, error, and cost
  analysis artifacts.
- Separate model-call latency from adapter end-to-end latency, and successful
  calls from rejected rows. Record observation counts and accepted-case
  comparisons with exact case lists. Reject missing paired comparison rows.
- Validate fresh and cached public API responses against the configured model.
  Native API preflight checks the SDK instead of requiring a standalone CLI.
- Preserve Python 3.10 compatibility for the base package and legacy `all`
  extra. The optional native SDK requires Python 3.11+.
- Preserve the exact evaluated SDK source under `examples/frozen/`; new calls
  use the hardened adapter. No saved diagnosis responses were changed.

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

The evaluated code is recorded in study commit
`93ceec395c9d0d7ee7738b9db2c49f455ffdee43`. The native adapter hash in the
manifests matches the frozen SDK source, not the hardened current adapter.
Offline statistics still reproduce byte for byte after the review fixes.

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

The evaluated SDK adapter treated missing tool counts as zero. Sessions were
configured without tools, but saved normalized counts cannot independently
prove explicit zero-tool telemetry because raw events were not retained.
This is fixed for future calls, not retroactively repaired in the evidence.

A matched SDK control would be needed before claiming a context-size-only
effect. No new paid runs are needed for the descriptive claims in this PR.

Saved Drain3 contexts preserve 11 trailing separators for empty templates.
The full staged whitespace check flags these data lines; they are retained
to preserve the exact evaluated inputs. Source/documentation whitespace is clean.

### Checklist

- [x] Frozen corpus and v1.2 artifacts unchanged
- [x] 157 cache tests and 10 hybrid tests pass locally
- [x] 32 Copilot/statistics, 14 API, 12 analysis-integrity, and 6 Drain3 tests pass locally (231 tests total with the suites above)
- [x] Existing validators pass
- [x] Corpus fingerprint and protocol lock pass
- [x] No credentials found in new artifacts
- [x] Six statistics files reproduce byte for byte; summary and subset counts agree
- [x] No upstream PR, issue, push, or deployment created
- [ ] Hosted CI at the eventual published commit (not run; no push authorized)
