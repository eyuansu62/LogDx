# Why RTK underperforms on CI log diagnosis — and what would fix it

A follow-up analysis on the [LogDx-CI v1.0](https://logdx-bench.github.io/)
leaderboard. This post is constructive, not adversarial: I want to
explain *why* a tool that ships excellent compression numbers ranks
6th, 8th, and 10th on our benchmark — and why that ranking is
**not** a verdict on RTK as a product.

## TL;DR

[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk)'s
compression strategy assumes "long output = a lot of redundancy."
CI failure logs violate that assumption: the critical signal is
often a single non-redundant line, surrounded by lines that *look*
redundant to a frequency-based compressor (50 similar-looking stack
frames; thousands of `test_xxx PASSED` lines around one
`test_yyy FAILED`). RTK's inductive bias is **redundancy-based**;
the task's information structure is **positional + surface-form-
based**. That mismatch is the root cause, not "RTK doesn't know what
a failure looks like."

## The result that needs explaining

On 35 real GitHub Actions failure cases × 3 model families (Claude
Haiku 4.5, Claude Sonnet 4.6, OpenAI gpt-5-mini), case-count-weighted
macro `diagnosis_score_v1_1`:

| Rank | Method | Overall |
|----:|--------|--------:|
| 1 | `hybrid-grep-120k-rtk-tail` | **0.670** |
| 2 | `hybrid-grep-120k-tail` | **0.666** |
| 3 | `grep` | 0.639 |
| 4 | `llm-summary-v1-haiku` <sub>*(v1.1)*</sub> | 0.632 |
| 5 | `tail-200` | 0.614 |
| 6 | `hybrid-grep-4k-rtk-err-cat` | 0.573 |
| 7 | **`rtk-err-cat`** | **0.470** |
| 8 | `raw` | 0.353 |
| 9 | **`rtk-read`** | **0.349** |
| 10 | **`rtk-log`** | **0.249** |
| — | `llm-summary-v1-mock` <sub>*(legacy)*</sub> | 0.328 |

Full leaderboard:
<https://logdx-bench.github.io/leaderboard.html>.

The obvious framing is "RTK doesn't understand CI failures, so it
loses to methods that do." This framing is **wrong**, or at best
incomplete. Here's why.

## The intuitive (but wrong) explanation

A natural first guess: "RTK's compression is domain-agnostic; `grep`
and `tail` are tuned to CI failure patterns, so of course they win."

There's a clean counter-example in the leaderboard: **`tail-200`
has zero domain knowledge** — it literally just returns the last
200 lines — and it still beats every single RTK mode by a wide
margin (0.614 vs the best RTK at 0.470).

A method with no failure-pattern knowledge, no failure-keyword
matching, and no semantic understanding of CI logs beats a tool that
*does* try to recognize errors (`rtk err cat`). So "RTK doesn't know
about failures" can't be the root cause — `tail-200` doesn't know
about failures either.

## The right explanation: inductive bias mismatch

Every log-reduction method has an **inductive bias** — an implicit
assumption about what important information looks like:

| Method | Bias (what it assumes is important) |
|---|---|
| `tail-200` | **Positional**: important info is at the end |
| `grep` | **Surface-form**: important info matches predictable patterns (`FAILED`, `Error:`, `panic:`, `Traceback`, exit codes) |
| `rtk-log` | **Rarity / dissimilarity**: important info has low frequency or is dissimilar to other lines |
| `rtk-err-cat` | **Keyword + rarity**: important info is in error-flavored regions |

CI failure logs have a specific information structure:

1. **Failure signal is positionally biased toward the end.** pytest
   summary, cargo error output, docker build error, npm install
   failure — almost always within the last few hundred lines.
2. **Failure signal has predictable surface forms.** A small set of
   regex patterns (`FAILED`, `Error:`, `panic:`, `error\[E\d+\]`,
   `Traceback`, `AssertionError`, `exit code [1-9]`) covers most of
   the failures across ecosystems.
3. **Noise is high-volume and *similar-looking*.** Stack frames are
   lexically similar to each other. Test-progress lines look like
   other test-progress lines. CI matrix retries repeat the same
   build steps. Network warnings repeat.

`tail-200`'s bias matches (1) directly. `grep`'s bias matches (2)
directly. **RTK's bias matches (3)** — but (3) is the *noise*, not
the signal.

Worse: RTK's similarity-based deduplication can't tell the
difference between "noise that looks similar to other noise" and
"signal that happens to look similar to surrounding noise." A real
`AssertionError` line embedded in a 50-frame stack trace looks
*lexically* very similar to the 49 framework frames around it. To a
frequency-based compressor they're all "stack-trace-shaped lines";
the unique one gets merged into the cluster summary.

This is the deepest version of why `rtk-log` lands at rank 10: its
core objective (maximize compression ratio via similarity-based
dedup) is **negatively correlated** with the actual downstream
objective (preserve the surgical detail needed for root-cause
identification).

## Why grep and tail win — and it's not because they're "smart"

`grep`'s win isn't that it understands failures. It's that:

- The **bias** (matching `FAILED` / `Error:` / etc) happens to be a
  good prior for CI logs — these patterns are nearly universal.
- The **mechanism** (regex + 3/8 lines of context) preserves
  failure lines *unmodified* and keeps their immediate
  surroundings. No merging, no rewriting, no risk of detail loss.

`tail-200`'s win is even simpler:

- It allocates 100% of its token budget to the positionally-most-
  signal-rich region.
- It does zero compression, zero rewriting, zero merging.
- For most CI logs under ~50k lines, the failure summary fits in
  the last 200 lines.

In information-theoretic terms: **both methods exploit a strong
positional + surface-form prior that RTK's general-purpose
compression algorithm cannot match without explicit domain tuning.**

## Where RTK still wins

The leaderboard's #1 method, `hybrid-grep-120k-rtk-tail` (0.670),
uses RTK's `err-cat` mode as an **intermediate fallback** when the
grep output exceeds 120k tokens but `rtk_input_truncated == False`.

On the argocd case in our stress split (89k-line build log),
`rtk-err-cat` scores **0.56 on Sonnet**, while the v2 hybrid that
falls back to `tail-200` on the same case only scores **0.12**.

In other words: **RTK is irreplaceable as a middle band for
oversized logs.** When `grep` outputs blow past the token budget
and `tail-200` would drop too much upstream context, `rtk-err-cat`
is the only baseline we tested that does targeted summarization
rather than naive truncation.

So the correct one-line summary is:

> **Stand-alone, RTK underperforms simpler methods on CI diagnosis.
> As a component inside a hybrid router for oversized logs, RTK is
> in the winning configuration.**

## What would actually fix the stand-alone case

If RTK wanted to optimize for "preserve enough evidence for LLM
root-cause diagnosis" (as opposed to "minimize tokens"), the
changes implied by this analysis are:

1. **Replace the optimization target.** "Compression ratio" is the
   wrong loss for downstream diagnosis. A downstream-task metric
   (signal-recall, root-cause-preservation) is needed for tuning.
2. **Protect lines matching CI failure patterns from dedup.** Even
   a small allowlist (`FAILED`, `Error:`, `panic:`, `error\[E\d+\]`,
   `Traceback`, `AssertionError`, exit-code lines) would prevent
   the dedup pass from merging signal-bearing lines into "similar
   stack frame" clusters.
3. **Add a positional prior.** Weight the last N% of the log
   higher in the compression budget. CI failure summaries cluster
   at the end; flat per-line treatment fights this structure.
4. **Expose a `--mode ci-diagnosis` (or similar).** RTK's current
   modes (`read` / `log` / `err cat`) are tuned for different
   surfaces. A CI-specific mode could ship the above three changes
   together.

I don't think RTK's existing modes are *bad* — they're optimized for
realtime wrapping of developer commands (`rtk cargo test`,
`rtk git log`), where compression ratio is the right objective.
This analysis just argues that CI failure diagnosis is a different
enough task that it warrants a different mode.

## Caveats on this analysis

1. **35 cases.** Per-case variance can shift overall means by ±0.05.
   The qualitative direction (RTK modes < grep < hybrids) is stable
   across all 3 model families, but exact rankings between adjacent
   methods may not be.
2. **Three model families.** Adding GPT-4o / Gemini / Llama could
   change absolute scores, but the inductive-bias argument is about
   the *task structure*, not the model — adding more model families
   should preserve the direction.
3. **No re-run of RTK with custom configs.** The benchmark uses
   stock RTK invocations (no custom rules, no `.rtkrc` tuning). A
   CI-tuned RTK config could close some of this gap; we did not
   test that.
4. **Mock-summary in the leaderboard.** Resolved in v1.1. The
   v1.0/early-v1.1 board used `llm-summary-v1-mock` (deterministic
   stub) as the LLM-summary class representative, which was unfair.
   v1.1 backfilled the real Haiku map-reduce summarizer
   (`llm-summary-v1-haiku`) to all 35 cases × 4 diagnosers — it
   lands at rank 4 overall (0.632, +0.30 over the mock), confirming
   the LLM-summary class is mid-pack, not bottom-4. See the
   [v1.1 promotion note](../leaderboard.html#v11--promoting-llm-summary-v1-haiku-to-the-headline)
   on the leaderboard. The mock remains visible as a legacy entry.

## See also

- [LogDx-CI homepage](https://logdx-bench.github.io/)
- [Full leaderboard](https://logdx-bench.github.io/leaderboard.html)
- [RTK as a method (reference doc)](../methods/rtk.md)
- [Technical report §3 (formal results)](../../reports/technical_report.md)
- [RTK on GitHub](https://github.com/rtk-ai/rtk)
