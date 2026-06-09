"""Example reducer for the logdx-ci CLI.

Usage:

    logdx-ci eval --reducer examples/my_reducer.py \\
        --diagnoser stub-debugger-v1 \\
        --splits v2/dev

Replace the `reduce` function body with your own log-reduction logic.
"""
from __future__ import annotations


def reduce(raw_log: str) -> str:
    """Trivial reducer: keep the last 200 lines of the log.

    Real reducers will typically:
      - identify failure region (last test/build step)
      - keep stderr / panic / traceback blocks intact
      - drop progress bars, ANSI noise, and apt-get install spam
      - optionally cap the output at N tokens
    """
    return "\n".join(raw_log.split("\n")[-200:])
