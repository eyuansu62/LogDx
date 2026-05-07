# cilog-bench / simple_rules_legacy (legacy)

**Status: legacy.** The repository has pivoted from "CI log compressor" to
CILogBench (a benchmark for CI failure context quality). This CLAUDE.md
applies **only** to the code under `baselines/simple_rules_legacy/cilog/`;
it documents the invariants the legacy compressor was designed around and
is kept for anyone revisiting the legacy baseline. New work belongs under
`cases/`, `schemas/`, `tools/`, and future `baselines/*` subdirectories.
See the top-level `README.md` for current direction.

Originally: benchmark harness to answer one question — **is rule-based CI
log compression worth building into a production tool?** That question is
no longer the project's objective; RTK (external) already fills the
production role, and this baseline is retained for benchmark comparison.

---

## Core thesis

CI logs are optimized for humans reading a terminal — timestamps, ANSI colors,
progress bars, boilerplate step headers, base64 screenshots. When an AI agent
reads them, 90%+ of that content is noise that wastes context window without
improving decisions.

We compress by **rule, not by ML**. If the compression is right, an engineer
reading only the compressed output should be able to diagnose the failure
exactly as fast as reading the original — just with 10× less to scroll through.

---

## The two metrics that matter

Any change to the compressor must be evaluated on **both** of these together.
Optimizing one without the other is meaningless.

1. **Token reduction** — compressed_tokens / original_tokens. Target ≥ 85%.
2. **Signal preservation** — of the distinctive signals extracted from the
   raw log (failed test names, exception messages, stack locations, exit
   codes, GHA error markers), what fraction appears verbatim in the output?
   Target ≥ 95%.

**Why both:** compressing to an empty string gives 100% reduction and 0%
preservation. Keeping the log untouched gives 0% reduction and 100%
preservation. Only the product of the two is useful.

When reporting results or proposing changes, always state both numbers.
Never celebrate a reduction improvement without checking preservation
didn't drop.

---

## Non-negotiable invariants

These rules exist because violating them silently produces worse outputs
than doing nothing. Don't relax them without explicit discussion.

**1. Never modify history, only compress new output.**
If we reshape or summarize content that's already in the Agent's context,
we break prompt caching — which costs more than any compression saves.
The compressor only processes new output about to enter context; it never
rewrites what's already there.

**2. Compression must be *verifiable*, not just *lossy*.**
Every compressed section keeps a `section_id` anchor. The design assumes
a future "expand on demand" verb (`cilog expand <section_id>`) so an
Agent that finds the compressed view insufficient can retrieve the original
untouched. This is non-negotiable — it's the safety net that lets
aggressive compression be safe at all.

**3. Over-compression is worse than under-compression.**
Hiding a real bug (stacktrace frame, assertion message, exit code) from
the Agent costs more than keeping extra noise. If a rule is uncertain,
it keeps the line. This is why per-framework compressors are conservative:
they *drop known-noise*, they don't *keep only known-signal*.

**4. Zero ML in the compression path.**
Not because ML is bad, but because this project is validating whether
rules alone are enough. Adding an ML classifier short-circuits the
question we're trying to answer. Signal extraction in `signals.py` for
measurement is fine — that's evaluation, not compression.

**5. No network calls in the compressor.**
`cilog/compressor.py` and `cilog/signals.py` are pure functions of their
input. Network I/O belongs in `cilog/bench.py` (fetching GH logs) and
nowhere else. This keeps the core deterministic and fast.

---

## Project structure and conventions

```
cilog/
├── compressor.py    # the compression engine (pure, no I/O)
├── signals.py       # signal extraction for preservation measurement
├── tokens.py        # token counting (tiktoken with char-approx fallback)
├── bench.py         # runner: fetches logs, invokes compressor, writes report
├── report.py        # HTML report builder (pure, no I/O except final write)
├── synthetic.py     # built-in fixtures for pipeline smoke testing
└── __init__.py
```

**Architectural rules:**

- `compressor.py` has no dependencies on other `cilog/` modules. It takes
  a string in, returns a string out plus metadata. Anything else is wrong.
- `signals.py` imports nothing from `compressor.py`. Signal extraction
  must be an *independent* reading of the raw log, or the preservation
  metric becomes circular (compressor agreeing with itself).
- `bench.py` is the only module allowed to do I/O (network, disk caches).
- `synthetic.py` fixtures are **expected to stay stable**. They're
  regression tests as much as they're smoke samples. Don't edit them
  to make new code pass — add new fixtures instead.

---

## How to add a new framework compressor

This is the most common change. The workflow:

1. Add a fixture to `synthetic.py` that captures real failure patterns
   for that framework (1 failing + many passing is the interesting case).
2. Add a detection rule to `detect_framework()` in `compressor.py`.
3. Write a `compress_<framework>()` function. Start conservative — keep
   everything that *looks* like failure context, drop only patterns
   you've confirmed are noise.
4. Register it in `FRAMEWORK_COMPRESSORS`.
5. Run `python -m cilog.bench --synthetic` and check both metrics moved
   in the right direction (reduction up OR same, preservation did not drop).
6. If available, run on 5+ real samples of that framework from GitHub.

A good compressor typically hits 80-95% reduction with 100% preservation
on its target framework. If preservation drops below 95%, the rules are
too aggressive — back off.

---

## How to debug a bad result

If a sample shows poor reduction *or* poor preservation:

- **Poor reduction, good preservation**: the noise in this log isn't
  covered by any existing rule. Read the raw log, find the dominant
  noise pattern, decide if it deserves a framework-specific compressor
  or a generic noise rule.
- **Good reduction, poor preservation**: the compressor is dropping
  lines that contain decision-critical info. Look at
  `SignalReport.missing_by_type` in the output — it tells you exactly
  which signal types got lost. Usually means a framework detector
  misfired (treating pytest output as generic, for example).
- **Both bad**: the framework detector failed outright and generic
  fallback kicked in on ill-suited content. Add a framework rule.

---

## What we deliberately do NOT do

These aren't accidents; they're scope decisions. Don't "fix" them without
discussion.

- **No streaming / incremental mode.** Load the whole log, process,
  emit. 50 MB logs fit in memory. Streaming adds complexity we don't
  need for a benchmark.
- **No GitLab CI / CircleCI / Buildkite.** GitHub Actions is 80%+ of
  the market and uses `##[group]` markers we can exploit. Adding other
  CIs dilutes the validation signal.
- **No "smart" tokenizer fallback.** When tiktoken can't download its
  BPE files, we use `chars / 3.5`. This is calibrated for code and
  "good enough" for relative comparison. Don't add a third tokenizer
  option.
- **No config file / settings.** Every behavior is either a default or
  a CLI flag. If a knob is worth having, it's worth being a flag;
  otherwise it's worth being a default.
- **No tests in `tests/`.** The synthetic fixtures in `synthetic.py`
  are the tests. If the pipeline regresses, the benchmark numbers move —
  that's the assertion.

---

## Communication style when working on this project

- When proposing a change, state its expected effect on **both metrics**
  before making it. If you can't predict the effect, run the benchmark
  before and after and report the delta.
- When reporting benchmark results, include the numbers, not adjectives.
  "93.3% reduction, 100% preservation" is useful. "Great compression"
  is not.
- When a change hurts one metric to help another, that's a trade-off
  decision, not a bug fix. Flag it explicitly.
- If you find a real-world log pattern that breaks the compressor,
  **add it to `synthetic.py` first**, then fix the compressor. The
  fixture ensures the regression can't come back silently.

---

## The decision this project exists to inform

After ~20 real GitHub samples across diverse frameworks, the data should
answer:

- **Go build the Rust MVP** if median reduction ≥ 85% AND median
  preservation ≥ 95% AND the failure modes are enumerable.
- **Don't build it** if either metric misses consistently, or if the
  logs where we compress well are the ones users weren't struggling
  with anyway.
- **Iterate** otherwise — usually by targeting the specific noise type
  that's dominating the remaining bytes (base64 blobs, matrix job
  duplication, debug-level logs, etc.).

Every line of code in this repo should be earning its keep against
this decision.
