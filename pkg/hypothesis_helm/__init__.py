"""
Property-based tests for Helm charts.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hypothesis_helm.charts.generate import coalesce, generate_tests
    from hypothesis_helm.charts.model import Chart
    from hypothesis_helm.charts.runner import check_chart

__all__ = ["Chart", "check_chart", "coalesce", "generate_tests"]


def __getattr__(name: str) -> object:
    """
    Load the public API without constructing strategies during pytest plugin startup.

    Args:
        name (str): Public package attribute requested by the caller.

    Returns:
        object: The exported chart type or framework function.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from hypothesis_helm.charts.generate import coalesce, generate_tests
    from hypothesis_helm.charts.model import Chart
    from hypothesis_helm.charts.runner import check_chart

    exports: dict[str, object] = {
        "Chart": Chart,
        "check_chart": check_chart,
        "coalesce": coalesce,
        "generate_tests": generate_tests,
    }
    globals().update(exports)
    return exports[name]
