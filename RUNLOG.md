# LogDx v1.3 execution runlog

Date: 2026-08-30

## Provenance

- Current source SHA: `fc957f0d0d0082019606cc20b8fb545683a03b44`
- Frozen v1.2 SHA: `99591c1471118c95155976346df72f520a05f100`
- Work branch: `cmongan/logdx-v1.3-modern-model-study`
- Copilot CLI: `1.0.82`
- Copilot SDK: `1.0.11` with bundled runtime `1.0.79`
- Python: `3.14.6`
- Corpus/prompt/schema/protocol composite fingerprint:
  `c76d91c815e21448b017600c14419c47fbebfe7d437e6f4d2cb69e1d93576967`
- Debugger prompt SHA-256:
  `ecffdf03c99a91b0f8f75e086720d9fb8db96af0d9dae5285baf679c9c9d28de`
- Diagnosis schema SHA-256:
  `7c56065ceb9c6b50f3abe1a6ed6e90ade3f611dc2e84879e45671255cf270112`
- Compatibility adapter SHA-256:
  `a37d5d679110ef731a856ca5e77080715cf6f82e330c7a8896e0332869b8243a`
- Native SDK adapter SHA-256:
  `20143deadb8e3e22cda32c4e86ca19be802af9e8c5b09620953aa597cc834ccc`

## Baseline gates

Before the change, the 35-case corpus fingerprint was unchanged. The exact
cache suite passed 157 tests. The hybrid suite passed 10 tests. All three
diagnosis validators passed. The protocol lock passed with 27 hashes and 35
cases.

## Implementation decisions

- The generic Copilot shim denies all tools and isolates Copilot state.
- Compatibility mode uses noninteractive JSON event output.
- Native mode uses the Copilot SDK JSON-RPC transport. It sends the prompt over
  stdin and avoids macOS `ARG_MAX`, which is `1048576` bytes.
- Model identity, reasoning settings, context mode/cap, prompt, shim, config,
  and reduced context are part of cache validation or identity.
- Drain3 is optional and pinned to `0.9.11`. One corpus-wide configuration is
  used for all cases.
- Runs were serialized after the workspace preflight reported memory pressure.

## Model identity

Copilot advertised `gpt-5-mini`, `gpt-5.6-luna`, `gpt-5.6-terra`, and
`gpt-5.6-sol`. Compatibility calls proved the requested and resolved identity
for Luna, Terra, and Sol on every successful call. Each model produced 280
rows: 35 cases times eight context methods. There were 253 proven model calls
and 27 explicit unsupported-context rows per model.

GPT-5 Mini was excluded. Five probes returned no resolved-model evidence. The
runner rejected them with `FAIL_PROVENANCE` and wrote no Mini result.

An earlier ACP prototype changed the active model after session creation and
was rejected. The SDK adapter instead proves the selected model at session
start, the model used for the call, the `long_context` tier, the 922,000-token
prompt limit, usage-model identity, and zero tool use. Each native model
produced 35 raw rows: 31 proven calls and four explicit over-cap results.

## Context boundary

The normal compatibility cap was 480,000 context characters. Oversized
contexts were rejected. Two near-limit contexts made the CLI return
no usable response after prompt overhead. They were rerun with a cap one
character below the observed context size so the artifact records an explicit
`unsupported_context_too_large` abstention. The affected caps are stored in
each row. No silent empty response was accepted.

## Matrix execution

- Models: Luna, Terra, Sol
- Methods: `rtk-log`, `tail`, `grep`, both canonical hybrids,
  `llm-summary-v1-gpt-5-mini`, `raw`, and `drain3-templates`
- Splits: dev, holdout, stress, v2/dev, v2/holdout, v2/stress
- Total rows: 840
- Proven calls: 759
- Explicit unsupported-context rows: 81
- Prompt tokens: 20,416,605
- Completion tokens: 290,763
- Observable token cost: `$38.02742265`

The cost uses Copilot's recorded `total_nano_aiu` and GitHub's documented
conversion. `100,000,000,000` nano-AIU equals USD 1 at the observed price
table. Included plan credits can change the amount charged to the account.

One Terra response was malformed JSON and one Sol call failed transiently.
Both retries reused valid cached calls and completed only the missing work.

## Native long-context panel

The SDK advertised a 1,050,000-token context window and a 922,000-token prompt
limit for Luna, Terra, and Sol. The adapter reserved 1,000 tokens and used a
921,000-token safe prompt cap.

| Model | Native raw score | Compat raw score | Native minus compat raw, 95% CI | Native minus hybrid v3, 95% CI | Errors | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Luna | 0.5859 | 0.3603 | +0.2257 [0.1126, 0.3424] | -0.0619 [-0.1557, 0.0264] | 4/35 | $2.5840 |
| Terra | 0.6257 | 0.3500 | +0.2757 [0.1555, 0.4038] | -0.0378 [-0.1466, 0.0588] | 4/35 | $22.9966 |
| Sol | 0.6350 | 0.3437 | +0.2913 [0.1681, 0.4199] | -0.0395 [-0.1415, 0.0576] | 4/35 | $22.9886 |

Native raw improved the full-corpus score through increased acceptance (31
versus 17 cases). Its mean score was `0.6155`. Reduction remained economically
useful on this corpus. Hybrid v3 had a
higher mean score of `0.6620`, no provider errors, and cost `$7.2978` across
the three models. The native-versus-hybrid quality intervals overlap zero, so
the quality difference is not statistically established. Four cases per
model still exceeded the safe native prompt cap.

The canonical native artifacts contain 17,003,217 prompt tokens, 30,227
completion tokens, and `$48.5691893` observable cost. Compatibility plus native
canonical artifacts total `$86.59661195`. The earlier `$87.27` execution
estimate is unverified because probe/retry usage is incomplete, including
one malformed Luna response. This is not a verified account charge. Reported
costs exclude frozen-summary preparation and local reducer computation.

## Stochastic check

The Terra `tail` / `pytest-pandas-001` smoke was run once, repeated from cache,
then repeated without cache. Both independent responses kept the same category
and `diagnosis_score_v1_1` of `0.580`. This is only a small variance check. It
does not show that model output is deterministic.

## Drain3

Drain3 generated all 35 case contexts. Six privacy scans found zero hits. Two
independent output-tree hashes were identical:
`3cd76754b775cd053827888292d75ec2e52f6da3fa0ad83df85b97a6e10243a3`.

Static mean required-signal recall was `0.8750`; critical-signal recall was
`0.8632`; byte reduction was `0.5338`. Drain3 missed 35 required signals,
including 22 critical signals. Across the three modern models its mean
diagnosis score was `0.5903`, below the two hybrids (`0.6620`, `0.6445`), the
LLM summary (`0.6420`), grep (`0.6185`), and tail (`0.6011`). Its mean input was
42,131 tokens and its provider-error rate was `0.1714`. It did not create a
new Pareto point.

## Decision

Recommendation: **PR**.

The aggregate reducer ordering remained similar to the averaged frozen
real-debugger-v1/v2/v3 panel under compatibility limits: Spearman rho was `1.0000` for Luna, `0.9286` for
Terra, and `0.9643` for Sol across seven shared methods. Drain3 also failed in
an informative way for this pinned configuration. Native mode increased raw
coverage; reduction retained an economic advantage on this corpus. These
descriptive results meet the PRD's PR/issue rule, subject to human review.

## Post-run methodology review and corrections

- All 945 diagnosis scores and 35 Drain3 static scores were independently
  rescored with zero differences. No model outputs or frozen data were changed.
- All positive native-versus-compatibility aggregate gain came from 14 newly
  accepted cases. Added same-17-case and native-accepted-31-case comparisons
  against compatibility raw, hybrid, and tail, including exact case lists.
- On the same 17 raw inputs, compatibility/native means were Luna
  `0.7417/0.6922`, Terra `0.7207/0.7025`, and Sol `0.7077/0.6963`.
- Exploratory historical-rank correlations on those 17 cases were `0.5714`,
  `0.4643`, and `0.3214`. Full-corpus rankings depend on capacity boundaries.
- The largest successful prompt was 693,398 tokens. No actual million-token
  input was evaluated. Native replaced the system prompt and used a different
  runtime version, so context size was not the only changed variable.
- Fixed latency aggregation: model-call time is separate from adapter
  end-to-end time, with successful, rejected, and all-row populations labelled.
  Previous mixed native Sol p50 was 5,261 ms; successful model-call p50 is
  7,087 ms and successful end-to-end p50 is 11,752 ms.
- Regenerated statistics offline. No new paid inference calls were made.

## Final verification after cloud-file recovery

macOS temporarily made repository files cloud-only, causing empty reads and
invalid Git/test results. Finder's `Keep Downloaded` was enabled for this
repository. Verification then found zero cloud-only files and both original
adapter SHA-256 values matched. No reset or content restoration was used.

- 157 cache tests, 10 hybrid tests, 29 Copilot/statistics tests, and three
  Drain3 tests passed (199 total).
- Provider-error, evaluation-manifest, diagnosis-context, corpus fingerprint,
  release-string, and v1.2 protocol-lock checks passed.
- All six statistics artifacts reproduced byte for byte in a temporary
  directory. Summary values, subset counts, and latency denominators agreed.
- Python compilation and `git diff --check` passed. Frozen tracked corpus,
  prompt, schema, protocol, and result files had no changes.

## Local packaging

After the study and methodology review, the user authorized a focused local
commit containing the implementation, tests, corrected report, proposed PR
text, and separate v1.3 artifacts. The upstream checkout base SHA above remains
the experiment's reference point; it is not the packaging commit SHA.

The staged package contains 1,221 files, mostly canonical saved experiment
artifacts. A high-signal credential scan found no matches. The full staged
whitespace check reports 11 trailing separators on empty Drain3 templates.
Those context bytes were preserved exactly because changing an evaluated
input would break provenance. The source/documentation whitespace check is
clean; the earlier unstaged check did not cover new artifact files.

No upstream PR, issue, push, or deployment was created. Hosted CI has not run.
