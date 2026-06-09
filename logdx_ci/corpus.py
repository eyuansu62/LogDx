"""Locate and load LogDx-CI v1.2 corpus cases.

For V0 we require the LogDx repo to be available locally — auto-discovered
by walking up from CWD looking for the `cases/` directory. A future
version will fall back to HF dataset download for fresh pip installs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]


@dataclass(frozen=True)
class Case:
    split: str
    case_id: str
    raw_log: str
    case_metadata: dict
    ground_truth: dict


class CorpusNotFound(RuntimeError):
    """Raised when the LogDx-CI corpus cannot be located locally."""


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) looking for `cases/` + `tools/`."""
    p = (start or Path.cwd()).resolve()
    for cand in [p] + list(p.parents):
        if (cand / "cases").is_dir() and (cand / "tools").is_dir():
            return cand
    raise CorpusNotFound(
        "Could not find the LogDx-CI corpus. Run logdx_ci.evaluate(...) "
        "from inside a clone of https://github.com/eyuansu62/LogDx, "
        "or pass `corpus_root=<path>` explicitly."
    )


def load_cases(
    splits: list[str] | None = None,
    corpus_root: Path | None = None,
) -> list[Case]:
    """Load all cases for the given splits."""
    if splits is None:
        splits = DEFAULT_SPLITS
    root = corpus_root or find_repo_root()
    cases: list[Case] = []
    for split in splits:
        split_dir = root / "cases" / split
        if not split_dir.is_dir():
            raise CorpusNotFound(f"Missing split directory: {split_dir}")
        for case_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            cases.append(
                Case(
                    split=split,
                    case_id=case_dir.name,
                    raw_log=(case_dir / "raw.log").read_text(),
                    case_metadata=json.loads((case_dir / "case.json").read_text()),
                    ground_truth=json.loads(
                        (case_dir / "ground_truth.json").read_text()
                    ),
                )
            )
    return cases
