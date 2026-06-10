"""Locate and load LogDx-CI corpus cases.

Resolution order for the corpus root (used by `evaluate()` internally):

  1. Explicit `corpus_root=<path>` argument.
  2. Walk up from cwd looking for `cases/` + `tools/` (the user cloned the repo).
  3. `$LOGDX_CI_ROOT` env var.
  4. `~/.logdx_ci_cache/repo/LogDx-<tag>/` if a previous run cached it.
  5. Download tarball from GitHub release (default tag: v1.2, ~20MB) and extract.

So `pip install logdx-ci && python -c 'import logdx_ci; ...'` works without
needing the user to clone the repo first — the corpus is fetched on demand.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPLITS = ["dev", "holdout", "stress", "v2/dev", "v2/holdout", "v2/stress"]

DEFAULT_REPO_TAG = "v1.2"
CACHE_ROOT = Path("~/.logdx_ci_cache").expanduser()
REPO_CACHE_DIR = CACHE_ROOT / "repo"
TARBALL_URL_TEMPLATE = (
    "https://github.com/eyuansu62/LogDx/archive/refs/tags/{tag}.tar.gz"
)


@dataclass(frozen=True)
class Case:
    split: str
    case_id: str
    raw_log: str
    case_metadata: dict
    ground_truth: dict


class CorpusNotFound(RuntimeError):
    """Raised when the LogDx-CI corpus cannot be located or fetched."""


def _looks_like_corpus_root(p: Path) -> bool:
    return all((p / sub).is_dir() for sub in ("cases", "tools", "prompts", "examples"))


def find_local_repo_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) looking for `cases/` + `tools/`.

    Returns None if no local repo found (unlike the old `find_repo_root`,
    which raised). Use `ensure_corpus_root()` for the resolved root that
    falls back to the cache and tarball download.
    """
    p = (start or Path.cwd()).resolve()
    for cand in [p] + list(p.parents):
        if _looks_like_corpus_root(cand):
            return cand
    return None


def _find_cached_repo_root() -> Path | None:
    if not REPO_CACHE_DIR.is_dir():
        return None
    candidates = sorted(
        d for d in REPO_CACHE_DIR.iterdir()
        if d.is_dir() and _looks_like_corpus_root(d)
    )
    return candidates[-1] if candidates else None


def _fetch_repo_tarball(tag: str) -> Path:
    """Download + extract the LogDx repo tarball to the cache dir. Returns extracted root."""
    url = TARBALL_URL_TEMPLATE.format(tag=tag)
    REPO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[logdx-ci] first-time setup: fetching corpus tarball "
        f"({tag}, ~20 MB)\n           from {url}",
        file=sys.stderr,
    )
    with tempfile.NamedTemporaryFile(
        suffix=".tar.gz", delete=False, dir=str(CACHE_ROOT)
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with urllib.request.urlopen(url, timeout=180) as resp:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(resp, f, length=1024 * 1024)
        size_mb = tmp_path.stat().st_size / (1024 * 1024)
        print(
            f"[logdx-ci] downloaded {size_mb:.1f} MB; extracting...",
            file=sys.stderr,
        )
        with tarfile.open(tmp_path) as tf:
            try:
                tf.extractall(REPO_CACHE_DIR, filter="data")  # py3.12+
            except TypeError:
                tf.extractall(REPO_CACHE_DIR)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    extracted = sorted(
        d for d in REPO_CACHE_DIR.iterdir()
        if d.is_dir() and d.name.startswith("LogDx-") and _looks_like_corpus_root(d)
    )
    if not extracted:
        raise CorpusNotFound(
            f"Tarball extracted but no valid LogDx-* directory found in "
            f"{REPO_CACHE_DIR}"
        )
    root = extracted[-1]
    print(f"[logdx-ci] corpus cached at {root}", file=sys.stderr)
    return root


def ensure_corpus_root(corpus_root: Path | None = None) -> Path:
    """Resolve the corpus root, fetching from GitHub on first use if needed.

    See module docstring for the resolution order.
    """
    if corpus_root is not None:
        p = Path(corpus_root).expanduser().resolve()
        if not _looks_like_corpus_root(p):
            raise CorpusNotFound(
                f"`corpus_root={p}` does not look like a LogDx repo "
                "(needs cases/ + tools/ + prompts/ + examples/)"
            )
        return p

    local = find_local_repo_root()
    if local is not None:
        return local

    env_root = os.environ.get("LOGDX_CI_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if _looks_like_corpus_root(p):
            return p
        raise CorpusNotFound(
            f"$LOGDX_CI_ROOT={env_root!r} but it doesn't look like a LogDx repo"
        )

    cached = _find_cached_repo_root()
    if cached is not None:
        return cached

    tag = os.environ.get("LOGDX_CI_TAG", DEFAULT_REPO_TAG)
    return _fetch_repo_tarball(tag)


def find_repo_root(start: Path | None = None) -> Path:
    """Backwards-compatible name — now resolves to ensure_corpus_root.

    Kept so existing internal callers (diagnoser.py, scoring.py,
    static_scoring.py) keep working. Prefer `ensure_corpus_root()` in
    new code for clarity about the side effect (may download on first use).
    """
    return ensure_corpus_root()


def load_cases(
    splits: list[str] | None = None,
    corpus_root: Path | None = None,
) -> list[Case]:
    """Load all cases for the given splits."""
    if splits is None:
        splits = DEFAULT_SPLITS
    root = ensure_corpus_root(corpus_root)
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
