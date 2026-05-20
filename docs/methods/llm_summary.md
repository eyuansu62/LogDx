# llm-summary-v1

`llm-summary-v1` is a context-provider baseline that summarizes a
failed CI log with a map-reduce LLM call sequence. CILogBench scores it
on **signal preservation** — whether the exact debugging evidence
required by ground truth survives summarization. M4 does not grade
root-cause accuracy; that is a later milestone.

## Pipeline

1. Read `cases/<split>/<case_id>/raw.log`.
2. Prefix every line with `L000123:` (1-indexed, zero-padded) so the
   model can cite line numbers.
3. Split into chunks of `--chunk-lines` (default 400) with
   `--chunk-overlap-lines` (default 20) between adjacent chunks.
4. For each chunk run the **MAP** prompt (`prompts/llm_summary_v1_map.md`).
   Chunks that return `NO_RELEVANT_FAILURE_SIGNAL` are dropped.
5. Concatenate the remaining MAP outputs in chunk order and run the
   **REDUCE** prompt (`prompts/llm_summary_v1_reduce.md`) to produce
   the final compact markdown context.
6. Write the final context to
   `results/<split>/<method>/<case_id>.txt` and a manifest row to
   `results/<split>/<method>.jsonl`.
7. Write per-call artifacts to
   `results/<split>/<method>/chunks/<case_id>/{map_NNN.json,reduce.json}`.

## Providers

The runner is provider-agnostic. Pick one with `--provider`:

### `mock` (default)

A deterministic local heuristic that extracts failure-keyword lines
with the same regex used by the `grep` baseline and bucketizes them
into the seven reduce sections. It does not call an LLM and does not
reach the network. Use it to verify the schema, the evaluator, and
the report pipeline.

**Infrastructure-only / legacy.** Named `llm-summary-v1-mock`.
From v1.0 through early v1.1 the mock stood in for the
LLM-summary class on the leaderboard because the real summarizer
had only been prototyped on a 16-case subset. **v1.1 promoted the
real `llm-summary-v1-haiku` to the headline** (full 35-case
backfill on all 4 diagnoser families) — the mock is no longer the
LLM-summary representative. Use the mock for schema /
infrastructure smoke tests only.

```bash
python tools/run_llm_summary_baseline.py \
    --split dev --provider mock --method llm-summary-v1-mock
```

### `command`

Shell out to a user-supplied command that speaks JSON. The command
receives one request on stdin:

```json
{
  "messages": [
    {"role": "system", "content": "...map prompt..."},
    {"role": "user",   "content": "...chunk content..."}
  ],
  "temperature": 0,
  "max_output_chars": 8000,
  "metadata": {
    "case_id": "pytest-pandas-001",
    "prompt_version": "llm_summary_v1",
    "stage": "map"
  }
}
```

and must return on stdout:

```json
{
  "content": "...markdown or bullets...",
  "provider": "example-provider",
  "model": "example-model",
  "usage": {"input_tokens": 12345, "output_tokens": 1200}
}
```

If `usage` is missing the runner estimates tokens as `chars / 4` and
records `usage_source: "estimated"` in the manifest.

```bash
export LLM_SUMMARY_COMMAND="/path/to/my_llm_cli"
python tools/run_llm_summary_baseline.py \
    --split dev --provider command \
    --command "$LLM_SUMMARY_COMMAND" \
    --method llm-summary-v1
```

The runner validates each returned payload minimally (`content` must
exist). Anything else is up to your shim.

## Privacy warning

**The `command` provider may send raw CI logs to an external model.**
The runner prints a warning in `--help` and default-selects `mock` for
exactly this reason. Before running with `--provider command`, confirm:

- The logs you are about to send do not contain private keys, tokens,
  or other secrets. CILogBench runs a secret-pattern scan during
  `validate_cases.py`, but the scan is heuristic and not exhaustive.
- The destination model + provider comply with your org's data-handling
  policy.

CILogBench never runs `rtk init`, modifies agent hooks, or auto-installs
any tool. All invocations are explicit subprocess calls.

## Caching

LLM calls are expensive and stochastic. Every call is cached under:

```
results/cache/<method>/<cache_key>.json
```

`cache_key` is a SHA-256 over `{case_id, raw_log_sha256, prompt_version,
prompt_sha256, provider, method, chunk_index, chunk_sha256, temperature,
max_output_chars, stage}`. Rerunning with the same inputs is free
(cache hit) and logs `cache_hit_count` in the manifest. Pass `--force`
to bypass the cache and re-call the provider.

## Manifest fields

LLM manifest rows include everything M2/M3 rows have, plus:

- `line_mapping_available: false` — LLM summaries do not preserve
  original line numbers.
- `mapping_type: "text"` — the evaluator scores via substring match.
- `included_line_ranges: []`.
- `metadata.provider` — `mock` or `command`.
- `metadata.model` — if the provider response includes it.
- `metadata.prompt_version` — `llm_summary_v1`.
- `metadata.map_prompt_sha256`, `metadata.reduce_prompt_sha256` — so
  later rebuilds can tell whether a prompt change triggered the delta.
- `metadata.chunk_lines`, `metadata.chunk_overlap_lines`,
  `metadata.chunk_count`, `metadata.non_empty_chunk_count`.
- `metadata.cache_hit_count`, `metadata.cache_miss_count`.
- `metadata.usage.{input_tokens, output_tokens, usage_source}` where
  `usage_source ∈ {provider_reported, estimated, mixed}`.
- `metadata.final_context_tokens_estimate` — chars/4 on the final
  context text.

## Scoring

The evaluator (`tools/evaluate_signal_recall.py`) treats LLM manifests
the same way as RTK ones:

- `evidence_span_coverage` is `N/A` (line mapping unavailable).
- `signal_recall` / `critical_signal_recall` use the normalized
  substring / alias / file-fallback logic (strict, case-sensitive,
  ANSI-stripped, CRLF→LF).

Paraphrased strings **do not count**. The summary must quote the exact
value (or a declared alias) for a signal to register. M4 is
evidence-preservation, not semantic diagnosis.

## Tuning knobs

```
--chunk-lines 400
--chunk-overlap-lines 20
--max-map-output-chars 8000
--max-reduce-output-chars 12000
--temperature 0           (strongly recommended for reproducibility)
--force                   (bypass cache)
--case-id <id>            (debug a single case; writes .debug.<id>.jsonl)
--fail-fast               (abort on the first case failure)
```

## Known caveats

- **Long logs.** If all chunks return `NO_RELEVANT_FAILURE_SIGNAL`
  (e.g. a badly-chunked boundary), the runner emits a
  deterministically-structured "no signal identified" summary rather
  than calling REDUCE. This keeps the output non-empty and schema-
  valid, but produces obviously poor recall.
- **Paraphrasing.** Even with the explicit "preserve exact strings"
  instruction, real models rephrase sometimes. When recall drops,
  inspect `results/<split>/<method>/chunks/<case_id>/map_*.json` to
  see what each chunk yielded.
- **Cache invalidation.** Changing a prompt rewrites
  `map_prompt_sha256` / `reduce_prompt_sha256` and invalidates the
  cache automatically. Changing the chunk size does too, because the
  chunk content hash changes.
