# CILogBench M7 experiment — `llm-summary-v1-stub` on `dev`

## Experiment summary

- Summary method: `llm-summary-v1-stub`
- Summarizer: `example-summarizer-v1`
- Diagnoser: `stub-debugger-v1`
- Split: **dev**
- Compared context methods: `raw`, `tail`, `grep`, `rtk-read`, `rtk-log`, `rtk-err-cat`, `llm-summary-v1-mock`, `llm-summary-v1-stub`
- Manifest: `results/dev/m7_real_summary_stub.manifest.json`

## Summarizer config summary

- Config: `configs/summarizers/example.llm-summary-v1-command.json` (SHA256 `915d46a630b8…`)
- Provider name: `user-configured`
- Model name: `user-configured-model` (version `unknown`)
- temperature=`0`, top_p=`1.0`, max_output_tokens=`1800`, json_mode=`False`, deterministic=`True`

## Diagnoser config summary

- Config: `configs/diagnosers/example.debugger-v1-command.json` (SHA256 `c3a6b43895a3…`)
- Provider name: `user-configured`
- Model name: `user-configured-model` (version `unknown`)
- temperature=`0`, max_output_tokens=`1200`, json_mode=`True`, deterministic=`True`

## Prompt hashes

- map_prompt_sha256: `684c5b978f4aa109f4241d7aa8187f63f9511c4193d6581c1195e15c379922e6`
- reduce_prompt_sha256: `e3739738b7136af3956f3712e7b76babd9224b6854dcc60ff16546a3fbb16702`
- debugger_prompt_sha256: `ecffdf03c99a91b0f8f75e086720d9fb8db96af0d9dae5285baf679c9c9d28de`

## Privacy audit summary

- Total pattern hits: **0**
- Methods scanned: **1**
- Disclaimer: This scanner is best-effort. It only detects patterns listed in patterns_checked. Absence of hits does NOT prove a context is safe to share. Review contexts manually before opting in to an external model provider.

## Signal recall table

| Context Method | Signal Recall | Critical Recall | Evidence Coverage | Reduction | Mapping | Processing Tokens | Final Context Tokens |
|---|---:|---:|---:|---:|---|---:|---:|
| raw | 100.0% | 100.0% | 100.0% | 0.0% | line | 0 | 130.3k |
| tail | 63.3% | 70.0% | 30.7% | 81.6% | line | 0 | 5.6k |
| grep | 86.7% | 88.3% | 78.4% | 69.8% | line | 0 | 42.5k |
| rtk-read | 100.0% | 100.0% | N/A | 0.0% | text | 0 | 130.3k |
| rtk-log | 25.7% | 30.3% | N/A | 99.2% | text | 0 | 387 |
| rtk-err-cat | 73.3% | 77.7% | N/A | 86.7% | text | 0 | 9.4k |
| llm-summary-v1-mock | 42.4% | 43.3% | N/A | 98.5% | text | 181.4k | 1.5k |
| llm-summary-v1-stub | 42.4% | 43.3% | N/A | 98.3% | text | 181.4k | 1.6k |

_Processing Tokens_ averages summarization cost (map+reduce input+output) per case. 0 for non-summary baselines. _Final Context Tokens_ estimates the text handed to the downstream reader (= byte_size/4).

## Diagnosis metric table

| Context Method | Success | Category Acc | Critical Mention | Must Mention | File Recall | Test Recall | Forbidden | Conf Err | Abstention | Context Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 130.2k | 0.374 |
| tail | 100.0% | 60.0% | 27.0% | 40.0% | 23.3% | 0.0% | 0.0% | 0.0% | 0.0% | 5.6k | 0.384 |
| grep | 100.0% | 80.0% | 18.0% | 20.0% | 0.0% | 0.0% | 0.0% | 0.0% | 20.0% | 42.5k | 0.334 |
| rtk-read | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 130.2k | 0.374 |
| rtk-log | 100.0% | 40.0% | 3.3% | 10.0% | 0.0% | 0.0% | 0.0% | 0.0% | 60.0% | 385 | 0.150 |
| rtk-err-cat | 100.0% | 100.0% | 28.0% | 25.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 9.4k | 0.434 |
| llm-summary-v1-mock | 100.0% | 60.0% | 21.3% | 20.0% | 20.0% | 0.0% | 0.0% | 0.0% | 40.0% | 1.5k | 0.304 |
| llm-summary-v1-stub | 100.0% | 60.0% | 21.3% | 20.0% | 20.0% | 0.0% | 0.0% | 0.0% | 40.0% | 1.6k | 0.304 |

## Cost table

Per-case averages. _Total Pipeline_ = summary processing + final context (sent to diagnoser) + diagnosis output.

| Context Method | Summary Processing | Final Context | Diagnosis Output | Total Pipeline | Estimated External Calls |
|---|---:|---:|---:|---:|---:|
| raw | 0 | 130.3k | 126 | 130.4k | — |
| tail | 0 | 5.6k | 137 | 5.7k | — |
| grep | 0 | 42.5k | 124 | 42.6k | — |
| rtk-read | 0 | 130.3k | 128 | 130.4k | — |
| rtk-log | 0 | 387 | 87 | 474 | — |
| rtk-err-cat | 0 | 9.4k | 137 | 9.5k | — |
| llm-summary-v1-mock | 181.4k | 1.5k | 116 | 183.1k | 67 |
| llm-summary-v1-stub | 181.4k | 1.6k | 116 | 183.1k | 67 |

## Signal-vs-diagnosis comparison

Joins the signal recall table above with the diagnosis table for this experiment. Rows with missing signal recall or missing diagnosis show N/A in the corresponding column.

| Context Method | Signal Recall | Critical Signal Recall | Reduction | Diagnosis Category Acc | Critical Mention | Conf Err | Context Tok |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 100.0% | 100.0% | 0.0% | 80.0% | 18.0% | 0.0% | 130.2k |
| tail | 63.3% | 70.0% | 81.6% | 60.0% | 27.0% | 0.0% | 5.6k |
| grep | 86.7% | 88.3% | 69.8% | 80.0% | 18.0% | 0.0% | 42.5k |
| rtk-read | 100.0% | 100.0% | 0.0% | 80.0% | 18.0% | 0.0% | 130.2k |
| rtk-log | 25.7% | 30.3% | 99.2% | 40.0% | 3.3% | 0.0% | 385 |
| rtk-err-cat | 73.3% | 77.7% | 86.7% | 100.0% | 28.0% | 0.0% | 9.4k |
| llm-summary-v1-mock | 42.4% | 43.3% | 98.5% | 60.0% | 21.3% | 0.0% | 1.5k |
| llm-summary-v1-stub | 42.4% | 43.3% | 98.3% | 60.0% | 21.3% | 0.0% | 1.6k |

## Per-case summary audit

| Case | Ctx Tok | Proc Tok | Signal Recall | Critical Recall | Category Acc | Critical Mention | Conf Err | Abstained |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `cargo-tokio-001` | 2.3k | 139.8k | 28.6% | 33.3% | 100.0% | 16.7% | — | — |
| `jest-nextjs-001` | 1.3k | 371.0k | 50.0% | 50.0% | 100.0% | 50.0% | — | — |
| `lint-react-001` | 180 | 8.0k | 33.3% | 33.3% | 0.0% | 0.0% | — | YES |
| `mypy-pandas-001` | 2.0k | 207.1k | 33.3% | 40.0% | 0.0% | 0.0% | — | YES |
| `pytest-pandas-001` | 2.1k | 181.3k | 66.7% | 60.0% | 100.0% | 40.0% | — | — |

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

