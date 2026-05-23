# CILogBench M6 experiment — `stub-debugger-v1` on `dev`

## Experiment summary

- Split: **dev**
- Cases: **5**
- Diagnoser: `stub-debugger-v1`
- Provider: `command`
- Config: `configs/diagnosers/example.debugger-v1-command.json` (SHA256 `c3a6b43895a3…`)
- Prompt: `prompts/debugger_v1.md` (SHA256 `ecffdf03c99a…`)
- Methods requested: `all`
- Methods run: `grep`, `llm-summary-v1-mock`, `raw`, `rtk-err-cat`, `rtk-log`, `rtk-read`, `tail`
- Manifest: `results/dev/m6_real_debugger_stub-debugger-v1.manifest.json`

## Diagnoser config summary

- Provider name: `user-configured`
- Model name: `user-configured-model`
- Model version: `unknown`
- Temperature: `0`, top_p: `1.0`, max_output_tokens: `1200`, json_mode: `True`, deterministic: `True`
- allow_raw_context: `True`, max_context_tokens: `None`, on_context_too_large: `mark_unsupported`, allow_truncation: `False`

## Privacy audit summary

- Total pattern hits: **0**
- Methods scanned: **7**
- Disclaimer: This scanner is best-effort. It only detects patterns listed in patterns_checked. Absence of hits does NOT prove a context is safe to share. Review contexts manually before opting in to an external model provider.

## Diagnosis metric table (M5)

| Context Method | Success | Category Acc | Critical Mention | Must Mention | Forbidden | Conf Err | Abstention | Context Tok | score_v1 (exp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grep | 100.0% | 80.0% | 18.0% | 20.0% | 0.0% | 0.0% | 20.0% | 42.5k | 0.334 |
| llm-summary-v1-mock | 100.0% | 60.0% | 21.3% | 20.0% | 0.0% | 0.0% | 40.0% | 1.5k | 0.304 |
| raw | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 0.0% | 130.2k | 0.374 |
| rtk-err-cat | 100.0% | 100.0% | 28.0% | 25.0% | 0.0% | 0.0% | 0.0% | 9.4k | 0.434 |
| rtk-log | 100.0% | 40.0% | 3.3% | 10.0% | 0.0% | 0.0% | 60.0% | 385 | 0.150 |
| rtk-read | 100.0% | 80.0% | 18.0% | 35.0% | 0.0% | 0.0% | 0.0% | 130.2k | 0.374 |
| tail | 100.0% | 60.0% | 27.0% | 40.0% | 0.0% | 0.0% | 0.0% | 5.6k | 0.384 |

## Signal-vs-diagnosis comparison

Joins the M2–M4 signal-recall evaluator with this run's diagnosis evaluator. Use it to check whether higher upstream signal preservation correlates with higher downstream diagnosis accuracy for this specific diagnoser and prompt.

| Context Method | Signal Recall | Critical Signal Recall | Context Reduction | Diagnosis Category Acc | Critical Mention | Conf Err | Context Tok |
|---|---:|---:|---:|---:|---:|---:|---:|
| grep | 86.7% | 88.3% | 69.8% | 80.0% | 18.0% | 0.0% | 42.5k |
| llm-summary-v1-mock | 42.4% | 43.3% | 98.5% | 60.0% | 21.3% | 0.0% | 1.5k |
| raw | 100.0% | 100.0% | 0.0% | 80.0% | 18.0% | 0.0% | 130.2k |
| rtk-err-cat | 73.3% | 77.7% | 86.7% | 100.0% | 28.0% | 0.0% | 9.4k |
| rtk-log | 25.7% | 30.3% | 99.2% | 40.0% | 3.3% | 0.0% | 385 |
| rtk-read | 100.0% | 100.0% | 0.0% | 80.0% | 18.0% | 0.0% | 130.2k |
| tail | 63.3% | 70.0% | 81.6% | 60.0% | 27.0% | 0.0% | 5.6k |

## Confident-error analysis

Confident errors (`confidence ≥ 0.70` AND (wrong category OR forbidden claim present)) are the key agent-safety failure mode: the diagnoser sounds sure while being wrong. Rates below are per context method.

No confident errors recorded on this run.

## Abstention analysis

Abstention (`root_cause_category == "unknown"` OR `confidence < 0.25`) is not automatically bad. It is preferable to a confident wrong answer when the context is poor.

- `grep` — 1/5 abstained: `lint-react-001`
- `llm-summary-v1-mock` — 2/5 abstained: `lint-react-001`, `mypy-pandas-001`
- `rtk-log` — 3/5 abstained: `jest-nextjs-001`, `lint-react-001`, `mypy-pandas-001`

## Interpretation guardrails

- This is a **5-case dev split**. Numbers are not a public leaderboard and should not be generalized without a holdout split (planned for a later milestone).
- A single fixed model's behavior may not transfer to other models. Do not conclude "method X beats method Y for LLM debugging in general" — the supportable statement is about this diagnoser and this prompt only.
- Deterministic text-matching metrics are a proxy. A high `critical_mention` value does not prove the diagnosis is actually useful; a low one does not prove it was wrong.
- If `deterministic` is false in the config, the numbers in this report may drift between runs even with temperature 0.
- Do not tune prompts, models, or methods after reading this report and present the new run as a comparison — it invalidates the experiment.

