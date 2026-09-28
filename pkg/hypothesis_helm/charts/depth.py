"""
Carry the selected dependency traversal depth through chart analysis and workers.
"""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager

from hypothesis_helm.environment import env, set_env

__all__ = ("ENVIRONMENT", "active_depth", "dependency_depth", "parse_max_depth")


ENVIRONMENT = "HYPOTHESIS_HELM_MAX_DEPTH"


def parse_max_depth(value: str) -> int | None:
    """
    Parse an optional dependency traversal limit, retaining unrestricted traversal for inf.

    Args:
        value (str): Nonnegative dependency depth or inf.

    Returns:
        int | None: Selected depth, or None for unrestricted traversal.
    """
    if value == "inf":
        return None
    try:
        depth = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max-depth must be inf or a nonnegative integer") from exc
    if depth < 0:
        raise argparse.ArgumentTypeError("max-depth must be inf or a nonnegative integer")
    return depth


def active_depth() -> int | None:
    """
    Read the command's dependency depth independently of compiler safety budgets.

    Returns:
        int | None: Selected depth, or None for unrestricted traversal.
    """
    value = env.get(ENVIRONMENT)
    return int(value) if value is not None else None


@contextmanager
def dependency_depth(max_depth: int | None) -> Iterator[None]:
    """
    Select a dependency depth and restore the surrounding command's scope afterward.

    Args:
        max_depth (int | None): Dependency levels to include; zero selects the current chart and None is unrestricted.

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
