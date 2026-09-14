"""
Inject seeded finite-domain faults and project complete manifest features onto fixed PCA axes.
"""

import math
import random
from pathlib import Path
from textwrap import dedent

import numpy as np
from numpy.typing import NDArray

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path, record_change
from hypothesis_helm.schemas.contracts import configuration_key, mapping


def inject_errors(
    chart: Path, values: list[dict[str, object]], percent: float, seed: int, *, workspace: FixtureWorkspace | None = None
) -> set[int]:
    """
    Add a visible error projection at uniformly sampled valid input assignments.

    Args:
        chart (Path): Generated structural fixture.
        values (list[dict[str, object]]): Complete ordered valid input domain.
        percent (float): Percentage of valid assignments to mark faulty, rounded down.
        seed (int): Reproducible error placement seed, independent from selection.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        set[int]: Exact failing input indices, serving as an independent oracle.
    """
    if not math.isfinite(percent) or not 0 <= percent <= 100 or not values:
        raise ValueError("require a nonempty domain and finite error percentage in 0..100")
    percent = float(percent)
    record_change(chart, "uniform_errors", {"percent": percent, "seed": seed}, workspace=workspace)
    chart = chart_path(chart, workspace=workspace)
    faulty = set(random.Random(seed).sample(range(len(values)), math.floor(len(values) * percent / 100)))
    paths = sorted(values[0])

    def branch(indices: list[int], depth: int) -> str:
        """
        Lower the error truth table to a decision tree with constant subtrees collapsed.

        Args:
            indices (list[int]): Valid assignments reaching this node.
            depth (int): Next input path to inspect.

        Returns:
            str: Helm expression producing the expected or incorrect status.
        """
        labels = {index in faulty for index in indices}
        if len(labels) == 1:
            return "incorrect" if True in labels else "expected"
        path = paths[depth]
        groups: dict[str, list[int]] = {}
        for index in indices:
            groups.setdefault(configuration_key({"value": values[index][path]}), []).append(index)
        branches = list(groups.values())
        if isinstance(values[indices[0]][path], bool):
            branches.sort(key=lambda group: bool(values[group[0]][path]), reverse=True)
        result = branch(branches[-1], depth + 1)
        for group in reversed(branches[:-1]):
            value = values[group[0]][path]
            if isinstance(value, bool):
                condition = f".Values.{path}" if value else f"not .Values.{path}"
            else:
                condition = f"eq (int .Values.{path}) {value}"
            result = "{{ if " + condition + " }}" + branch(group, depth + 1) + "{{ else }}" + result + "{{ end }}"
        return result

    template = dedent(
        f"""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: benchmark-error
        data:
          status: "{branch(list(range(len(values))), 0)}"
        """
    ).removeprefix("\n")
    (chart / "templates/benchmark-error.yaml").write_text(template)
    return faulty


def manifest_features(resources: list[dict[str, object]]) -> dict[str, float]:
    """
    Encode resource presence, numeric leaves and typed categorical leaves without document order.

    Args:
        resources (list[dict[str, object]]): Complete rendered manifest bundle.

    Returns:
        dict[str, float]: Sparse feature vector with stable resource and JSON path identities.
    """
    features: dict[str, float] = {}

    def visit(value: object, path: list[object]) -> None:
        """
        Preserve nested shape and leaf identity, including list ordering and empty containers.

        Args:
            value (object): Current JSON-compatible manifest node.
            path (list[object]): Typed path from the resource identity.

        Returns:
            None: Features are accumulated into the enclosing sparse vector.
        """
        key = configuration_key({"path": path})
        features[key + ":present"] = 1.0
        if isinstance(value, dict):
            features[key + ":container:object"] = 1.0
            for name, child in mapping(value).items():
                visit(child, [*path, name])
        elif isinstance(value, list):
            features[key + ":container:array"] = 1.0
            for index, child in enumerate(value):
                visit(child, [*path, index])
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError("manifest contains nonfinite numeric data")
            features[key + ":numeric"] = numeric
        else:
            features[key + ":category:" + configuration_key({"value": value})] = 1.0

    occurrences: dict[str, int] = {}
    for resource in sorted(resources, key=configuration_key):
        metadata = mapping(resource.get("metadata", {}))
        identity = configuration_key(
            {
                "apiVersion": resource.get("apiVersion"),
                "kind": resource.get("kind"),
                "namespace": metadata.get("namespace"),
                "name": metadata.get("name"),
            }
        )
        occurrence = occurrences.get(identity, 0)
        occurrences[identity] = occurrence + 1
        visit(resource, [identity, occurrence])
    return features


def project(
    bundles: list[list[dict[str, object]]],
) -> tuple[NDArray[np.float64], dict[str, object]]:
    """
    Fit standardized PCA once to the complete input-weighted output population.

    Args:
        bundles (list[list[dict[str, object]]]): Outputs in complete valid input order.

    Returns:
        tuple[NDArray[np.float64], dict[str, object]]:
            Two-dimensional scores and reproducible basis metadata.
    """
    if not bundles:
        raise ValueError("PCA requires a nonempty output population")
    sparse = [manifest_features(bundle) for bundle in bundles]
    names = sorted(set().union(*(row.keys() for row in sparse)))
    matrix = np.array([[row.get(name, 0.0) for name in names] for row in sparse], dtype=np.float64)
    center = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    active = scale > 0
    standardized = (matrix[:, active] - center[active]) / scale[active]
    _, singular, vectors = np.linalg.svd(standardized, full_matrices=False)
    dimensions = min(2, len(singular))
    basis = vectors[:dimensions].copy()
    for component in basis:
        if component[np.argmax(np.abs(component))] < 0:
            component *= -1
    scores = np.zeros((len(bundles), 2), dtype=np.float64)
    scores[:, :dimensions] = standardized @ basis.T
    variance = np.zeros(2, dtype=np.float64)
    if float(np.sum(singular**2)) > 0:
        variance[:dimensions] = singular[:dimensions] ** 2 / np.sum(singular**2)
    return scores, {
        "features": [name for name, keep in zip(names, active, strict=True) if keep],
        "center": center[active].tolist(),
        "scale": scale[active].tolist(),
        "components": basis.tolist(),
        "explained_variance_ratio": variance.tolist(),
        "weighting": "one row per valid input, including repeated outputs",
        "encoding": ("resource presence, numeric leaves, typed one-hot categories; numeric strings remain categorical"),
        "fit": "complete faulty chart population once per category; no refit after trimming",
    }
