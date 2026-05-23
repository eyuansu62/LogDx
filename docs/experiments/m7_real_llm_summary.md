# M7 experiment — Real LLM summary context + diagnosis

M7 adds the first **real LLM-generated summary** as a context-provider
baseline, then feeds that summary to the M5/M6 fixed diagnoser. It is
the first milestone where CILogBench can compare three major context
strategies inside one protocol:

```
  simple filters (tail / grep)
  external-tool compression (RTK)
  LLM-generated summary
          ↓
   fixed diagnoser (same model + prompt for all methods)
          ↓
   deterministic diagnosis evaluator
```

## Two model roles, kept separate

M7 has exactly two model roles. They may share a provider, but the
benchmark must record them separately:

| role | input | output | prompt |
|---|---|---|---|
| **summarizer** | raw.log chunk(s) | compact failure context | `prompts/llm_summary_v1_{map,reduce}.md` |
| **diagnoser** | one method's context | structured diagnosis JSON | `prompts/debugger_v1.md` |

M7 answers: **does the summary context help the fixed diagnoser?** It
does not answer "can the summarizer itself diagnose?" — that is a
different experiment (and the summarizer's output may happen to include
a diagnosis, which is allowed but not the thing we grade).

## Name guard

The wrapper refuses method names that are not `llm-summary-v1-<slug>`,
and explicitly refuses the reserved `llm-summary-v1-mock`. Example
valid slugs:

```
llm-summary-v1-claude
llm-summary-v1-gpt
llm-summary-v1-local
llm-summary-v1-stub      (the infrastructure stub we ship)
```

Do not include API keys, account IDs, or private endpoint names in the
slug. The slug shows up in filesystem paths, reports, and manifests.

## Privacy gates (two of them)

1. **Raw-log audit.** Before calling any external summarizer, the
   wrapper runs `tools/audit_context_privacy.py --context-method raw`
   and stops if any secret pattern fires. Override with
   `--allow-privacy-audit-hits` (but inspect first — read
   `reports/legacy/dev_privacy_audit.md`).
2. **External-LLM opt-in.** Even after a clean audit, the wrapper
   refuses to invoke the summarizer or the diagnoser unless either:
   - `CILOGBENCH_ALLOW_EXTERNAL_LLM=1` in the environment, OR
   - `--allow-external-llm` on the CLI.

The wrapper is deliberately noisy about these gates. They are the two
layers of defense that protect CI logs from leaving the host without
an explicit decision.

## Running

```bash
# 0. Validate + audit (happen automatically inside the wrapper).

# 1. Author a summary shim that speaks the M4 stdin/stdout contract:
#    stdin  JSON = {"messages":[...], "temperature":0, "metadata":{stage,...}}
#    stdout JSON = {"content":"...", "usage":{"input_tokens":..,"output_tokens":..}}
#    See examples/summary_shim_stub.py for a no-API-key reference.

# 2. Opt in + set the shim.
export LLM_SUMMARY_COMMAND="/path/to/summary_shim"
export DIAGNOSIS_COMMAND="/path/to/diagnosis_shim"
export CILOGBENCH_ALLOW_EXTERNAL_LLM=1

# 3. Run the full M7 loop.
python tools/run_m7_real_summary_experiment.py \
    --summarizer-config configs/summarizers/example.llm-summary-v1-command.json \
    --summarizer-name my-summarizer-v1 \
    --method llm-summary-v1-my-summarizer \
    --diagnoser-config configs/diagnosers/example.debugger-v1-command.json \
    --diagnoser-name my-debugger-v1 \
    --allow-external-llm
```

Useful flags:

- `--summary-only` — stop after generating + evaluating the summary
  (useful when you want to inspect the summary before spending diagnosis
  tokens).
- `--diagnosis-only` — skip summary regeneration, assume the manifest
  already exists (useful when swapping diagnosers).
- `--no-cache` — force regeneration; bypasses M4 and M5 caches.
- `--strict` — abort on first error instead of recording `provider_error`
  and continuing.

## What the wrapper does in order

1. `tools/validate_cases.py cases/<split>` — structural + line-range
   sanity.
2. `tools/audit_context_privacy.py --context-method raw` — best-effort
   secret scan on raw logs; gate.
3. `tools/run_llm_summary_baseline.py --provider command --method
   llm-summary-v1-<slug>` — map-reduce summarization using the shim.
   Output lands at `results/<split>/<method>.jsonl` +
   `results/<split>/<method>/<case>.txt`.
4. `tools/evaluate_signal_recall.py --method <method>` — text-based
   signal recall on the new summary context, using the same evaluator
   used for raw/tail/grep/RTK.
5. (Optional) `tools/run_diagnosis.py` + `tools/evaluate_diagnosis.py`
   + `tools/render_diagnosis_report.py` — run the fixed diagnoser
   over the new summary context and produce the M5 diagnosis report.
6. `tools/render_report.py` — regenerate the cross-method
   signal-recall report so the new summary method appears alongside
   raw/tail/grep/RTK/mock.
7. Write the M7 manifest
   (`results/<split>/m7_real_summary_<slug>.manifest.json`) and the
   M7 experiment report
   (`reports/<split>_m7_real_summary_<slug>.md`).

## Cost accounting

The M7 report surfaces three distinct token costs, because an LLM
summary can have a tiny final context while being expensive to produce:

- **Summary Processing** — input + output tokens across every map and
  reduce call, averaged per case. Non-summary baselines report 0.
- **Final Context** — tokens in the artifact handed to the diagnoser.
  This is what a chat model or agent would actually consume downstream.
- **Diagnosis Output** — tokens emitted by the diagnoser JSON.

`Total Pipeline = Summary Processing + Final Context + Diagnosis
Output`. A 99% final-context reduction that burned 50× the raw tokens
during summarization may be a worse trade than it looks.

## Supportable / unsupportable statements

M7 supports claims of the form:

> On 5 dev cases, with summarizer S (prompt SHA `abc…`, config SHA
> `def…`) and debugger D (prompt SHA `xyz…`), the summary method
> preserved Y% of required signals and produced diagnosis category
> accuracy Z%.

M7 does **not** support claims of the form:

- "LLM summaries are generally better than RTK."
- "This benchmark proves summarization is solved."
- "Model A is a better CI debugger than Model B."

The reasons are unchanged from earlier milestones: 5-case dev split,
one prompt version, deterministic text matching as a proxy for semantic
correctness, one fixed diagnoser. Publishing a winner requires a
frozen holdout split (planned for M8).

## Common failure modes

- **Summarizer returns plain text, not JSON.** The M4 runner accepts
  plain text and wraps it. Record whether output is structured in the
  report (so future readers know what the provider actually did).
- **Summary omits critical evidence.** Let the signal-recall + diagnosis
  evaluators catch it; do not patch individual summaries. Annotate the
  failure mode in the "Summary failure modes" section of the M7 report.
- **Summarizer hallucinates unsupported facts.** The diagnoser's
  `valid_evidence_quote_rate` catches downstream citations that don't
  appear in the summary. `forbidden_claim_violations` catches the ones
  we explicitly annotated as wrong. Combined they form a deterministic
  hallucination proxy.
- **Raw log too large for a single call.** The M4 runner already
  chunks. The summarizer config's `chunking.chunk_lines` /
  `chunk_overlap_lines` keys let you tune it. Keep `max_chunks: null`
  for dev; set explicit caps only when the model API genuinely
  limits you.
- **Privacy audit hits.** The default is "stop". Overriding with
  `--allow-privacy-audit-hits` is a conscious choice — explain it in
  the commit message that accompanies the experiment artifacts.

## What M7 does not do

- No MCP / search-agent baseline. Planned for M11.
- No LLM judge; evaluation stays deterministic.
- No public leaderboard. Planned after M8 adds a holdout split.
- No prompt tuning per case, per method, or per model.
