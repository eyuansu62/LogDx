# llm_summary_v1 / REDUCE

You will receive the concatenated outputs of the MAP stage, one block
per chunk, ordered by chunk index. Your job is to produce a compact,
markdown-formatted debugging context that another engineer or coding
agent can read to diagnose the failure.

Preserve exact names, file paths, test names, line numbers, error
strings, and quoted evidence whenever available. Do not replace them
with vague paraphrases. If two bullets refer to the same underlying
line, keep only one.

## Output format (exactly these section headers, in this order)

```
# CI Failure Summary

## Primary Failure

## Critical Evidence

## Failed Tests / Checks

## Relevant Files and Locations

## Commands and Exit Codes

## Possible Root Cause

## Uncertainties / Missing Context
```

Section guidance:

- **Primary Failure.** One short paragraph naming the tool and the
  failure shape (e.g. "pytest collection errors in 52 files, all
  caused by a NumPy DeprecationWarning that is raised as an error").
  Cite the exact tool name as it appears in the log.
- **Critical Evidence.** A short list of exact strings that a human
  reviewer would most want to see. Keep them in backticks. Include the
  log line numbers (e.g. `L001282`) so a reader can find them again.
- **Failed Tests / Checks.** Bullet the exact test identifiers or
  check names. No paraphrasing.
- **Relevant Files and Locations.** `path/to/file.py:LINE` when
  available, otherwise just the file.
- **Commands and Exit Codes.** Commands the CI job ran that relate
  to the failure, plus exit codes (GHA `##[error]` markers count).
- **Possible Root Cause.** Two sentences max. Stay inside what the log
  supports. If the evidence is ambiguous, say so.
- **Uncertainties / Missing Context.** Anything the log does not
  resolve (version drift, hidden upstream cause, masked secret, etc.).

Rules:

1. **No section may be omitted**, even if empty. Write
   `- _(none identified)_` on its own bullet when a section has no
   content supported by the MAP output.
2. **Do not invent content.** If the MAP output did not mention
   something, the REDUCE output cannot either.
3. **Keep evidence strings verbatim** inside backticks. Do not
   normalize quotes, whitespace, or case.
4. **Be concise.** Target under 12,000 characters total.

## Input

The next message contains the MAP outputs concatenated in chunk order.
