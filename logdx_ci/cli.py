"""Command-line entry point: `logdx-ci eval --reducer path/to/reducer.py`.

Your reducer module must expose a top-level function named `reduce` with
signature `def reduce(raw_log: str) -> str`. Example:

    # my_reducer.py
    def reduce(log: str) -> str:
        return log[-2000:]   # toy: tail-2000-chars

Then:

    logdx-ci eval --reducer my_reducer.py --diagnoser stub-debugger-v1
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from .api import evaluate


def _load_reducer(path: str):
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Reducer module not found: {p}")
    spec = importlib.util.spec_from_file_location("_user_reducer", p)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    fn = getattr(mod, "reduce", None)
    if fn is None or not callable(fn):
        raise AttributeError(
            f"{p} must define a top-level callable named `reduce`"
        )
    return fn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="logdx-ci",
        description="Evaluate a log reducer on the LogDx-CI v1.2 corpus.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_eval = sub.add_parser("eval", help="Run evaluation on the corpus.")
    p_eval.add_argument(
        "--reducer", required=True,
        help="Path to a Python file exposing `def reduce(log: str) -> str`."
    )
    p_eval.add_argument(
        "--diagnoser", default="stub-debugger-v1",
        choices=["stub-debugger-v1", "real-debugger-v2"],
        help="Which diagnoser to use (default: stub-debugger-v1)."
    )
    p_eval.add_argument(
        "--splits", nargs="*", default=None,
        help="Which splits to evaluate. Default: all 6 (35 cases)."
    )
    p_eval.add_argument(
        "--no-cache", action="store_true",
        help="Disable diagnosis cache (forces fresh LLM calls)."
    )
    p_eval.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-case progress."
    )
    args = parser.parse_args(argv)

    if args.cmd != "eval":
        parser.error(f"Unknown subcommand: {args.cmd}")

    reducer = _load_reducer(args.reducer)
    result = evaluate(
        reducer=reducer,
        diagnoser=args.diagnoser,
        splits=args.splits,
        cache_dir=None if args.no_cache else "~/.logdx_ci_cache/diagnosis",
        verbose=not args.quiet,
    )
    print()
    print(result.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
