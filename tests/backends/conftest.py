"""
Select real native backend validation explicitly in local and hosted test runs.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register an explicit native test route without silently skipping unavailable hardware.

    Args:
        parser (pytest.Parser): Pytest option owner.

    Returns:
        None: Adds the backend validation selector.
    """
    parser.addoption("--native-backend", choices=("reference", "cpu-vector", "gpu"), default="reference")


@pytest.fixture
def native_backend(request: pytest.FixtureRequest) -> str:
    """
    Return the declared engine; an unavailable selected engine must fail its tests.

    Args:
        request (pytest.FixtureRequest): Current test configuration.

    Returns:
        str: Explicit engine selection.
    """
    return str(request.config.getoption("--native-backend"))
