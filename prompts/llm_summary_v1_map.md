# llm_summary_v1 / MAP

You are reading one chunk of a failed CI log. Each line is prefixed with
its 1-indexed line number like `L000123:`. The chunk may end mid-incident.

Extract ONLY evidence that is relevant to diagnosing the CI failure.
Prefer exact strings from the log over paraphrases. Do NOT invent
information that is not present.

For each relevant item, emit a bullet that keeps the original
tool-printed text verbatim inside backticks, plus the log line numbers
it came from, in this form:

```
- [CATEGORY] `<exact text from the log>`  (lines: L000123)
```

Use these categories (keep the bracket notation; case-sensitive):

```
[FAILED_TEST]           — failing test identifier (FAILED, --- FAIL, ✘, etc.)
[ASSERTION]             — assertion, expectation, or comparison message
[EXCEPTION]             — raised exception / panic / fatal error line
[COMPILE_ERROR]         — compiler / type checker / linter diagnostic
[STACK_LOCATION]        — file:line (or file + line) appearing in stack / traceback
[EXIT_CODE]             — tool exit code, including GHA ##[error] lines
[COMMAND]               — command the job ran (yarn ..., npm ..., cargo ..., python ...)
[PACKAGE]               — dependency install error or version mismatch
[GHA_ERROR]             — ##[error] / ##[warning] GitHub Actions markers
[REMEDIATION]           — tool-printed fix suggestion (e.g. "Please run yarn prettier-all")
[STEP_NAME]             — section / step / group header naming the failing phase
[UNCERTAINTY]           — genuine ambiguity about what the log shows
```

Rules:

1. **Keep exact strings.** Preserve file paths, test names, line
   numbers, error messages, and exit codes character-for-character
   inside backticks. Do not normalize or summarize them.
2. **One concept per bullet.** If a single log line has two distinct
   signals, emit two bullets.
3. **Be conservative.** If a line is not clearly relevant to the
   failure, skip it. Noise that costs us recall is better than noise
   that dilutes the summary.
4. **No invented context.** Do not add interpretation beyond what the
   log literally says. If something is unclear, use `[UNCERTAINTY]`.
5. **No headers or prose.** Output only the bulleted list.
6. **If nothing relevant is in this chunk**, output exactly one line:

```
NO_RELEVANT_FAILURE_SIGNAL
```

## Input chunk

The next message contains the log chunk.
