# Headroom `LogCompressor` evaluated on LogDx-CI v1.2

| | |
|---|---|
| Tool | [`headroom-ai`](https://github.com/chopratejas/headroom) 0.24.0 |
| Module | `headroom.transforms.LogCompressor` |
| Config | `LogCompressorConfig()` defaults |
| Evaluated against | LogDx-CI v1.2 (35 cases, 6 splits) |
| Diagnoser | `static-signal-recall` (no LLM, deterministic) |
| Date | 2026-06-09 |

## Headline

Two complementary numbers, both on the full 35-case corpus, mean
compressed size **13,955 chars / case (~3,500 tokens)**:

| Metric | Headroom | Closest baseline | What it measures |
|---|---:|---|---|
| `critical_signal_recall` (static, no LLM) | **0.605** | between `rtk-err-cat` (0.537) and `hybrid-grep-4k-rtk-err-cat-v1` (0.681) | Did the reducer preserve ground-truth signal text? |
| `diagnosis_score_v1_1` (Claude Sonnet 4.6) | **0.601** | `tail-200` (0.614, +0.013) | Did the diagnoser produce the right root-cause from the reduced context? |

**Token efficiency story**: Headroom hits diagnosis_score 0.601 at ~3,500
tokens / case, vs `tail-200` at 0.614 with ~6,108 tokens. **Roughly half
the tokens at -0.013 score**. confident_error_rate = 0.029 (vs
tail-200's 0.019, hybrid-rtk-tail's 0.000).

## Pareto frontier (tokens × score)

Out of the 12 methods evaluated, **Headroom is on the Pareto frontier
for both metrics** — no method delivers a better score at fewer
tokens, and no method delivers fewer tokens at a comparable or better
score. It is the second point on the curve (just above `rtk-log`'s
extreme-compression corner).

**Pareto front by `diagnosis_score_v1_1`** (5 of 12 methods, low → high tokens):

```
rtk-log              810t    0.249
→ headroom-LogComp  3,500t   0.601   ← this run
tail-200            6,108t   0.614
hybrid-grep-120k-tail            19,753t   0.666
hybrid-grep-120k-rtk-tail        19,844t   0.670
```

**Pareto front by `critical_signal_recall`** (7 of 12 methods):

```
rtk-log              810t    0.182
→ headroom-LogComp  3,500t   0.605   ← this run
tail-200            6,108t   0.754
hybrid-grep-120k-tail            19,753t   0.819
hybrid-grep-120k-rtk-tail        19,844t   0.823
grep                             88,355t   0.841
rtk-read                        274,289t   0.965
```

Dominated under both metrics (not on either frontier):
`hybrid-grep-4k-rtk-err-cat-v1`, `rtk-err-cat`, `raw`,
`llm-summary-v1-gpt-5-mini`, `llm-summary-v1-haiku`.

The headline takeaway: **at ~half the tokens of `tail-200` (3.5k vs
6.1k), Headroom retains 98% of the diagnosis quality** (0.601 / 0.614).
The closest comparison point on the Pareto curve to its left is
`rtk-log` at one-quarter the tokens — but with a -0.35 score drop;
that's the cliff Headroom is sitting above.

## Position on the diagnosis-score leaderboard

| Method | tokens | diagnosis_score_v1_1 | conf. err |
|---|---:|---:|---:|
| `hybrid-grep-120k-rtk-tail` | 19,844 | 0.670 | 0.000 |
| `hybrid-grep-120k-tail` | 19,753 | 0.666 | 0.010 |
| `llm-summary-v1-gpt-5-mini` | 537,638 | 0.664 | 0.010 |
| `grep` | 88,355 | 0.639 | 0.000 |
| `llm-summary-v1-haiku` | 1,681,520 | 0.632 | 0.029 |
| `tail-200` | 6,108 | 0.614 | 0.019 |
| **`headroom LogCompressor` (defaults)** | **~3,500** | **0.601** | **0.029** |
| `hybrid-grep-4k-rtk-err-cat-v1` | 19,892 | 0.573 | 0.029 |
| `rtk-err-cat` | 19,850 | 0.470 | 0.029 |
| `raw` | 275,248 | 0.353 | 0.000 |
| `rtk-read` | 274,289 | 0.349 | 0.010 |
| `rtk-log` | 810 | 0.249 | 0.133 |

Headroom sits **7th of 12** by score, but **2nd-most-compact** (only
`rtk-log` is smaller, and it costs heavily on score). On the static
signal-recall metric:

| Method | critical_signal_recall |
|---|---:|
| `raw` / `rtk-read` | 0.965 |
| `grep` | 0.841 |
| `hybrid-grep-120k-rtk-tail-v3` | 0.823 |
| `hybrid-grep-120k-tail-v2` | 0.819 |
| `llm-summary-v1-gpt-5-mini` | 0.810 |
| `tail-200` | 0.754 |
| `llm-summary-v1-haiku` | 0.701 |
| `hybrid-grep-4k-rtk-err-cat-v1` | 0.681 |
| **`headroom LogCompressor`** | **0.605** |
| `rtk-err-cat` | 0.537 |
| `rtk-log` | 0.182 |

## Config sensitivity

The defaults are aggressive (`max_total_lines=100`,
`max_errors=10`). Raising capacity helps moderately:

| Config | CSR | mean chars / case | zero-score cases |
|---|---:|---:|---:|
| `defaults` (max 100 lines, 10 errors) | 0.605 | 13,955 | 6 |
| `max 200 lines` | 0.638 | 16,038 | 5 |
| `max 200 lines, 50 errors` | 0.657 | 24,204 | 5 |
| `max 500 lines, 100 errors, 20 stacks` | 0.698 | 38,698 | 3 |

Even with 5× capacity (`max_total_lines=500`), LogCompressor stays
below `tail-200` (0.754) and `llm-summary-v1-haiku` (0.701) — the gap
isn't closable by capacity tuning alone.

## Distribution

**Static signal-recall** (35 cases):

| Bucket | Cases | Notable |
|---|---:|---|
| Perfect (1.0) | 11 | `pytest-pandas`, `pushpr-nextjs`, `pytest-sklearn-stress`, `moby-buildx-bake`, `nodejs-test-debugger-exec-timeout`, … |
| ≥ 0.5 | 18 | |
| < 0.5 | 10 | |
| Zero | 6 | `pnpm-jest-config`, `dubbo-samples-test-timeout`, `pnpm-audit-vuln-ip-address`, `argocd-race-conditions`, `cpython-tcl-windows-matrix`, `numpy-pytest-segfault-argsort` |

**LLM diagnosis_score** (35 cases):

| Bucket | Cases | Notable |
|---|---:|---|
| ≥ 0.8 | 12 | `cargo-tokio`, `pytest-sklearn-stress` ×2 (0.95), `pandas-cpp-xsimd-neon64`, `pushpr-nextjs` (0.9) |
| ≥ 0.5 | 22 | |
| < 0.5 | 12 | |
| Zero | 1 | `dubbo-samples-test-timeout` (only case where Sonnet produced no usable diagnosis) |

The static metric has 6 zero-score cases; the LLM metric has only 1.
This is the expected "**LLM rescue**" effect — Sonnet can sometimes
infer a root cause from partial / paraphrased signals that strict
substring matching misses. The cases that remain hard under the LLM
metric (`pnpm-audit-vuln-ip-address` at 0.150, `numpy-pytest-segfault`
at 0.150, `airflow-precommit-tsc-middle` at 0.242) are the ones where
Headroom drops the *failure-region* lines, not just specific signal
strings.

## Methodology

```python
from headroom.transforms import LogCompressor
import logdx_ci

lc = LogCompressor()                                # defaults
def headroom_reducer(raw_log: str) -> str:
    return lc.compress(raw_log).compressed

result = logdx_ci.evaluate(reducer=headroom_reducer)
print(result.summary())
```

We used `LogCompressor` directly because it's purpose-built for log
text. We also ran the canonical `headroom.compress(messages, ...)`
entry point across multiple configs:

| Config | CSR | mean chars / case | Note |
|---|---:|---:|---|
| `compress()` defaults | 0.965 | 1,107,816 | passthrough — user messages not compressed by default |
| `compress(compress_user_messages=True)` | 0.181 | 27,523 | router collapsed to dedupe garbage (≈ `rtk-log` baseline) |
| `compress(CUM=True, target_ratio=0.5)` | 0.181 | 27,523 | `target_ratio` ignored for single user message |
| `compress(CUM=True, target_ratio=0.8)` | 0.181 | 27,523 | same |

So `compress()` either does nothing (defaults) or collapses to
dedupe-output that destroys diagnosis-relevant signal (0.181). For
single-shot CI log reduction, **`LogCompressor` (0.605) is the best
entry point** in the public Headroom API surface we found.

If we're missing a config or higher-level entry point that's
specifically meant for "compress one CI log file" (vs the
agent-message-trace use case Headroom's headline numbers cover), happy
to re-run.

`static-signal-recall` is deterministic — it counts whether the
ground-truth `required_signals` (failed test names, stack locations,
error type strings) survive in the reducer's output. No LLM call, ~8s
for 35 cases, $0 cost. This is a **necessary-not-sufficient** check
for downstream LLM diagnosis quality. The follow-up step is to score
the same reducer under `diagnoser="real-debugger-v2"` (Claude
Sonnet 4.6) for leaderboard-comparable `diagnosis_score_v1_1` numbers.

## Reproduce

```bash
git clone https://github.com/eyuansu62/LogDx.git
cd LogDx
pip install -e .
pip install headroom-ai
python -c "
import logdx_ci
from headroom.transforms import LogCompressor
lc = LogCompressor()
print(logdx_ci.evaluate(lambda log: lc.compress(log).compressed).summary())
"
```

Raw per-case scores: [`headroom_logcompressor_default.json`](headroom_logcompressor_default.json).
