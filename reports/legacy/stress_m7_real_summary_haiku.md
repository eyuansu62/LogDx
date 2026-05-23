# CILogBench M7 experiment — `llm-summary-v1-haiku` on `stress`

## Experiment summary

- Summary method: `llm-summary-v1-haiku`
- Summarizer: `claude-haiku-4-5-summary-v1`
- Split: **stress**
- Compared context methods: `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-haiku`
- Manifest: `results/stress/m7_real_summary_haiku.manifest.json`

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
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 91.6k |
| tail | 100.0% | 100.0% | 100.0% | 33.5% | line | 0 | 5.0k |
| grep | 86.2% | 87.5% | 86.5% | 89.7% | line | 0 | 1.9k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 91.6k |
| rtk-log | 30.3% | 34.2% | N/A | 96.9% | text | 0 | 164 |
| rtk-err-cat | 39.2% | 44.2% | N/A | 97.2% | text | 0 | 2.6k |
| llm-summary-v1-mock | 55.9% | 64.2% | N/A | 91.9% | text | 101.2k | 373 |
| llm-summary-v1-haiku | 66.4% | 71.2% | N/A | 69.9% | text | 2.3k | 346 |

_Processing Tokens_ averages summarization cost (map+reduce input+output) per case. 0 for non-summary baselines. _Final Context Tokens_ estimates the text handed to the downstream reader (= byte_size/4).

## Cost table

Per-case averages. _Total Pipeline_ = summary processing + final context (sent to diagnoser) + diagnosis output.

| Context Method | Summary Processing | Final Context | Diagnosis Output | Total Pipeline | Estimated External Calls |
|---|---:|---:|---:|---:|---:|
| raw | 0 | 91.6k | 0 | 91.6k | — |
| tail | 0 | 5.0k | 0 | 5.0k | — |
| grep | 0 | 1.9k | 0 | 1.9k | — |
| rtk-read | 0 | 91.6k | 0 | 91.6k | — |
| rtk-log | 0 | 164 | 0 | 164 | — |
| rtk-err-cat | 0 | 2.6k | 0 | 2.6k | — |
| llm-summary-v1-mock | 101.2k | 373 | 0 | 101.6k | 40 |
| llm-summary-v1-haiku | 2.3k | 346 | 0 | 2.6k | 8 |

## Signal-vs-diagnosis comparison

Joins the signal recall table above with the diagnosis table for this experiment. Rows with missing signal recall or missing diagnosis show N/A in the corresponding column.

| Context Method | Signal Recall | Critical Signal Recall | Reduction | Diagnosis Category Acc | Critical Mention | Conf Err | Context Tok |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 100.0% | 0.0% | N/A | N/A | N/A | 91.6k |
| tail | 100.0% | 100.0% | 33.5% | N/A | N/A | N/A | 5.0k |
| grep | 86.2% | 87.5% | 89.7% | N/A | N/A | N/A | 1.9k |
| rtk-read | 100.0% | 100.0% | 0.0% | N/A | N/A | N/A | 91.6k |
| rtk-log | 30.3% | 34.2% | 96.9% | N/A | N/A | N/A | 164 |
| rtk-err-cat | 39.2% | 44.2% | 97.2% | N/A | N/A | N/A | 2.6k |
| llm-summary-v1-mock | 55.9% | 64.2% | 91.9% | N/A | N/A | N/A | 373 |
| llm-summary-v1-haiku | 66.4% | 71.2% | 69.9% | N/A | N/A | N/A | 346 |

## Per-case summary audit

| Case | Ctx Tok | Proc Tok | Signal Recall | Critical Recall | Category Acc | Critical Mention | Conf Err | Abstained |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `cleanup-k8s-stress-001` | 302 | 2.5k | 60.0% | 75.0% | N/A | N/A | — | — |
| `cleanup-tsc-stress-001` | 355 | 2.0k | 60.0% | 75.0% | N/A | N/A | — | — |
| `docbuild-hf-stress-001` | 373 | 2.9k | 60.0% | 60.0% | N/A | N/A | — | — |
| `prettier-react-stress-001` | 355 | 1.7k | 85.7% | 75.0% | N/A | N/A | — | — |

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

