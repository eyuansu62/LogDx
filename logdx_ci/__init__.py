"""logdx-ci: evaluate your log reduction tool on the LogDx-CI v1.2 corpus.

Quickstart:

    import logdx_ci

    def my_reducer(raw_log: str) -> str:
        # your logic here
        return raw_log[-2000:]  # toy example: tail 2000 chars

    result = logdx_ci.evaluate(my_reducer)   # default = static, no LLM
    print(result.summary())

See logdx_ci/README.md for a full tutorial.
"""
from .api import evaluate, Result
from .baselines import BASELINES, STATIC_BASELINES

__all__ = ["evaluate", "Result", "BASELINES", "STATIC_BASELINES"]
__version__ = "0.5.0"
