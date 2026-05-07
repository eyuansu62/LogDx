# CILogBench M7 experiment — `llm-summary-v1-haiku` on `holdout`

## Experiment summary

- Summary method: `llm-summary-v1-haiku`
- Summarizer: `claude-haiku-4-5-summary-v1`
- Split: **holdout**
- Compared context methods: `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-haiku`
- Manifest: `results/holdout/m7_real_summary_haiku.manifest.json`

## Summarizer config summary

- Config: `configs/summarizers/haiku.json` (SHA256 `26dae6cfc87d…`)
- Provider name: `anthropic`
- Model name: `claude-haiku-4-5` (version `2026-04-25`)
- temperature=`0`, top_p=`1.0`, max_output_tokens=`1800`, json_mode=`False`, deterministic=`False`

## Prompt hashes

- map_prompt_sha256: `684c5b978f4aa109f4241d7aa8187f63f9511c4193d6581c1195e15c379922e6`
- reduce_prompt_sha256: `e3739738b7136af3956f3712e7b76babd9224b6854dcc60ff16546a3fbb16702`

## Privacy audit summary

- Total pattern hits: **0**
- Methods scanned: **1**
- Disclaimer: This scanner is best-effort. It only detects patterns listed in patterns_checked. Absence of hits does NOT prove a context is safe to share. Review contexts manually before opting in to an external model provider.

## Signal recall table

| Context Method | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Processing Tokens | Final Context Tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 11.1k |
| tail | 93.1% | 95.0% | 100.0% | 51.3% | line | 0 | 4.6k |
| grep | 89.8% | 95.0% | 73.1% | 87.0% | line | 0 | 1.5k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 11.1k |
| rtk-log | 33.1% | 36.0% | N/A | 97.5% | text | 0 | 261 |
| rtk-err-cat | 48.8% | 43.0% | N/A | 97.0% | text | 0 | 367 |
| llm-summary-v1-mock | 60.1% | 58.0% | N/A | 96.6% | text | 13.7k | 362 |
| llm-summary-v1-haiku | 47.6% | 57.0% | N/A | 96.2% | text | 2.8k | 384 |

_Processing Tokens_ averages summarization cost (map+reduce input+output) per case. 0 for non-summary baselines. _Final Context Tokens_ estimates the text handed to the downstream reader (= byte_size/4).

## Cost table

Per-case averages. _Total Pipeline_ = summary processing + final context (sent to diagnoser) + diagnosis output.

| Context Method | Summary Processing | Final Context | Diagnosis Output | Total Pipeline | Estimated External Calls |
|---|---:|---:|---:|---:|---:|
| raw | 0 | 11.1k | 0 | 11.1k | — |
| tail | 0 | 4.6k | 0 | 4.6k | — |
| grep | 0 | 1.5k | 0 | 1.5k | — |
| rtk-read | 0 | 11.1k | 0 | 11.1k | — |
| rtk-log | 0 | 261 | 0 | 261 | — |
| rtk-err-cat | 0 | 367 | 0 | 367 | — |
| llm-summary-v1-mock | 13.7k | 362 | 0 | 14.0k | 14 |
| llm-summary-v1-haiku | 2.8k | 384 | 0 | 3.2k | 13 |

## Signal-vs-diagnosis comparison

Joins the signal recall table above with the diagnosis table for this experiment. Rows with missing signal recall or missing diagnosis show N/A in the corresponding column.

| Context Method | Signal Recall | Critical Signal Recall | Reduction | Diagnosis Category Acc | Critical Mention | Conf Err | Context Tok |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 100.0% | 0.0% | N/A | N/A | N/A | 11.1k |
| tail | 93.1% | 95.0% | 51.3% | N/A | N/A | N/A | 4.6k |
| grep | 89.8% | 95.0% | 87.0% | N/A | N/A | N/A | 1.5k |
| rtk-read | 100.0% | 100.0% | 0.0% | N/A | N/A | N/A | 11.1k |
| rtk-log | 33.1% | 36.0% | 97.5% | N/A | N/A | N/A | 261 |
| rtk-err-cat | 48.8% | 43.0% | 97.0% | N/A | N/A | N/A | 367 |
| llm-summary-v1-mock | 60.1% | 58.0% | 96.6% | N/A | N/A | N/A | 362 |
| llm-summary-v1-haiku | 47.6% | 57.0% | 96.2% | N/A | N/A | N/A | 384 |

## Per-case summary audit

| Case | Ctx Tok | Proc Tok | Signal Recall | Critical Recall | Category Acc | Critical Mention | Conf Err | Abstained |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `actions-terraform-001` | 192 | 1.8k | 0.0% | 0.0% | N/A | N/A | — | — |
| `dependabot-cargo-001` | 430 | 3.1k | 50.0% | 50.0% | N/A | N/A | — | — |
| `docs-transformers-001` | 440 | 2.3k | 66.7% | 80.0% | N/A | N/A | — | — |
| `pushpr-nextjs-001` | 455 | 4.3k | 71.4% | 80.0% | N/A | N/A | — | — |
| `tsc-typescript-001` | 404 | 2.3k | 50.0% | 75.0% | N/A | N/A | — | — |

## Summary failure modes (qualitative)

Inspect `results/<split>/<method_name>/chunks/<case>/` for per-chunk map outputs and the final reduce output to judge whether the summarizer paraphrases away evidence, collapses multiple failures, or invents facts. Classic patterns to watch for:

- omitting file names or test identifiers that do appear in the raw log;
- paraphrasing exact error strings so literal signal recall drops without a real loss of meaning;
- collapsing multiple distinct failures into one;
- overfocusing on the last failure (common with tail-biased prompts);
- overfocusing on GitHub Actions runner/setup noise;
- inventing a root cause the log does not support;
- quoting lines that do not appear in the context (caught automatically by `valid_evidence_quote_rate` at diagnosis time).

Fill this section with concrete observations after reading the per-case outputs; do not edit the benchmark code or the prompt to patch individual cases.

## Interpretation guardrails

- This is a **5-case dev split**. M7 numbers cannot support statements of the form "LLM summaries are better than RTK in general".
- M7 CAN support statements of the form "on these 5 dev cases, with summarizer S and prompt v1 (SHA `xxx…`), the final summary preserved Y% of required signals and produced diagnosis category accuracy Z% under debugger D (prompt SHA `yyy…`)."
- Signal recall is a text-preservation proxy. A summary may paraphrase correctly and still lose literal matches; cross-check with the diagnosis category accuracy and critical-signal mention.
- Cost matters. Report summary processing tokens alongside final context size; a 99% final-context reduction that required 50× more processing tokens than raw may not be cheaper end-to-end.
- Do not retune prompts/models/methods after reading this report and present the new run as a comparison — that invalidates the experiment.

