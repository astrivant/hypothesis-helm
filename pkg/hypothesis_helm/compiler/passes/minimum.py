"""
Export deterministic value examples and reduce successfully verified baselines.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from jsonschema import validators

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.constants import fill_missing
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.render_hashes import RenderHashes
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer
from hypothesis_helm.schemas.conformity import ENVIRONMENT
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping, sequence
from hypothesis_helm.schemas.model import ValuesModel


def value_paths(value: object, prefix: tuple[str | int, ...] = ()) -> list[tuple[str | int, ...]]:
    """
    Enumerate removable mapping entries and array elements without treating false values as absent.

    Args:
        value (object): Concrete values subtree.
        prefix (tuple[str | int, ...]): Path to this subtree.

    Returns:
        list[tuple[str | int, ...]]: Parent entries followed by their descendants.
    """
    entries = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
    result = []
    for key, child in entries:
        path = (*prefix, key)
        result.append(path)
        result.extend(value_paths(child, path))
    return result


def remove_paths(values: dict[str, object], paths: list[tuple[str | int, ...]]) -> dict[str, object]:
    """
    Remove selected entries from a copy, deleting array indices from highest to lowest.

    Args:
        values (dict[str, object]): Candidate baseline.
        paths (list[tuple[str | int, ...]]): Entries to delete.

    Returns:
        dict[str, object]: Independent candidate retaining actual values for every remaining key.
    """
    candidate = copy.deepcopy(values)
    for path in reversed(paths):
        parent: object = candidate
        try:
            for key in path[:-1]:
                parent = (
                    parent[key] if isinstance(parent, dict) else parent[key] if isinstance(parent, list) and isinstance(key, int) else None
                )
            if isinstance(parent, dict):
                parent.pop(path[-1], None)
            elif isinstance(parent, list) and isinstance(path[-1], int):
                del parent[path[-1]]
        except (KeyError, IndexError, TypeError):
            continue
    return candidate


def resource_count(resources: list[dict[str, object]]) -> int:
    """
    Count Kubernetes objects, excluding empty List envelopes.

    Args:
        resources (list[dict[str, object]]): Validated rendered documents.

    Returns:
        int: Number of actual resources in the output.
    """
    return sum(
        resource_count([mapping(item) for item in sequence(resource["items"])]) if resource.get("kind") == "List" else 1
        for resource in resources
    )


def export_minimal(
    chart: Chart,
    target: Path | None = None,
    *,
    directory: Path = Path("."),
    helm: str = "helm",
    timeout: float = 30,
    budget: float = 30,
    build_dependencies: bool = True,
) -> dict[str, object]:
    """
    Export deterministic example values and reduce them only when validation succeeds.

    Args:
        chart (Chart): Original defaults and input contract.
        target (Path | None): Optional export filename.
        directory (Path): Generated-filename destination.
        helm (str): Helm executable.
        timeout (float): Per-command limit, also bounded by the search deadline.
        budget (float): Total preparation, rendering, and minimization budget in seconds.
        build_dependencies (bool): Build dependencies in the isolated copy before verification.

    Returns:
        dict[str, object]: Export paths and explicit validation status; failed examples remain reviewable.
    """
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("minimal-values timeout must be positive and finite")
    started = time.monotonic()
    deadline = started + budget
    best: dict[str, object] | None = None
    best_count = 0
    tested = 0
    complete = False
    last_error = "No valid baseline was found"
    validator = validators.validator_for(chart.schema)(chart.schema)
    checked: dict[str, int] = {}
    hashes = RenderHashes(scope="minimal-values-search")
    model = ValuesModel.from_schema(chart.schema)
    inventory = InputInventory.build(chart)
    example = fill_missing(model, chart.defaults, inventory.known)
    conformity = json.loads(os.environ[ENVIRONMENT]) if os.environ.get(ENVIRONMENT) else None
    try:
        with tempfile.TemporaryDirectory(prefix="helm-minimum-") as temporary:
            with execution_timer(budget):
                isolated = Path(temporary) / "chart"
                shutil.copytree(chart.path, isolated)
                metadata = mapping(yamlio.load((isolated / "Chart.yaml").read_text()))
                if metadata.get("type") == "library":
                    raise ValueError("Library charts do not have standalone nonempty manifests")
                if build_dependencies and metadata.get("dependencies"):
                    built = Processes().run(
                        [helm, "dependency", "build", str(isolated)],
                        capture_output=True,
                        text=True,
                        timeout=min(timeout, max(0.001, deadline - time.monotonic())),
                    )
                    if built.returncode:
                        raise ValueError(f"Cannot verify minimal values: {built.stdout}{built.stderr}")

                def verify(values: dict[str, object]) -> int:
                    """
                    Replace chart defaults before linting and rendering a schema-accepted candidate.

                    Args:
                        values (dict[str, object]): Concrete entire baseline to verify.

                    Returns:
                        int: Nonzero resource count on success, zero for a rejected candidate.
                    """
                    nonlocal tested, last_error
                    if time.monotonic() >= deadline:
                        raise TimeLimitReached()
                    key = configuration_key(values)
                    if key in checked:
                        return checked[key]
                    tested += 1
                    checked[key] = 0
                    if not validator.is_valid(json_value(values)):
                        last_error = "Candidate violates values.schema.json"
                        return 0
                    (isolated / "values.yaml").write_text(yamlio.dump(values))
                    try:
                        lint = Processes().run(
                            [helm, "lint", str(isolated)],
                            capture_output=True,
                            text=True,
                            timeout=min(timeout, max(0.001, deadline - time.monotonic())),
                        )
                        if lint.returncode:
                            last_error = lint.stdout + lint.stderr
                            return 0
                        resources = render(
                            Chart(isolated, chart.schema, values),
                            {},
                            helm=helm,
                            timeout=min(timeout, max(0.001, deadline - time.monotonic())),
                            hashes=hashes,
                            stream=False,
                        )
                        count = resource_count(resources)
                        if not count:
                            last_error = "Candidate renders no resources"
                        checked[key] = count
                        return count
                    except (AssertionError, ValueError, subprocess.TimeoutExpired) as exc:
                        last_error = str(exc)
                        return 0

                best_count = verify(chart.defaults)
                if best_count:
                    best = copy.deepcopy(chart.defaults)
                else:
                    best_count = verify(example)
                    if best_count:
                        best = copy.deepcopy(example)
                if best is not None:
                    # Disabling an optional component is accepted only if it removes resources.
                    for path in value_paths(best):
                        if path[-1] != "enabled":
                            continue
                        candidate = copy.deepcopy(best)
                        parent: object = candidate
                        for key in path[:-1]:
                            parent = (
                                parent[key]
                                if isinstance(parent, dict)
                                else parent[key]
                                if isinstance(parent, list) and isinstance(key, int)
                                else None
                            )
                        if isinstance(parent, dict) and parent.get("enabled") is True:
                            parent["enabled"] = False
                            count = verify(candidate)
                            if 0 < count < best_count:
                                best, best_count = candidate, count
                    granularity = 2
                    while paths := value_paths(best):
                        width = max(1, math.ceil(len(paths) / granularity))
                        for offset in range(0, len(paths), width):
                            candidate = remove_paths(best, paths[offset : offset + width])
                            count = verify(candidate)
                            if 0 < count <= best_count:
                                best, best_count = candidate, count
                                granularity = 2
                                break
                        else:
                            if width == 1:
                                break
                            granularity = min(len(paths), granularity * 2)
                            continue
                    complete = True
    except TimeLimitReached:
        if time.monotonic() < deadline:
            raise  # Respect a shorter enclosing scan deadline.
    verified = best is not None
    if best is None:
        best = example
    verification = {
        "generated_value_preference": "supplied values, declared defaults/const, then typed zeros; no generated-value search",
        "kubernetes_api_validation": ("passed" if verified else "not-confirmed") if conformity else "not-run",
        "kubernetes_schema_version": conformity["version"] if conformity else None,
        "verified": verified,
        "validation_error": last_error.replace(str(isolated), "chart") if not verified else None,
        "checks": (["values schema", "Helm lint", "Helm template", "manifest envelopes"] + (["Kubeconform"] if conformity else []))
        if verified
        else [],
        "nonempty_resources": best_count,
        "candidates_checked": tested,
        "elapsed_seconds": time.monotonic() - started,
        "budget_seconds": budget,
        "search_complete": complete,
        "deletion_minimal": complete,
        "globally_minimal_proven": False,
        "scope": "No single remaining entry can be removed while preserving validity "
        "without increasing the resource count; no global minimum over all values is claimed"
        if complete
        else "Minimality not established; see verification status",
        "render_equivalence_proven": False,
    }
    optimized = Chart(chart.path, chart.schema, best)
    return inventory.dump(optimized, target, directory=directory, verification=verification)
