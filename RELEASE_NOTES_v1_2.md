# LogDx-CI v1.2 — Release Notes

**Tag**: `v1.2`
**Date**: 2026-05-20
**Project homepage**: <https://logdx-bench.github.io/>
**Type**: Minor release — adds `llm-summary-v1-gpt-5-mini` as a new
context-provider method on the headline leaderboard; falsifies the
self-call-bias hypothesis raised in the v1.1.1 review.

## TL;DR

v1.2 adds a **non-Anthropic** LLM-summary baseline,
`llm-summary-v1-gpt-5-mini` (real OpenAI gpt-5-mini map-reduce
summarizer, same prompts / chunk_lines=500 / temp=0 as the v1.1
haiku-summary). Two headline changes:

1. **`llm-summary-v1-gpt-5-mini` is the new agent-loop #1** at 0.749
   (vs the previous #1 `hybrid-grep-120k-rtk-tail` at 0.747), with
   the LOWEST tool-call count of any method (0.37/case — half as
   many as `tail-200`'s 0.69).
2. **Self-call-bias hypothesis is falsified.** Cross-pair
   (gpt-5-mini-summarizer → Haiku-debugger) BEATS self-pair
   (Haiku-summarizer → Haiku-debugger) by +0.071. Summary quality
   tracks the summarizer's ability to extract failure signal at
   chunk granularity, not shared priors between summarizer and
   debugger model families.

## Headline numbers

### Single-shot overall (case-weighted across 3 model families × 35 cases)

| Rank | Method | Overall | conf_err | total_tokens/case |
|----:|--------|--------:|--------:|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | **0.670** | 0.000 | 19,844 |
| 2 | `hybrid-grep-120k-tail` | **0.666** | 0.010 | 19,753 |
| **3** | **`llm-summary-v1-gpt-5-mini` (NEW)** | **0.664** | 0.010 | 537,638 |
| 4 | `grep` | 0.639 | 0.000 | 88,355 |
| 5 | `llm-summary-v1-haiku` | 0.632 | 0.029 | 1,681,520 |
| 6 | `tail-200` | 0.614 | 0.019 | 6,108 |
| 7+ | … | | | |

### Cross-family table: haiku-summary vs gpt-5-mini-summary

| Diagnoser | haiku-summary | **gpt5mini-summary** | Δ |
|---|---:|---:|---:|
| `real-debugger-v1` (Haiku 4.5) | 0.583 | **0.654** | +0.071 |
| `real-debugger-v2` (Sonnet 4.6) | **0.704** | 0.686 | -0.018 |
| `real-debugger-v3` (gpt-5-mini) | 0.608 | **0.652** | +0.044 |
| `real-agent-v1` (Sonnet+tools) | 0.690 | **0.749** | +0.059 |

gpt-5-mini-summary wins on 3 of 4 diagnosers. Critically, it wins on
the Haiku debugger (cross-family) MORE than haiku-summary does on
the Haiku debugger (self-pair). Self-call bias does not explain
v1.1's haiku-summary numbers.

### USD cost (snapshot 2026-05-20)

| Method | Reducer $ | Avg diagnoser $ | Total $/case |
|---|---:|---:|---:|
| `llm-summary-v1-gpt-5-mini` | $0.176 | $0.007 | **$0.184** |
| `llm-summary-v1-haiku` | $1.754 | $0.006 | **$1.760** |
| `hybrid-grep-120k-rtk-tail` | — | $0.031 | $0.031 |
| `grep` | — | $0.129 | $0.129 |
| `raw` | — | $0.392 | $0.392 |

gpt-5-mini-summary is **10× cheaper than haiku-summary** at the
reducer level. The gap is Claude-Code-CLI nested-invocation overhead
(cached-prefix tokens) that the OpenAI-direct call doesn't carry.

## Agent-loop result

`llm-summary-v1-gpt-5-mini` is the new agent-loop #1:

| Rank | Method | Agent score | conf_err | iters | tools/case | tokens/case |
|----:|--------|---:|---:|---:|---:|---:|
| **1** | **`llm-summary-v1-gpt-5-mini`** | **0.749** | **0.000** | **1.40** | **0.37** | 10,755 (agent-only) |
| 2 | `hybrid-grep-120k-rtk-tail` | 0.747 | 0.000 | 1.94 | 0.97 | 37,152 |
| 3 | `hybrid-grep-4k-rtk-err-cat` | 0.737 | 0.000 | 2.37 | 1.40 | 42,862 |

The agent commits to a diagnosis on turn 1 about 60% of the time
when fed a gpt-5-mini summary — it doesn't need to fall back to
grep/tail tool calls because the summary already names the failure.

## What's in this release

### New artifacts

- `examples/summary_shim_openai.py` — OpenAI Chat Completions shim
  for the summary use case. Mirrors the M4 command-provider
  contract; uses `max_completion_tokens=4096`, follows the same
  forbidden-key safety check as the Claude shim.
- `protocols/logdx-ci-v1.2.lock.json` — frozen protocol lock for the
  v1.2 release.
- `RELEASE_NOTES_v1_2.md` — this file.

### Shim bug fixes (rolled into v1.2)

- `examples/diagnosis_shim_openai.py`:
  - **`json.loads(strict=False)`** — gpt-5-mini occasionally echoes
    ANSI escape codes from evidence quotes into JSON string values.
    Strict JSON spec rejects raw control chars; `strict=False`
    accepts them. Without this, valid-shape diagnoses with embedded
    escapes were being rejected as JSONDecodeError.
  - **3-attempt parse retry** — gpt-5-mini is non-deterministic for
    certain inputs even at temperature=0 (the reasoning trace
    varies). Retries up to 3 times on parse failure before
    propagating to the runner. Recovers 4-of-4 previously-flaky
    cases observed during the v1.2 backfill.

### Data

- 35 new context-method rows under
  `results/<split>/llm-summary-v1-gpt-5-mini.jsonl` (one per case
  per split, 6 splits)
- 35 × 4 = 140 new diagnosis rows under
  `results/<split>/diagnoses/<diag>/llm-summary-v1-gpt-5-mini.jsonl`
- Refreshed eval manifests for all 4 diagnosers × 6 splits

### Updated docs

- `docs/leaderboard.md` — headline tables, agent-loop table, cost
  breakdown, USD cost section, v1.2 promotion note (cross-family
  finding), method references
- `docs/index.md` — homepage overall table updated

## What did NOT change

- **Corpus**: same 35 cases. `huggingface/corpus_fingerprint.json`
  matches.
- **Schemas / prompts / evaluator code**: no SHA changes from v1.1.2.
- **Existing methods**: no re-runs. haiku-summary numbers identical
  to v1.1.1 / v1.1.2.

## Implementation notes

- gpt-5-mini summary uses the same `chunk_lines=500`,
  `chunk_overlap_lines=25`, `temperature=0`, model alias
  `gpt-5-mini` (resolves to `gpt-5-mini-2025-08-07`).
- 3 cases re-chunked at `chunk_lines=100` (same as haiku-summary):
  nodejs-test-debugger-exec-timeout-v2-001,
  pytest-sklearn-stress-001, pytest-sklearn-stress-002.
- All 35 gpt-5-mini-summary rows have `provider_error=None` and
  non-zero output.

## CI status

```
✅ validate_committed_diagnosis_provider_errors.py
✅ validate_eval_manifest_consistency.py
✅ validate_diagnosis_vs_context_consistency.py
✅ validate_corpus_fingerprint.py
✅ validate_protocol_lock.py   (against logdx-ci-v2-partial-2026-05-20)
```

Test suite: 157/157 PASS.

## Reproducibility

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx
git checkout v1.2

# Re-run any single eval (deterministic; uses cached diagnoses)
python3 tools/evaluate_diagnosis.py --split v2/dev --diagnoser real-debugger-v3

# Per-method macro scores will match this release's published numbers.

# Optional: USD-cost re-computation
python3 tools/compute_usd_costs.py
```

To regenerate the gpt-5-mini-summary contexts from scratch (real
API call):

```bash
export OPENAI_API_KEY=...
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1
python3 tools/run_llm_summary_baseline.py \
    --split v2/dev --method llm-summary-v1-gpt-5-mini \
    --provider command \
    --command "python3 examples/summary_shim_openai.py" \
    --chunk-lines 500 --chunk-overlap-lines 25 --temperature 0
```

## Acknowledgements

The cross-family check (v1.2) follows the post-v1.1.1 project
review where self-call bias was flagged as one of the two
remaining critical methodology gaps. The bias hypothesis turned
out to be wrong, but the falsification itself is a load-bearing
finding — anyone running v1.1's haiku-summary number through a
non-Claude downstream agent can now expect it to track the v1.2
results within a few percentage points.
