"""
Partition the framework suite across CI runners independently of chart sharding.
"""

import hashlib

import pytest

__all__ = ("pytest_addoption", "pytest_collection_modifyitems")


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register an explicit test-suite partition, separate from production shard coordinates.

    Args:
        parser (pytest.Parser): Active pytest argument registry.

    Returns:
        None: The optional one-based shard argument becomes available.
    """
    parser.addoption("--suite-shard", help="Run one framework test shard, expressed as INDEX/TOTAL (one-based)")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    Assign each collected test to exactly one runner using its stable pytest node identifier.

    Args:
        config (pytest.Config): Explicit suite shard supplied by CI or a developer.
        items (list[pytest.Item]): Collected tests, identical in each local xdist worker.

    Returns:
        None: Only this runner's tests remain, preserving their original collection order.
    """
    raw = config.getoption("suite_shard")
    if raw is None:
        return
    try:
        index, total = map(int, str(raw).split("/"))
        if not 1 <= index <= total:
            raise ValueError("shard outside bounds")
    except ValueError as error:
        raise pytest.UsageError("--suite-shard must be INDEX/TOTAL with 1 <= INDEX <= TOTAL") from error
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        # Avoid Python's process-randomized hash: all runners must agree on ownership.
        owner = int.from_bytes(hashlib.sha256(item.nodeid.encode()).digest()[:8]) % total
        (selected if owner == index - 1 else deselected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
