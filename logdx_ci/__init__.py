"""logdx-ci: evaluate your log reduction tool on the LogDx-CI v1.2 corpus.

Quickstart:

    import logdx_ci

    def my_reducer(raw_log: str) -> str:
        # your logic here
        return raw_log[-2000:]  # toy example: tail 2000 chars

    result = logdx_ci.evaluate(my_reducer, diagnoser="stub-debugger-v1")
    print(result.summary())

See logdx_ci/README.md for a full tutorial.
"""
from .api import evaluate, Result
from .baselines import BASELINES

__all__ = ["evaluate", "Result", "BASELINES"]
__version__ = "0.1.0"
