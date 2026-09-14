"""
Control failure prevalence and clustering independently of the generated chart's branches.
"""

from __future__ import annotations

import json
import math
import random
from fractions import Fraction
from pathlib import Path
from textwrap import dedent

from attrs import frozen

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path, record_change
from hypothesis_helm.benchmarking.charts.manifests import configmap
from hypothesis_helm.benchmarking.charts.names import name_inputs
from hypothesis_helm.benchmarking.charts.workload import expected_output
from hypothesis_helm.schemas.contracts import mapping, sequence


def configure_surface(logical: Path, depth: int, *, workspace: FixtureWorkspace | None = None) -> dict[str, object]:
    """
    Add a nested resource to the common quantile chart with stable field names.

    Args:
        logical (Path): Fresh common chart whose fields will receive fixed surface names.
        depth (int): Number of nested Boolean conditions enclosing the extra resource.
        workspace (FixtureWorkspace | None): Owner of the reusable chart directory.

    Returns:
        dict[str, object]: Updated oracle metadata and retained replay operation.
    """
    chart = chart_path(logical, workspace=workspace)
    metadata = chart / "benchmark.json"
    spec = mapping(json.loads(metadata.read_text()))
    count = int(str(spec["input_complexity"]))
    if not 0 <= depth <= count:
        raise ValueError("condition depth must fit the input fields")
    names = [f"surfaceSwitch{index + 1:02d}" for index in range(count)]
    spec = name_inputs(chart, spec, names)
    gates = names[count - depth :] if depth else []
    resource = dedent(
        """
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: surface-gated
        data:
          state: present
        """
    ).lstrip("\n")
    template = "".join("{{ if .Values." + name + " }}\n" for name in gates) + resource + "{{ end }}\n" * depth
    (chart / "templates/surface.yaml").write_text(template)
    spec["structure"] = {"name": "error-surface", "paths": gates, "depth": depth}
    spec["unused_inputs"] = max(0, count - int(str(spec["active_inputs"])) - depth)
    metadata.write_text(json.dumps(spec, indent=2) + "\n")
    record_change(logical, "error_surface", {"depth": depth}, workspace=workspace)
    return spec


def surface_manifests(values: dict[str, object], spec: dict[str, object]) -> list[dict[str, object]]:
    """
    Calculate the unmodified chart's complete output without consulting error labels.

    Args:
        values (dict[str, object]): Full Boolean assignment.
        spec (dict[str, object]): Common quantile and nested-resource parameters.

    Returns:
        list[dict[str, object]]: Independent expected render used to verify the fixture.
    """
    result = [configmap("matrix", {"value": expected_output(values, spec)})]
    if all(values[str(path)] for path in sequence(mapping(spec["structure"])["paths"])):
        result.append(configmap("surface-gated", {"state": "present"}))
    return result


@frozen
class ErrorPopulation:
    """
    Hold a seeded input-aware assertion independently of chart generation and selection.

    Attributes:
        paths (tuple[str, ...]): Stable bit order of the Boolean input cube.
        failed (frozenset[int]): Assignments whose expected value differs from the fixed chart.
        neighbor_fraction (float | None): Fraction of one-switch neighbors of erroneous inputs that also fail.
    """

    paths: tuple[str, ...]
    failed: frozenset[int]
    neighbor_fraction: float | None

    @classmethod
    def build(cls, paths: tuple[str, ...], percent: float, clustering: float, seed: int) -> ErrorPopulation:
        """
        Select nested failing sets from a uniform-to-distance-ranked ordering.

        Args:
            paths (tuple[str, ...]): Complete Boolean field inventory.
            percent (float): Requested erroneous-input percentage, rounded down to whole assignments.
            clustering (float): Zero shuffles uniformly; one prioritizes Hamming distance from a seeded centre.
            seed (int): Error-placement seed independent of traversal and method order.

        Returns:
            ErrorPopulation: Exact denominator and measured neighborhood concentration.
        """
        if not paths or len(paths) > 12 or len(set(paths)) != len(paths):
            raise ValueError("require 1..12 distinct Boolean paths")
        if not math.isfinite(percent) or not 0 <= percent <= 100 or not math.isfinite(clustering) or not 0 <= clustering <= 1:
            raise ValueError("require error percent in 0..100 and clustering in 0..1")
        count = 2 ** len(paths)
        rng = random.Random(seed)
        centre = rng.randrange(count)
        priorities = [(1 - clustering) * rng.random() + clustering * (index ^ centre).bit_count() / len(paths) for index in range(count)]
        order = list(range(count))
        rng.shuffle(order)
        order.sort(key=priorities.__getitem__)
        size = int(count * Fraction(str(percent)) / 100)
        failed = frozenset(order[:size])
        neighbors = sum((index ^ (1 << bit)) in failed for index in failed for bit in range(len(paths)))
        return cls(paths, failed, neighbors / (len(failed) * len(paths)) if failed else None)

    def index(self, values: dict[str, object]) -> int:
        """
        Encode an assignment in the oracle's fixed field order.

        Args:
            values (dict[str, object]): Complete Boolean values configuration.

        Returns:
            int: Unique input identity, independent of planner visitation order.
        """
        return sum(int(bool(values[path])) << bit for bit, path in enumerate(self.paths))

    def erroneous(self, values: dict[str, object], resources: list[dict[str, object]], spec: dict[str, object]) -> bool:
        """
        Compare a real rendered value with the seeded input-aware specification.

        Args:
            values (dict[str, object]): Current configuration; no unvisited outcome is consulted.
            resources (list[dict[str, object]]): Actual Helm output or a compiler-proved equivalent render.
            spec (dict[str, object]): Quantile oracle parameters.

        Returns:
            bool: Whether this observed output violates its configuration's assertion.
        """
        expected = expected_output(values, spec)
        if self.index(values) in self.failed:
            expected += "-correction-required"
        actual = next(mapping(resource["data"])["value"] for resource in resources if mapping(resource["metadata"])["name"] == "matrix")
        return actual != expected
