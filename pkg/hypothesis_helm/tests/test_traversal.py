"""
Traversal preserves coverage while varying reproducible scheduling priorities.
"""

from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.cli import argument_parser
from hypothesis_helm.execution.estimate import estimate_suite
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.execution.traversal import order_configurations, order_paths
from hypothesis_helm.schemas.contracts import mapping, sequence

PATHS = [("global",), ("global", "configMaps"), ("service",), ("service", "ports", "*"), ("image", "tag")]


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        ("linear", [0, 1, 2, 3, 4]),
        ("root-first", [0, 2, 1, 4, 3]),
        ("leaf-first", [3, 1, 4, 0, 2]),
    ],
)
def test_path_depth_order(strategy: str, expected: list[int]) -> None:
    """
    Visit complete depth layers in the requested direction, preserving depth ties.

    Args:
        strategy (str): Deterministic non-random traversal mode.
        expected (list[int]): Original path indices in expected execution order.

    Returns:
        None: Container and array paths receive their actual YAML path depth.
    """
    assert order_paths(PATHS, lambda path: path, strategy=strategy) == [PATHS[index] for index in expected]
    for command in ("run", "test", "scan"):
        assert argument_parser().parse_args([command, "charts", "--traversal-strategy", strategy]).traversal_strategy == strategy


def test_random_path_order_is_seeded_and_subset_stable() -> None:
    """
    Change timeout prefixes with the seed while preserving shard and cache ordering.

    Returns:
        None: Repeated seeds reproduce the order without losing or duplicating paths.
    """
    original = PATHS.copy()
    first = order_paths(PATHS, lambda path: path, seed=0)
    assert first == order_paths(PATHS, lambda path: path, seed=0)
    assert first != order_paths(PATHS, lambda path: path, seed=1)
    assert set(first) == set(PATHS) and len(first) == len(PATHS)
    subset = PATHS[::2]
    assert order_paths(subset, lambda path: path, seed=0) == [path for path in first if path in subset]
    assert PATHS == original


@pytest.mark.parametrize("strategy", ["unknown", "shallow", "deep"])
def test_unknown_traversal_is_rejected(strategy: str) -> None:
    """
    Reject invalid traversal modes even when the selected work is empty.

    Args:
        strategy (str): Unsupported or removed traversal name.

    Returns:
        None: An unsupported mode cannot silently fall back to linear traversal.
    """
    with pytest.raises(ValueError, match="traversal_strategy"):
        order_paths([], lambda path: path, strategy=strategy)
    with pytest.raises(ValueError, match="traversal_strategy"):
        order_configurations([], lambda value: value, {}, strategy=strategy)
    for command in ("run", "test", "scan"):
        with pytest.raises(SystemExit) as error:
            argument_parser().parse_args([command, "charts", "--traversal-strategy", strategy])
        assert error.value.code == 2


def test_finite_traversal_preserves_filtered_population() -> None:
    """
    Reorder only retained joint cases, with explicit changed-field depth semantics.

    Returns:
        None: Traversal never restores omitted cases or removes retained configurations.
    """
    baseline = {"replicas": 1, "global": {"port": 80}}
    shallow = {"replicas": 2, "global": {"port": 80}}
    deep = {"replicas": 1, "global": {"port": 81}}
    retained = [deep, shallow]
    assert order_configurations(retained, lambda value: value, baseline, strategy="root-first") == [shallow, deep]
    assert order_configurations(retained, lambda value: value, baseline, strategy="leaf-first") == [deep, shallow]
    random = order_configurations(retained, lambda value: value, baseline, seed=42)
    assert random == order_configurations(retained, lambda value: value, baseline, seed=42)
    assert len(random) == 2 and all(value in retained for value in random)
    assert retained == [deep, shallow]


@pytest.mark.parametrize("strategy", ["root-first", "leaf-first"])
def test_parallel_workers_finish_each_depth_layer(tmp_path: Path, strategy: str) -> None:
    """
    Require an entire depth layer to finish before dispatching the next one.

    Args:
        tmp_path (Path): Runnable saved-suite fixture and result directory.
        strategy (str): Increasing or decreasing path depth.

    Returns:
        None: Every real child pytest process observes all required earlier-layer markers.
    """
    blocks = [
        dedent("""
        import pytest
        from pathlib import Path
        """)
    ]
    for index, path in enumerate(PATHS):
        earlier = [
            other
            for other, candidate in enumerate(PATHS)
            if (len(candidate) < len(path) if strategy == "root-first" else len(candidate) > len(path))
        ]
        blocks.append(
            dedent(f"""
            @pytest.mark.hypothesis_helm_path({path!r})
            def test_path_{index}():
                root = Path(__file__).parent
                assert all((root / str(index)).exists() for index in {earlier!r})
                (root / "{index}").touch()
            """)
        )
    (tmp_path / "test_chart_values.py").write_text("\n".join(blocks))
    assert run_suite(tmp_path, jobs=3, cache=False, traversal_strategy=strategy) == 0


def test_dry_run_exposes_reproducible_path_order(tmp_path: Path) -> None:
    """
    Collect the same seeded order used by execution without invoking any properties.

    Args:
        tmp_path (Path): Saved suite whose bodies must never execute during estimation.

    Returns:
        None: Two equal seeds match and another seed changes the collected execution order.
    """
    blocks = [
        dedent("""
        import pytest
        """)
    ]
    for index, path in enumerate(PATHS):
        blocks.append(
            dedent(f"""
            @pytest.mark.hypothesis_helm_path({path!r})
            def test_path_{index}():
                raise AssertionError("dry-run executed a property")
            """)
        )
    (tmp_path / "test_chart_values.py").write_text("\n".join(blocks))
    orders = []
    for seed in (0, 0, 1):
        result = estimate_suite(tmp_path, seed=seed, cache=False, traversal_strategy="random")
        assert result["traversal_strategy"] == "random" and result["seed"] == seed
        orders.append([str(mapping(item)["test"]) for item in sequence(result["properties"])])
    assert orders[0] == orders[1] and orders[0] != orders[2]
    assert set(orders[0]) == set(orders[2])
