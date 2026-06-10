# logdx-ci

Evaluation harness for **log reduction tools** targeting LLM root-cause
diagnosis on CI failures. Wraps the LogDx-CI v1.2 corpus (35 real GitHub
Actions failure cases, AI-drafted + author-verified ground truth) into a
five-minute Python API.

[![arXiv](https://img.shields.io/badge/arXiv-2605.28876-b31b1b.svg)](https://arxiv.org/abs/2605.28876)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](../LICENSE)

## Install

```bash
pip install logdx-ci
```

The corpus + scoring code (~20 MB) is auto-fetched from the LogDx
GitHub release on first use and cached at `~/.logdx_ci_cache/repo/`.
No clone required.

For the LLM-based diagnosers (`real-debugger-v1/v2/v3`) you also need
either the `claude` CLI on PATH (Haiku / Sonnet) or `OPENAI_API_KEY`
(gpt-5-mini). The default `static-signal-recall` diagnoser needs
neither — runs deterministic, free, in under a second.

## Five-minute tutorial

```python
import logdx_ci

# 1. Define your log reducer
def my_reducer(raw_log: str) -> str:
    """Toy: keep only lines containing 'error'."""
    return "\n".join(
        line for line in raw_log.split("\n")
        if "error" in line.lower()
    )

# 2. Evaluate on the corpus (default = static, no LLM, no API key, <1s)
result = logdx_ci.evaluate(
    reducer=my_reducer,
    # diagnoser defaults to "static-signal-recall"
    # splits defaults to all 6 (= 35 cases)
)

# 3. Inspect
print(result.summary())
```

Output:

```
LogDx-CI evaluation result
  diagnoser:           static-signal-recall
  cases evaluated:     35
  critical_signal_recall: 0.7536
  mean reduced chars:  3,053
  elapsed:             0.05 sec
  closest baseline:    tail (0.754, +0.000)

method                                   csr      tokens  note
--------------------------------------------------------------------------------
**YOU**                               0.7536       3,053
raw                                   0.9649           —  +0.211 vs you
rtk-read                              0.9649           —  +0.211 vs you
grep                                  0.8411           —  +0.087 vs you
hybrid-grep-120k-rtk-tail-v3          0.8225           —  +0.069 vs you
hybrid-grep-120k-tail-v2              0.8189           —  +0.065 vs you
llm-summary-v1-gpt-5-mini             0.8104           —  +0.057 vs you
tail                                  0.7536           —  +0.000 vs you
llm-summary-v1-haiku                  0.7009           —  -0.053 vs you
hybrid-grep-4k-rtk-err-cat-v1         0.6810           —  -0.073 vs you
rtk-err-cat                           0.5372           —  -0.216 vs you
rtk-log                               0.1819           —  -0.572 vs you
```

## Use the real diagnoser

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

result = logdx_ci.evaluate(
    reducer=my_reducer,
    diagnoser="real-debugger-v2",   # Claude Sonnet 4.6
)
```

Cost preview (per case, at 2026-05-20 pricing): ~$0.03 for an average
reduced context (~20k tokens). Full 35-case eval ≈ $1.05 + your reducer's
own cost.

## Command-line

```bash
# Define your reducer as `reduce` in a Python file:
cat > my_reducer.py << 'EOF'
def reduce(log):
    return log[-2000:]
EOF

# Evaluate
logdx-ci eval --reducer my_reducer.py --diagnoser stub-debugger-v1 --splits v2/dev
```

## Supported diagnosers

| Name | What it measures | API key | Speed | Cost |
|---|---|---|---|---|
| `static-signal-recall` | Did the reducer **preserve** required signals? (text-only, no LLM) | none | <1s / 35 cases | $0 |
| `stub-debugger-v1` | Smoke test only (deterministic regex stub) | none | <1s / 35 cases | $0 |
| `real-debugger-v2` | Did Sonnet 4.6 give a correct **diagnosis** from the reduced context? | `claude` CLI logged in | ~3s / case | ~$0.03 / case |

**Recommended workflow**: prototype with `static-signal-recall` (free,
deterministic, 50ms for 35 cases) → confirm pipeline → spend $1 on
`real-debugger-v2` for leaderboard-comparable diagnosis scores.

V0.2 will add `real-debugger-v1` (Haiku), `real-debugger-v3` (gpt-5-mini),
and `real-agent-v1` (Sonnet + 4 tools, 5-turn cap).

## Caching

By default, diagnosis results are cached at `~/.logdx_ci_cache/diagnosis/`
keyed by `(diagnoser, case_id, reduced_context_hash)`. Re-running the same
reducer is free.

## Citing

```bibtex
@article{qin2026logdx,
  title         = {{LogDx-CI}: Benchmarking Log Reduction Tools
                  for LLM Root-Cause Diagnosis},
  author        = {Qin, Bowen},
  year          = {2026},
  eprint        = {2605.28876},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE},
}
```
