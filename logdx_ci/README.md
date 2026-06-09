# logdx-ci

Evaluation harness for **log reduction tools** targeting LLM root-cause
diagnosis on CI failures. Wraps the LogDx-CI v1.2 corpus (35 real GitHub
Actions failure cases, AI-drafted + author-verified ground truth) into a
five-minute Python API.

[![arXiv](https://img.shields.io/badge/arXiv-2605.28876-b31b1b.svg)](https://arxiv.org/abs/2605.28876)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](../LICENSE)

## Install

```bash
pip install logdx-ci                  # stub diagnoser only (no API key)
pip install 'logdx-ci[anthropic]'     # + Sonnet 4.6 diagnoser
```

V0 requires running from inside a clone of
[github.com/eyuansu62/LogDx](https://github.com/eyuansu62/LogDx) (the
corpus and shim scripts live there). V0.2 will fall back to fetching the
corpus from HuggingFace on first use.

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

# 2. Evaluate on the corpus
result = logdx_ci.evaluate(
    reducer=my_reducer,
    diagnoser="stub-debugger-v1",   # deterministic, no API key
    splits=["v2/dev"],              # fast subset (3 cases); omit for full 35
)

# 3. Inspect
print(result.summary())
```

Output (with `stub-debugger-v1`, a deterministic regex matcher — for
real scores comparable to the leaderboard, use `real-debugger-v2`):

```
LogDx-CI evaluation result
  diagnoser:           stub-debugger-v1
  cases evaluated:     3
  diagnosis_score_v1_1: 0.0167
  confident_error_rate: 0.0000
  mean reduced chars:  27,281
  elapsed:             0.1 sec
  closest baseline:    rtk-log (0.249, -0.232)

Note: stub-debugger-v1 is a deterministic regex matcher for smoke tests;
the comparison below is not apples-to-apples. Use diagnoser=
'real-debugger-v2' for scores comparable to the v1.2 leaderboard.

method                                score      tokens  note
--------------------------------------------------------------------------------
**YOU**                              0.0167      27,281
hybrid-grep-120k-rtk-tail            0.6700      19,844  +0.653 vs you
hybrid-grep-120k-tail                0.6660      19,753  +0.649 vs you
...
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

## V0 supported diagnosers

| Name | Model | API key | Speed | Cost |
|---|---|---|---|---|
| `stub-debugger-v1` | Deterministic regex stub | none | 0.5s / case | $0 |
| `real-debugger-v2` | Claude Sonnet 4.6 | `ANTHROPIC_API_KEY` | ~3s / case | ~$0.03 / case |

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
