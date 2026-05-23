# E10 Phase 3 (Partial) — v1.3 method generalization to the v2 corpus

> **Status:** partial / 8 v2 cases (Phase 2 paused at 8/34, not the
> 10-case checkpoint). Signal-recall only; no real debugger run yet.
> Mock LLM summary only. Treat as directional, not statistical.
>
> Source: `tools/run_baseline.py` + `tools/run_rtk_baseline.py` +
> `tools/run_llm_summary_baseline.py` (mock provider) +
> `tools/run_hybrid_baseline.py` (config:
> `configs/hybrids/hybrid-grep-4k-rtk-err-cat-v1.json`) +
> `tools/evaluate_signal_recall.py`. Run on 2026-05-07.

## TL;DR

The v1.3-tuned hybrid (`hybrid-grep-4k-rtk-err-cat-v1`) is the
**worst-generalizing** of the 8 locked v1.3 methods on the v2 corpus.
It loses 0.34 macro signal-recall and 0.50 macro critical-signal-recall
moving from v1.3 to v2 — substantially more than any single-method
baseline.

```text
                                   v1.3      v2     Δ      v1.3      v2     Δ
method                             sig    sig    sig     crit    crit    crit
raw                              1.0000 1.0000 +0.000   1.0000  1.0000 +0.000
rtk-read                         1.0000 1.0000 +0.000   1.0000  1.0000 +0.000
grep                             0.8756 0.8286 -0.047   0.9028  0.7167 -0.186
tail                             0.8549 0.7777 -0.077   0.8833  0.7084 -0.175
rtk-err-cat                      0.5377 0.4556 -0.082   0.5495  0.4445 -0.105
llm-summary-v1-mock              0.5278 0.4611 -0.067   0.5517  0.2278 -0.324
rtk-log                          0.2874 0.2365 -0.051   0.3239  0.1389 -0.185
hybrid-grep-4k-rtk-err-cat-v1    0.8237 0.4841 -0.340   0.8894  0.3944 -0.495   ← largest drop
```

`raw` and `rtk-read` are pinned at 1.0 by definition (they keep the
full log). Among the rest, **grep is the smallest signal-recall
drop**, and **hybrid is the largest** by a factor of 4–7×.

This **directly confirms the §9 limitation in
`docs/reports/cilogbench_v1_3_limitations.md`**: the 4k-token
threshold inside `hybrid-grep-4k-rtk-err-cat-v1` was tuned on the
same v1.3 corpus that scored it. The independent v2 corpus shows
the hybrid does not generalize.

## Why hybrid fails

Hybrid's per-case routing on the 8 v2 cases:

```text
v2 case                                   route          hybrid (sig/crit)  grep (sig/crit)
moby-buildx-bake-v2-001                   rtk-err-cat    0.83 / 0.67        1.00 / 1.00     ← grep wins
pip-pytest-network-github-v2-001          rtk-err-cat    0.57 / 1.00        1.00 / 1.00     ← grep wins
pnpm-jest-config-v2-001                   rtk-err-cat    0.20 / 0.00        0.80 / 0.50     ← grep wins big
biome-pnpm-not-found-v2-001               rtk-err-cat    0.50 / 0.00        1.00 / 1.00     ← grep wins big
gh-cli-go-test-prompter-v2-001            grep           0.33 / 0.00        0.33 / 0.00     ← both lose (Go FAIL)
pandas-cpp-xsimd-neon64-v2-001            rtk-err-cat    0.71 / 0.67        1.00 / 1.00     ← grep wins
pnpm-audit-vuln-ip-address-v2-001         grep           0.29 / 0.00        0.29 / 0.00     ← both lose (audit table)
prettier-jest-snapshot-babel-v2-001       rtk-err-cat    0.33 / 0.50        1.00 / 1.00     ← grep wins big
```

- **6 of 8** v2 cases routed to `rtk-err-cat`.
- **5 of those 6** would have done strictly better on grep, often
  drastically (e.g. prettier snapshot: 0.33 → 1.00, biome: 0.50 → 1.00).
- The remaining 2 cases (`gh-cli-go-test-prompter` and
  `pnpm-audit-vuln-ip-address`) both lose under grep too — the
  failure surfaces don't match grep's regex `error|failed|...|##[error]`:
  - Go test output uses `--- FAIL:` (uppercase, no `failed`).
  - pnpm audit's vulnerability output uses `vulnerabilities found`,
    not any of grep's failure keywords.

So the v2 corpus reveals **two distinct generalization failures**:

1. **Hybrid threshold misroutes.** The 4k-token threshold pushes
   medium-large logs into rtk-err-cat, where RTK's category extractor
   often misses the actual failure surface. Grep — even imperfect
   grep — beats rtk-err-cat on these.
2. **Grep regex blindspots.** Even with full context, grep's v1.3-era
   regex doesn't cover Go's `--- FAIL:` marker or pnpm-audit's
   ascii_table format. (RTK has the same blindspots, plus more.)

`raw` and `rtk-read` pass everything through and so retain 100%, but
that defeats the purpose (no compression).

## Implications for the v1.3 headline

The v1.3 one-pager headline:
> "matched grep on quality at ~⅓ token cost"

needs an explicit caveat for v2:

> The v1.3 corpus was used to tune the hybrid threshold; on a fresh
> 8-case v2 corpus, the same hybrid loses 0.34 signal-recall vs the
> identical grep baseline. The cost advantage is real; the quality
> match does not survive distribution shift to v2.

This is the most important finding of E10 so far, and it shows up
**purely from signal-recall** — without needing the calibrated sv1.1
score or a real debugger run. A real-debugger Phase 3.5/4 (running
`real-debugger-v2` on the v2 corpus) would test whether the
diagnosis-quality story tracks the signal-recall story or not.

## Caveats

1. **8 cases.** This is half of v1.3's 16, less than the planned
   34/50. Variance per case is high. The headline finding is
   directionally clear (hybrid is the worst by a wide margin) but
   should be confirmed at 30+ cases before quoting it as definitive.
2. **Signal-recall is a deterministic proxy** for diagnosis quality.
   `diagnosis_score_v1_1` is the calibrated metric and requires
   running a real debugger; that hasn't been done for v2 yet.
3. **Mock LLM summary only.** `llm-summary-v1-mock` is a deterministic
   stand-in, not the real Haiku summarizer. The real-summary numbers
   from v1.3's E3 are not directly comparable.
4. **Ground-truth was AI-drafted then human-verified.** Each v2
   ground_truth.json was drafted by Opus 4.7 reading raw.log, then
   verified by the project author item-by-item via a checklist (per
   the "AI-draft + human-verify" pattern from E10 Phase 2 plan §
   "Strategic decision"). This is the same pattern as E9's review
   and is plan-compliant per "model-generated ground truth unless
   those labels are later human verified." However, it is **not**
   independent human annotation; project-bias caveats from
   limitations §2.1 still apply.
5. **v2 corpus is heavy on flaky/network failures.** 3 of 8 cases
   are `flaky_or_transient=true`, all 3 with github.com 502s as the
   underlying root cause. This may bias results toward methods that
   recognize HTTP error patterns. Larger v2 will dilute this.
6. **The hybrid is still rank #1 by token cost.** The dramatic
   reduction is real (~95% on most v2 cases). The cost vs quality
   tradeoff has shifted: on v2, hybrid pays the same low token cost
   as on v1.3, but for substantially worse signal preservation.

## Recommended follow-ups (in priority order)

1. **Run `real-debugger-v2` (Sonnet 4.6) on the 8 v2 cases × 8
   methods.** Produces sv1.1 numbers comparable to v1.3's headline.
   This is the canonical generalization metric.
2. **Continue Phase 2 to 10–34 cases.** Specifically target the
   two grep-blindspot patterns (Go `--- FAIL:` and audit-table) plus
   timeout/OOM and matrix/monorepo, to harden these findings.
3. **Inspect the hybrid threshold.** v1.3 picked 4k tokens via
   E4's offline budget sweep on the v1.3 corpus. A v2-tuned
   threshold would likely be different. Resist re-tuning before v2
   has 30+ cases — re-tuning on a 8-case subset would re-introduce
   the same selection-by-method risk that v2 is meant to expose.
4. **Extend grep regex.** Adding `\bFAIL\b`, `\bvulnerabilities\b`,
   and a few more failure keywords would close two of the v2
   blindspots. But: any regex extension should be motivated by
   collected cases, not speculative.

## Per-method run summary

```text
v1.3 splits (legacy: dev=5, holdout=5, stress=6, total=16)
v2 splits (new_v2: v2/dev=3, v2/holdout=5, total=8)

For each method × split, the eval is in:
    results/<split>/eval_<method>.json    (per-case + macros)
    results/<split>/<method>.jsonl        (manifest)
    results/<split>/<method>/<case>.txt   (the context text)

Hybrid routing decisions:
    results/<split>/hybrid-grep-4k-rtk-err-cat-v1.routes.jsonl
```

## What this report does NOT support

- Any claim about diagnosis quality on v2 (no debugger run yet).
- Any claim about the v1.3 hybrid being "wrong" on v1.3 — it scored
  what it scored. The finding is that it doesn't generalize, not
  that v1.3 numbers are invalid.
- Any leaderboard ranking. The 8-case v2 corpus is a direction
  indicator, not a benchmark.

## Where to next

Either:
- **(A) Run real-debugger-v2 on v2** — produces sv1.1 numbers,
  confirms whether the signal-recall story tracks diagnosis quality.
- **(B) Resume Phase 2 collection** — push toward 30+ v2 cases to
  harden the headline. Specifically target Go test failures, audit
  outputs, timeout/OOM, matrix/monorepo.
- **(C) Both, in sequence** — typically the right answer if budget
  allows.
