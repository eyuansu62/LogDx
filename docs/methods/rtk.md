# RTK as a CILogBench method

[RTK (Rust Token Killer)](https://github.com/rtk-ai/rtk) is an external CLI
proxy that compresses command output before it reaches an LLM context. In
CILogBench it is treated as an **external baseline** — it is benchmarked
alongside raw/tail/grep, not cloned or wrapped.

## Methods included

CILogBench runs three RTK invocations as distinct methods. Each feeds the
case's `raw.log` to RTK and captures stdout as the context handed to a
future agent:

| method | command | purpose |
|---|---|---|
| `rtk-read` | `rtk read <raw.log>` | file-reading compression path |
| `rtk-log` | `rtk log <raw.log>` | log-specific dedup/filter path |
| `rtk-err-cat` | `rtk err cat <raw.log>` | errors-only filter over `cat` output |

We optionally may add `rtk-test-cat` (`rtk test cat <raw.log>`) as a
diagnostic; it is not part of M3 acceptance.

None of these is tuned for GitHub Actions logs. CILogBench exists to
measure whether they preserve the evidence an agent needs to identify a
root cause. Do not interpret numbers here as a judgement of RTK overall:
RTK's designed use case is realtime wrapping of developer commands
(`rtk cargo test`, `rtk git log`), not post-hoc CI log triage. These
methods probe the boundary where RTK's generic compression behaviour is
applied to something outside its core target.

## Why external, not embedded

- **Drift avoidance.** RTK is actively developed. CILogBench should not
  mirror a moving implementation. Shelling out to whatever version is on
  the developer's machine keeps the benchmark honest about what the
  tool actually does today.
- **Reproducibility via metadata.** Every RTK manifest row records the
  binary path, version, full argv, exit code, runtime in ms, and
  stderr path (if any) — enough to reconstruct the exact invocation.

## Installing RTK

On macOS:

```bash
brew install rtk
rtk --version    # expected: rtk 0.x.y
```

On Linux or other platforms, see <https://github.com/rtk-ai/rtk> for
official instructions. The RTK binary only needs to be on `PATH`; no
configuration is required.

If the binary lives elsewhere:

```bash
python tools/run_rtk_baseline.py --method rtk-log --split dev \
    --rtk-bin /path/to/rtk
```

## What CILogBench does NOT do with RTK

- **No `rtk init`.** RTK supports a hook system that automatically
  rewrites commands in the user's agent/shell. CILogBench avoids this
  to keep the benchmark run hermetic — every invocation is an explicit
  subprocess call with captured stdout.
- **No auto-install.** `tools/run_rtk_baseline.py` fails with a clear
  error if `rtk` is not on `PATH` (unless `--allow-missing` is passed).
- **No modification of the user's RTK config.** If you've customized
  `~/.config/rtk/config.toml`, that config will be respected; the
  benchmark does not rewrite it. Equally, RTK's telemetry defaults
  (opt-in) are untouched.
- **No fuzzy signal matching.** RTK outputs are scored with a
  strict substring check after ANSI strip + CRLF→LF normalization.
  The evaluator does not do semantic judgement; M3 is empirical, not
  model-graded.

## Why evidence-line coverage is `N/A` for RTK methods

Raw/tail/grep preserve original line numbers (`line_mapping_available=true`),
so the evaluator can check whether each ground-truth evidence line
appears in the method's output. RTK methods dedupe, re-group, and
rewrite content; the line numbering in an RTK stdout is no longer tied
to the raw log. `line_mapping_available` is set to `false` and
`evidence_span_coverage` is reported as `N/A` in the summary report and
`null` in the JSON. Treating it as `0.0` would conflate "not measurable"
with "missed all evidence" and penalize any tool that achieves
compression by reorganization.

Signal preservation for RTK methods is scored via:

1. **Primary value** — strict substring match of the signal's `value`
   field in the normalized (ANSI-stripped, CRLF→LF) context text.
2. **Aliases** — optional short forms listed in the signal, used only
   when the alias literally appears in the raw log. See
   `docs/annotation_guide.md`.
3. **File fallback** — for `stack_location` signals that carry only
   `file` (+optional `line`), a substring match on the filepath.

Each preserved signal records which path fired (`text_fallback`,
`alias`, or `file_fallback`) in `per_signal[*].preserved_via`.

## Debugging a single case

Handy when an RTK method produces surprising output for one case:

```bash
python tools/run_rtk_baseline.py --method rtk-log --split dev \
    --case-id cargo-tokio-001
```

This writes to `results/dev/rtk-log.debug.cargo-tokio-001.jsonl`
instead of overwriting the canonical manifest. You can then inspect:

```bash
cat results/dev/rtk-log/cargo-tokio-001.txt
cat results/dev/rtk-log/cargo-tokio-001.stderr.txt   # if non-empty
```

## Known caveats of these RTK methods on CI logs

- `rtk read` at its default level (`--level none`) passes the content
  through unmodified. It gives an RTK-flavoured upper bound for signal
  recall but achieves 0% reduction — useful as a sanity check, not as a
  compression method.
- `rtk log` is aggressive: it emits a short `Log Summary` block and a
  dedup-clustered list. Expect very high reduction and low recall on CI
  logs that don't match RTK's expected log format.
- `rtk err cat` behaves close to a smart error-keyword filter. It can
  miss explanatory lines that lack failure keywords (e.g. Prettier's
  "Please run yarn prettier-all" recommendation).
