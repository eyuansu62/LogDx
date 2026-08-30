# LogDx v1.3 modern-model study

## Recommendation

**PR, subject to human review; do not publish automatically.** Aggregate
reducer rankings remained similar to the averaged historical panel under the
compatibility limits. Native mode accepted more raw cases and improved the
full-corpus score. Reduction remained economically useful on this corpus.
The one tested Drain3 configuration lost specific diagnostic evidence.

These are composite benchmark scores, not percentages of correctly diagnosed
failures. The experiment does not isolate context size from other serving
changes or establish performance on a one-million-token input.

## Scope and provenance

The study used source SHA `fc957f0d0d0082019606cc20b8fb545683a03b44`
and frozen v1.2 SHA `99591c1471118c95155976346df72f520a05f100`.
It did not change the 35-case corpus or frozen historical results. The Copilot
CLI version was `1.0.82`; the native SDK was `1.0.11` with bundled runtime
`1.0.79`; Python was `3.14.6`. The compatibility adapter SHA-256 was
`a37d5d679110ef731a856ca5e77080715cf6f82e330c7a8896e0332869b8243a`.
The native adapter SHA-256 was
`20143deadb8e3e22cda32c4e86ca19be802af9e8c5b09620953aa597cc834ccc`.

Luna, Terra, and Sol each ran 35 cases over eight methods and six split groups.
Each produced 280 rows: 253 proven model calls and 27 explicit
unsupported-context results. Every successful row resolved to its requested
model. GPT-5 Mini was excluded after five probes could not prove resolved
identity and wrote no results.

## Modern-model transfer

The historical rank uses the mean per-case result from frozen
`real-debugger-v1`, `real-debugger-v2`, and `real-debugger-v3`. Drain3 is not in
that panel, so Spearman uses seven shared methods.

| Model | Best method | Best score v1.1 | Historical rank rho | Calls / rows | Error rate |
|---|---|---:|---:|---:|---:|
| Luna | hybrid RTK-tail v3 | 0.6478 | 1.0000 | 253 / 280 | 0.0964 |
| Terra | hybrid RTK-tail v3 | 0.6635 | 0.9286 | 253 / 280 | 0.0964 |
| Sol | hybrid RTK-tail v3 | 0.6746 | 0.9643 | 253 / 280 | 0.0964 |

Across all three models, no established reducer beat the hybrid RTK-tail v3
with a paired 95% interval wholly above zero. The apparent differences among
the hybrid, LLM summary, grep, and tail usually overlap zero. Do not declare a
winner among those methods.

The ranking claim is conditional on the 35-case corpus and compatibility
limits. On the 17 raw cases accepted by both modes, compatibility-versus-pooled
historical rank correlations fall to `0.5714`, `0.4643`, and `0.3214` for Luna,
Terra, and Sol. This exploratory subset check is not a replacement estimate;
it shows that the full-corpus ordering is sensitive to case selection and
capacity failures. Do not generalize it to model capability alone.

| Method | Mean score v1.1 | Mean input tokens per call | Error rate | Recorded downstream cost |
|---|---:|---:|---:|---:|
| hybrid RTK-tail v3 | 0.6620 | 37,927 | 0.0000 | $7.2978 |
| hybrid tail v2 | 0.6445 | 37,356 | 0.0000 | $7.1935 |
| LLM summary | 0.6420 | 6,262 | 0.0000 | $1.4976 |
| grep | 0.6185 | 39,608 | 0.0857 | $6.9644 |
| tail | 0.6011 | 13,882 | 0.0000 | $2.8583 |
| Drain3 | 0.5903 | 42,131 | 0.1714 | $6.6877 |
| raw | 0.3513 | 45,871 | 0.5143 | $4.2991 |
| RTK | 0.1999 | 5,615 | 0.0000 | $1.2291 |

The LLM-summary label is the frozen reducer name. Luna, Terra, or Sol performed
the downstream diagnosis; GPT-5 Mini did not perform these v1.3 diagnosis
calls. Costs here cover downstream diagnosis only. They exclude preparation
of the frozen LLM summaries and local reducer computation. They are not an
end-to-end cost ranking of reduction pipelines. Input/output token means use
calls with recorded usage; score and error means include rejected rows.

## Per-model quality and operations

The quality columns below average all eight methods. Use the per-method JSON
files for method-level claims.

| Model | Score v1.1 | Confident error | Abstention | Critical recall | Valid quote | Mean input | Mean output | Successful model-call p50 / p95 | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Luna | 0.5306 | 0.0393 | 0.2071 | 0.5458 | 0.9322 | 26,900 | 377 | 3,776 / 6,630 ms | $1.8697 |
| Terra | 0.5422 | 0.0321 | 0.2429 | 0.5840 | 0.9288 | 26,900 | 352 | 3,859 / 6,634 ms | $18.0826 |
| Sol | 0.5433 | 0.0250 | 0.2679 | 0.5708 | 0.9732 | 26,898 | 420 | 4,746 / 9,463 ms | $18.0752 |

These latency values use 253 successful model calls per model. They exclude
adapter startup and rejected requests. Successful end-to-end p50/p95 values
are Luna `8,122 / 11,923 ms`, Terra `8,024 / 11,013 ms`, and Sol
`8,760 / 13,682 ms`. JSON artifacts also report rejected and all-row
end-to-end latency separately, with observation counts.

Total recorded usage was 20,416,605 prompt tokens and 290,763 completion
tokens. The observable token cost was `$38.02742265`. This converts Copilot's
recorded nano-AIU using GitHub's current token price table and USD 0.01 per AI
credit. Included plan credits can reduce the billed amount.

## Raw and native long context

Raw compatibility mode did not make reduction obsolete. Its mean score was
`0.3513`, and `51.43%` of raw rows exceeded the practical context boundary.
Each established reducer except RTK was significantly better than raw for at
least one model; the hybrid-v3 intervals versus raw were wholly above zero on
all three models.

The SDK advertised a 1,050,000-token context window and a 922,000-token prompt
limit for all three models. The adapter used a 921,000-token safe cap. It
proved the requested model at session start, model call, and usage reporting.
It also proved `long_context` mode and zero available or used tools.
The largest successful counted prompt was 693,398 tokens. Four cases per
model exceeded the safe cap. This is a native long-context corpus evaluation,
not a measured one-million-token-input test.

| Model | Native raw | Compat raw | Native minus compat raw, 95% CI | Hybrid v3 | Native minus hybrid v3, 95% CI | Errors | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Luna | 0.5859 | 0.3603 | +0.2257 [0.1126, 0.3424] | 0.6478 | -0.0619 [-0.1557, 0.0264] | 4/35 | $2.5840 |
| Terra | 0.6257 | 0.3500 | +0.2757 [0.1555, 0.4038] | 0.6635 | -0.0378 [-0.1466, 0.0588] | 4/35 | $22.9966 |
| Sol | 0.6350 | 0.3437 | +0.2913 [0.1681, 0.4199] | 0.6746 | -0.0395 [-0.1415, 0.0576] | 4/35 | $22.9886 |

Across all 35 cases, native raw significantly beat compatibility raw. Its
mean score was `0.6155`, compared with `0.6620` for hybrid v3. The
native-versus-hybrid intervals overlap zero, so the quality difference is not
established. Hybrid v3 had no provider errors and cost `$7.2978`; native raw
had a `0.1143` error rate and cost `$48.5692`. Four cases per model exceeded
the native cap. Hybrid had better input coverage; native recorded downstream
cost was about 6.7 times the hybrid cost for this model mix and price snapshot. This is not
proof that hybrid has better diagnosis quality, or a general reliability claim.

### Accepted-case comparisons

Compatibility raw accepted 17 cases; native raw accepted those 17 plus 14 more.
All of the positive full-corpus gain came from the 14 newly accepted cases.
On identical accepted raw inputs, the means were lower in native mode:

| Model | Compat raw, 17 cases | Native raw, same 17 | Native minus compat, 95% CI | Native raw, 14 newly accepted |
|---|---:|---:|---:|---:|
| Luna | 0.7417 | 0.6922 | -0.0495 [-0.0930, -0.0077] | 0.6242 |
| Terra | 0.7207 | 0.7025 | -0.0182 [-0.0468, 0.0086] | 0.7112 |
| Sol | 0.7077 | 0.6963 | -0.0114 [-0.0283, 0.0024] | 0.7421 |

On the 31 native-accepted cases, native/hybrid mean scores were
`0.6615/0.6667`, `0.7064/0.6619`, and `0.7170/0.6835`. Each paired interval
overlapped zero. The JSON artifacts include comparisons with compatibility
raw, hybrid, and tail for every subset, with exact case lists. Subsets were
added after review; their intervals are exploratory and unadjusted for
multiple comparisons. They do not establish equivalence or a new winner.

The user prompt construction is shared, but the SDK replaces the system
prompt with `Follow the user instruction exactly. Do not use tools.` The CLI
uses its serving system prompt. Runtime versions also differ (`1.0.79` versus
`1.0.82`). Thus the observed result is increased coverage and a higher
full-corpus score under a different serving setup, not an isolated causal
effect of context size. A matched SDK control is needed for that stronger claim.

### Native timing

All times below use the 31 successful calls per model. Model-call time and
adapter end-to-end time are different measurements and are never pooled.

| Model | Model-call p50 / p95 | End-to-end p50 / p95 |
|---|---:|---:|
| Luna | 4,367 / 8,077 ms | 9,105 / 13,328 ms |
| Terra | 4,458 / 9,676 ms | 9,911 / 14,933 ms |
| Sol | 7,087 / 15,345 ms | 11,752 / 20,473 ms |

Native canonical usage was 17,003,217 prompt tokens and 30,227 completion
tokens. Compatibility plus native canonical cost was `$86.59661195`. The
earlier `$87.27` execution estimate is unverified, not an account charge:
probe/retry usage is incomplete, including one malformed Luna response.

## Drain3

Drain3 `0.9.11` used one corpus-wide configuration. Its two output-tree hashes
were identical. Six privacy scans found zero hits.

- Required-signal recall: `0.8750`
- Critical-signal recall: `0.8632`
- Byte reduction: `0.5338`
- Missed required signals: 35
- Missed critical signals: 22

Its downstream score was significantly above raw for Luna, Terra, and Sol.
The paired 95% intervals for Drain3 minus raw were `[0.1161, 0.3511]`,
`[0.1238, 0.3733]`, and `[0.1270, 0.3672]`. However, its intervals against
hybrid-v3 overlapped zero, while its mean quality was lower, its input was
larger, and its error rate was higher than tail. Drain3 did not create a Pareto
point in the pooled recorded downstream score/cost comparison. Exact test
names, version bounds, counts, and commands were common losses after values
became `<*>`. These results concern this pinned template-only configuration,
not all uses of Drain3. They do not establish statistically worse diagnosis
quality than hybrid. For example, the Prettier template retains
`- Unexpected token <*>` but loses the annotated `(1:8)` location.

## Limits

- Compatibility CLI and native SDK differ in system prompt and runtime.
  Comparison with the frozen direct-API panel is also approximate.
- Near-limit contexts can fail after prompt overhead even below the nominal
  character cap. Those cases are explicit abstentions with their effective cap.
- One uncached Terra sample repeat retained the same category and score. This
  small check cannot measure full stochastic variance.
- Sol pricing was promotional on the execution date and can change.
- Four raw cases exceeded the 921,000-token safe prompt cap for every model.
- The SDK transport differs from the compatibility CLI transport and from the
  frozen direct-API panel.
- One malformed Luna response was retried. Its failed-call usage was not
  observable, so the actual execution cost is approximate.
- Case bootstrap intervals cover variation across these 35 cases, not full
  run-to-run model variation. Overlapping zero does not establish equivalence.

## Artifacts

The exact per-model metrics, paired 10,000-sample bootstrap intervals, runtime,
tokens, and error rates are in `results/v1_3/*-compat-statistics.json` and
`results/v1_3/*-native-long-statistics.json`. The machine-readable decision is
in `results/v1_3/study_summary.json`.
