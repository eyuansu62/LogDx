# Annotation Guide

How to write a correct `ground_truth.json` for a case.

This project's credibility hinges on the ground truth being **faithful to
the log** and **not tuned to any particular method**. A ground truth that
drifts toward any specific baseline (e.g., grep's keyword set, a hybrid
router's selection rule, or a future LLM method's bias) silently
converts the benchmark into a confirmation exercise.

## Core rules

1. **Use only evidence visible in `raw.log`.** Do not infer details
   (version numbers, upstream PRs, runner OS) that are not printed in
   the log itself.

2. **Do not tune ground truth based on any method's output.** Write the
   answer from the raw log alone. Methods are scored against this
   answer; scoring against itself is circular.

3. **Prefer narrow evidence spans over huge ranges.** An
   `evidence_span` is the minimum range a careful reader would need to
   reconstruct the answer. If you find yourself covering 500 lines to
   explain one failure, pick the 10-20 that carry the load.

4. **Mark the minimum set of critical signals.** `required_signals` is
   the floor, not the wish list — something a method *must* produce for
   the case to count as preserved.

5. **Use importance levels consistently:**
   - `critical` — removing this makes root-cause identification impossible.
     Typical: the first failing test, the exception type + message, the
     exit-code marker, the dominant error category header.
   - `important` — helpful for correct scope but not strictly required.
     Typical: secondary error class counts, the harness panic frame,
     downstream wrapper warnings.
   - `optional` — context that aids readability but can be dropped.
     Typical: step names, workflow names, setup-step location.

6. **Keep `root_cause.summary` short and concrete.** 1–3 sentences.
   Name the specific tool + file/test + observed behavior. Do not
   speculate on fixes beyond what the log literally suggests.

7. **Write `fix_suggestion` only if the log clearly supports it.**
   If the log says `Please run yarn prettier-all`, the fix suggestion
   is to run that command. If the log merely says a test failed, the
   fix suggestion belongs in `expected_diagnosis.must_mention` as a
   diagnostic direction, not a prescription.

8. **Line numbers are 1-indexed and inclusive.** `[start, end]` with
   `start <= end`. `[42, 42]` means exactly line 42. The validator
   enforces this and will reject 0-indexed ranges.

9. **`must_mention` and `must_not_claim` are concrete substrings or
   short phrases**, not sentences. Methods will be scored for whether
   a diagnosis produced against that method's output references these
   phrases. Think: what do you want to *see* a human writer say, and
   what would you *flag as wrong*?

10. **One file, one truth.** If the same fact appears twice in the log,
    cite the first clean occurrence in `evidence_lines` rather than all
    repetitions. Redundancy in evidence is not a feature.

## Suggested workflow

Given a `raw.log`:

1. **Read the tail first** (last ~200 lines). The `##[error]` markers,
   `exit code`, and post-job summary usually reveal the failure shape
   before you know its cause.

2. **Identify the anchor** — the one section the reader's attention
   should go to. This is almost never `_preamble` or step-setup. Note
   its line range.

3. **Write `root_cause.summary` first**, before annotating individual
   signals. This forces you to articulate the answer before hunting for
   evidence to support it.

4. **Annotate `required_signals` working backward from the summary.**
   For each claim in the summary, find the smallest line range that
   evidences it. That becomes a critical signal.

5. **Fill `evidence_spans` last**, grouping related critical signals
   into coherent ranges. Ranges can overlap signals; that's fine.

6. **Run the validator.** Fix any line-range errors (off-by-one is the
   most common). Re-read your summary against the evidence you cited —
   if the cited lines don't actually support the summary, the summary
   is speculation.

## Aliases (optional, rare)

Some signals have a canonical full form and a shorter conventional form
that *also appears in the raw log*. Example: a trybuild test name
`tests-build::macros compile_fail_full` is often referenced elsewhere
simply as `compile_fail_full`. You may add an `aliases` array to the
signal so that a method preserving only the shorter form still counts
as passing:

```json
{
  "type": "failed_test",
  "value": "tests-build::macros compile_fail_full",
  "aliases": ["compile_fail_full"],
  "importance": "critical",
  "evidence_lines": [[2759, 2759]]
}
```

Rules:

- Aliases must be **justified by the raw log**. If `compile_fail_full`
  appears on its own in raw.log, it is a legal alias. If it does not,
  do not invent one.
- **Do not add aliases after looking at a specific method's output.**
  The benchmark scores methods against ground truth; tuning ground
  truth to help a method is the one thing that invalidates the loop.
- Keep aliases sparse. Default to zero aliases per signal; add one only
  when a canonical short form is clearly present.

## Common mistakes

- **Citing the short test summary as the ONLY evidence for a pytest
  failure.** The summary is useful, but the traceback or assertion
  message is usually where the *cause* lives. Cite both.
- **Treating repeated errors as separate signals.** If the same
  DeprecationWarning fires 40 times, that's 1 signal type, not 40.
  Cite the first occurrence.
- **Over-specifying `relevant_files`.** Only list files that a human
  fixing the bug would need to touch. Stack-trace spelunking files
  (standard library, framework internals) don't belong here.
- **Leaving `must_not_claim` empty or vague.** Good negative
  constraints surface the failure modes you've seen methods hallucinate:
  e.g., "network failure" when the real cause is a formatting issue.
- **Evidence lines that exceed `line_count`.** Usually caused by
  editing `case.json`'s count without re-running `wc -l`. Let the
  validator catch this.
