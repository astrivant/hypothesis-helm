"""
Carry the selected dependency traversal depth through chart analysis and workers.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from hypothesis_helm.environment import env, set_env

ENVIRONMENT = "HYPOTHESIS_HELM_MAX_DEPTH"


def active_depth() -> int | None:
    """
    Read the command's dependency depth independently of compiler safety budgets.

    Returns:
        int | None: Selected depth, or unrestricted traversal for library callers without a scope.
    """
    value = env.get(ENVIRONMENT)
    return int(value) if value is not None else None


@contextmanager
def dependency_depth(max_depth: int | None) -> Iterator[None]:
    """
    Select a dependency depth and restore the surrounding command's scope afterward.

    Args:
        max_depth (int | None): Zero for the current chart, or the number of dependency levels to include.

    Yields:
        None: Analyses and spawned workers inherit this depth until the scope exits.
    """
    if max_depth is not None and (type(max_depth) is not int or max_depth < 0):
        raise ValueError("max-depth must be a nonnegative integer")
    previous = set_env(ENVIRONMENT, str(max_depth) if max_depth is not None else None)
    try:
        yield
    finally:
        set_env(ENVIRONMENT, previous)
