## Stress case selection (M9)

The `cases/stress/` split is intentionally adversarial — it should expose
distribution dependencies that `cases/dev/` alone cannot reveal.

### Current picks (6 cases)

| case_id | failure_category | size | signal_pos | stress axis |
|---|---|---|---|---|
| `pytest-sklearn-stress-001` | `test_assertion` | large (5.7k lines, 1.1 MB) | late | large log + late evidence + test-progress noise |
| `pytest-sklearn-stress-002` | `test_assertion` | large (5.7k lines, 1.0 MB) | late | same doctest, different env (conda-forge vs pip); Jaccard 0.26 vs stress-001 |
| `prettier-react-stress-001` | `lint_error` (tag: `formatting_failure`) | small (228 lines) | late | `multi_failure=true` — two formatting violations, not one |
| `cleanup-k8s-stress-001` | `permission_or_secret` | small (83 lines) | late | gh 403 post-job cleanup, 3-line evidence in tail |
| `cleanup-tsc-stress-001` | `permission_or_secret` | small (83 lines) | late | same mechanism as k8s in a different repo (Jaccard 0.67, below 0.80 threshold) |
| `docbuild-hf-stress-001` | `github_actions_config` | small (40 lines) | middle | downstream gate reacting to an upstream job; requires cross-job reasoning (`requires_repo_context=true`, difficulty `hard`) |

### Why these six

Each case probes a specific weakness of the simpler methods:

1. **Large log + late evidence** (sklearn-001): `tail-200` has to reach line
   5648; `grep` will catch the `FAILED` keyword but may miss Expected/Got;
   `rtk-log` aggressively dedups pytest progress — will it keep the doctest
   block or collapse it?
2. **Distribution shift within category** (sklearn-002): same failing test
   in a different environment. A method that memorized the sklearn-001
   pattern should generalize; one that doesn't reveals brittleness.
3. **Multi-failure formatting** (prettier-react): the dev lint-react case
   has one offending file; this has two. A "first match wins" heuristic
   silently loses the second file.
4. **Repo generalization** (cleanup-k8s vs cleanup-tsc): identical cleanup
   mechanism, different repos. A method that works on k8s should also
   work on TypeScript.
5. **Cross-job reasoning** (docbuild-hf): the failing step is a **gate**
   reacting to an upstream `doc_build` outcome. The tiny log shows only
   the gate's `if/else/exit 1`. A diagnoser that stops at `exit 1`
   without reading the shell conditional misses the real upstream cause.
   This is the only `hard` case by `diagnosis_difficulty`.

### Why only 6 (and documentation of the cache limitation)

The repository has a cached set of 20 raw GHA logs from earlier
milestones. 5 are in `cases/dev/`, 5 in `cases/holdout/`, and the
remaining 10 are heavily near-duplicated by content (same
workflow/test/repo reruns, Jaccard frequently ≥ 0.7 with dev/holdout
cases). After excluding contamination candidates, 6 genuinely distinct
stress cases were available. The plan's **minimum acceptance** is 6,
the **preferred target** is 8–12. Adding more cases requires fetching
new GHA logs, which needs a `GITHUB_TOKEN` and a fetch pass that is
explicitly out of scope for M9.

The corpus is designed so the next corpus-expansion milestone can drop
in additional logs without reshuffling v1.1:

- Add a new case directory under `cases/stress/<new_case_id>/`.
- Rerun `build_split_manifest.py` and freeze a new protocol version
  (`cilogbench-v1.2` or `cilogbench-v2` depending on severity).

### Rules for adding new stress cases

1. **Real CI logs only.** No synthetic or hand-edited logs in the stress
   split. Use `cases/dev/` synthetic smoke tests (none exist yet) for
   tooling.
2. **Pass `check_holdout_contamination.py` against both dev and
   holdout.** Near-duplicates (Jaccard ≥ 0.80) are rejected.
3. **Maximize axis coverage first, case count second.** A 6-case stress
   split spanning 6 axes is more informative than a 20-case split that
   all belongs to one category.
4. **Annotate before running methods.** Same rule as holdout.
5. **Tag honestly.** `diagnosis_difficulty: easy` is OK. `diagnosis_difficulty:
   hard` should be justified in `notes`.

### Known gaps in the current 6

- No `docker_build` failure case. Would need to fetch a new log.
- No `timeout_or_oom` case.
- No `flaky_or_transient` case.
- No `huge` (>50k-line) log.
- No `scattered` signal-position case.

These gaps are recorded in `reports/experiments/split_balance.md` so future
corpus-expansion work can target them.
