"""Main public API: evaluate(reducer, diagnoser) -> Result."""
from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

from .baselines import BASELINES, closest_baseline, render_table
from .corpus import Case, load_cases, find_repo_root
from .diagnoser import SUPPORTED_DIAGNOSERS, diagnose, preflight
from .scoring import macro, score_case

Reducer = Callable[[str], str]


@dataclass
class CaseResult:
    case_id: str
    split: str
    score: float | None                # diagnosis_score_v1_1
    category_match: float | None
    confident_error: bool
    reduced_chars: int


@dataclass
class Result:
    """Result of running evaluate(reducer, ...) on the LogDx-CI corpus."""

    score: float | None                # macro diagnosis_score_v1_1
    confident_error_rate: float
    chars_per_case: float              # mean reduced-context size (chars)
    diagnoser: str
    n_cases: int
    elapsed_sec: float
    per_case: dict[str, CaseResult] = field(default_factory=dict)

    def __post_init__(self):
        # tolerate dict-of-dict on deserialization
        if self.per_case and not isinstance(
            next(iter(self.per_case.values())), CaseResult
        ):
            self.per_case = {
                k: CaseResult(**v) for k, v in self.per_case.items()
            }

    def vs_closest_baseline(self) -> str:
        if self.score is None:
            return "(no score)"
        return closest_baseline(self.score)

    def summary(self) -> str:
        score_str = f"{self.score:.4f}" if self.score is not None else "—"
        lines = [
            f"LogDx-CI evaluation result",
            f"  diagnoser:           {self.diagnoser}",
            f"  cases evaluated:     {self.n_cases}",
            f"  diagnosis_score_v1_1: {score_str}",
            f"  confident_error_rate: {self.confident_error_rate:.4f}",
            f"  mean reduced chars:  {self.chars_per_case:,.0f}",
            f"  elapsed:             {self.elapsed_sec:.1f} sec",
            f"  closest baseline:    {self.vs_closest_baseline()}",
            "",
        ]
        if self.diagnoser == "stub-debugger-v1":
            lines.append(
                "Note: stub-debugger-v1 is a deterministic regex matcher "
                "for smoke tests; the comparison below is not apples-to-"
                "apples. Use diagnoser='real-debugger-v2' for scores "
                "comparable to the v1.2 leaderboard."
            )
            lines.append("")
        lines.append("Comparison vs LogDx-CI v1.2 reference baselines:")
        lines.append("")
        lines.append(render_table(self.score or 0.0, self.chars_per_case))
        return "\n".join(lines)

    def to_json(self, path: str | Path) -> None:
        data = asdict(self)
        Path(path).write_text(json.dumps(data, indent=2, default=str))


def evaluate(
    reducer: Reducer,
    diagnoser: str = "stub-debugger-v1",
    splits: list[str] | None = None,
    cache_dir: str | Path | None = "~/.logdx_ci_cache/diagnosis",
    api_key: str | None = None,
    corpus_root: str | Path | None = None,
    verbose: bool = True,
) -> Result:
    """Evaluate a log reducer on the LogDx-CI v1.2 corpus.

    Parameters
    ----------
    reducer : Callable[[str], str]
        Your reduction function. Takes the full raw log, returns reduced text.
    diagnoser : str
        Which diagnoser to use. V0 supports:
          - "stub-debugger-v1" (default; deterministic, no API key)
          - "real-debugger-v2" (Claude Sonnet 4.6 via Anthropic API)
    splits : list[str] | None
        Which corpus splits to evaluate. Default: all 6 (= 35 cases).
        Pass e.g. ["v2/dev"] for a fast 3-case sanity check.
    cache_dir : str | Path | None
        Where to cache diagnosis results. Same reducer output → cache hit
        (free, no re-bill). Pass None to disable caching.
    api_key : str | None
        Provider API key. Defaults to ANTHROPIC_API_KEY env var.
    corpus_root : str | Path | None
        Path to the LogDx repo (must contain `cases/` + `tools/`).
        Default: auto-discover by walking up from cwd.
    verbose : bool
        If True, print progress to stdout.

    Returns
    -------
    Result with .score, .confident_error_rate, .summary(), .per_case.

    Example
    -------
    >>> import logdx_ci
    >>> def my_reducer(log: str) -> str: return log[-2000:]
    >>> r = logdx_ci.evaluate(my_reducer)
    >>> print(r.summary())
    """
    if diagnoser not in SUPPORTED_DIAGNOSERS:
        raise ValueError(
            f"Unknown diagnoser {diagnoser!r}. "
            f"V0 supports: {SUPPORTED_DIAGNOSERS}"
        )
    preflight(diagnoser)

    root = Path(corpus_root).expanduser() if corpus_root else find_repo_root()
    cases = load_cases(splits=splits, corpus_root=root)
    if verbose:
        print(
            f"[logdx-ci] evaluating {len(cases)} case(s) with diagnoser="
            f"{diagnoser!r}",
            file=sys.stderr,
        )

    per_case: dict[str, CaseResult] = {}
    diag_scores: list[float | None] = []
    cat_match: list[float | None] = []
    confident_errors = 0
    confident_error_denom = 0
    chars_total = 0
    t0 = time.time()

    for i, case in enumerate(cases, 1):
        if verbose:
            print(
                f"  [{i:>2}/{len(cases)}] {case.split}/{case.case_id}",
                end=" ",
                file=sys.stderr,
                flush=True,
            )
        # 1. user reducer
        reduced = reducer(case.raw_log)
        if not isinstance(reduced, str):
            raise TypeError(
                f"Reducer must return str, got {type(reduced).__name__} "
                f"on case {case.case_id}"
            )
        chars_total += len(reduced)

        # 2. diagnose
        diag = diagnose(
            diagnoser=diagnoser,
            case_id=case.case_id,
            reduced_context=reduced,
            case_metadata=case.case_metadata,
            cache_dir=Path(cache_dir).expanduser() if cache_dir else None,
            api_key=api_key,
        )

        # 3. score
        scored = score_case(
            diagnosis=diag,
            ground_truth=case.ground_truth,
            reduced_context=reduced,
        )
        diag_score = scored.get("diagnosis_score_v1_1")
        diag_scores.append(diag_score)
        cat_match.append(scored.get("category_match_score_v1_1"))
        ce = bool(scored.get("confident_error_v1_1"))
        if scored.get("diagnosis_success", True):
            confident_error_denom += 1
            if ce:
                confident_errors += 1

        per_case[case.case_id] = CaseResult(
            case_id=case.case_id,
            split=case.split,
            score=diag_score,
            category_match=scored.get("category_match_score_v1_1"),
            confident_error=ce,
            reduced_chars=len(reduced),
        )
        if verbose:
            print(
                f"  score={diag_score:.3f}" if diag_score is not None else "  score=—",
                file=sys.stderr,
            )

    elapsed = time.time() - t0
    return Result(
        score=macro(diag_scores),
        confident_error_rate=(
            confident_errors / confident_error_denom
            if confident_error_denom else 0.0
        ),
        chars_per_case=chars_total / len(cases) if cases else 0.0,
        diagnoser=diagnoser,
        n_cases=len(cases),
        elapsed_sec=elapsed,
        per_case=per_case,
    )
