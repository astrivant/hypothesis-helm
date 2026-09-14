"""
Runtime helpers used by generated, editable Python property tests.
"""

from __future__ import annotations

import copy
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import SkipTest

from attrs import frozen
from hypothesis import assume, note
from hypothesis import strategies as st
from hypothesis.strategies import DataObject
from jsonschema import validators

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.rendering import RenderFailure, render
from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.rules import check, ignored
from hypothesis_helm.schemas.contracts import json_value, mapping, schema_strategy, sequence


@frozen
class RenderOptions:
    """
    Configure Helm rendering for every property in a generated suite.

    Attributes:
        timeout (float): Maximum seconds allowed for each Helm invocation.
        helm (str): Helm executable used for rendering.
        release (str): Release name supplied to Helm.
        namespace (str): Release namespace supplied to Helm.
        kube_version (str | None): Optional Kubernetes capability version.
        allow_empty (bool): Whether empty rendered output satisfies the contract.
    """

    timeout: float = 30
    helm: str = "helm"
    release: str = "hypothesis"
    namespace: str = "default"
    kube_version: str | None = None
    allow_empty: bool = False


@contextmanager
def prepared_chart(source: Path, generated: Path) -> Iterator[Chart]:
    """
    Render a temporary chart with the reviewed coalesced values/inferred schema.

    Args:
        source (Path): Source chart location or template text.
        generated (Path): Directory containing the generated schema and values snapshots.

    Yields:
        Chart: Temporary chart with the reviewed testing contract.
    """
    with tempfile.TemporaryDirectory(prefix="hypothesis-helm-generated-") as directory:
        target = Path(directory) / "chart"
        shutil.copytree(source, target)
        shutil.copyfile(generated / "values.coalesced.yaml", target / "values.yaml")
        shutil.copyfile(generated / "values.inferred.schema.json", target / "values.schema.json")
        chart = Chart.load(target)
        chart.dependency_model = Dependencies.build(target)
        yield chart


def _replace(
    values: dict[str, object],
    path: tuple[str | int, ...],
    value: object,
    *,
    schema: dict[str, object] | None = None,
    data: DataObject | None = None,
) -> dict[str, object]:
    """
    Replace one concrete leaf while preserving the rest of the YAML document.

    Args:
        values (dict[str, object]): Values document used as the rendering baseline.
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        value (object): Candidate value supplied by the property strategy.
        schema (dict[str, object] | None): JSON Schema defining the accepted value domain.
        data (DataObject | None): Hypothesis draw context for dependent values and parent
            containers.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    result = copy.deepcopy(values)
    current: object = result

    def context(prefix: tuple[str | int, ...], next_segment: str | int) -> object:
        """
        Generate required sibling values for a missing parent container.

        Args:
            prefix (tuple[str | int, ...]): Resolved parent path for the current value.
            next_segment (str | int): Next path component used to choose a container kind.

        Returns:
            object: Parsed or generated value at the requested boundary.
        """
        if data is not None and schema is not None:
            from hypothesis_helm.charts.model import _schema_nodes

            symbolic = tuple("*" if isinstance(p, int) else p for p in prefix)
            nodes = _schema_nodes(schema, symbolic, schema)
            if nodes:
                fragment: dict[str, object] = {"allOf": nodes}
                for key in ("$defs", "definitions"):
                    if key in schema:
                        fragment[key] = schema[key]
                return data.draw(schema_strategy(fragment), label="missing parent context")
        return [] if isinstance(next_segment, int) else {}

    for i, segment in enumerate(path[:-1]):
        next_segment = path[i + 1]
        if isinstance(segment, int):
            if not isinstance(current, list):
                raise ValueError("path requires an array")
            while len(current) <= segment:
                current.append(context(path[: i + 1], next_segment))
        elif isinstance(current, dict):
            if segment not in current or current[segment] is None:
                current[segment] = context(path[: i + 1], next_segment)
        else:
            raise ValueError("path requires an object")
        current = current[segment] if isinstance(current, list) and isinstance(segment, int) else mapping(current)[str(segment)]
    final = path[-1]
    if isinstance(final, int):
        if not isinstance(current, list):
            raise ValueError("path requires an array")
        while len(current) <= final:
            current.append(None)
    if isinstance(current, list) and isinstance(final, int):
        current[final] = copy.deepcopy(value)
    else:
        mapping(current)[str(final)] = copy.deepcopy(value)
    return result


def _concrete_path(
    path: tuple[str | int, ...],
    defaults: dict[str, object],
    schema: dict[str, object],
    data: DataObject,
) -> tuple[str | int, ...]:
    """
    Check  concrete path.

    Args:
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        defaults (dict[str, object]): Existing chart defaults that take precedence during
            coalescing.
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        data (DataObject): Hypothesis draw context for dependent values and parent containers.

    Returns:
        tuple[str | int, ...]: Result of the documented operation.
    """
    from hypothesis import strategies as st

    from hypothesis_helm.charts.model import _schema_nodes

    concrete: list[str | int] = []
    current: object = defaults
    for segment in path:
        if segment == "*":
            nodes = _schema_nodes(schema, tuple(str(p) for p in concrete), schema)
            if isinstance(current, list) or any(n.get("type") == "array" for n in nodes):
                segment = (
                    data.draw(st.integers(min_value=0, max_value=max(0, len(current) - 1))) if isinstance(current, list) and current else 0
                )
            elif isinstance(current, dict) and current:
                segment = data.draw(st.sampled_from(sorted(current)))
            else:
                patterns = [p for n in nodes for p in mapping(n.get("patternProperties", {}))]
                segment = str(data.draw(schema_strategy({"type": "string", "pattern": patterns[0]}))) if patterns else "__hypothesis_key__"
        concrete.append(segment)
        try:
            current = current[segment] if isinstance(current, list) and isinstance(segment, int) else mapping(current)[str(segment)]
        except (TypeError, KeyError, IndexError, ValueError):
            current = None
    return tuple(concrete)


def _constraint(path: tuple[str | int, ...], value: object) -> dict[str, object]:
    """
    Check  constraint.

    Args:
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        value (object): Candidate value supplied by the property strategy.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if not path:
        return {"const": value}
    head, *tail = path
    child = _constraint(tuple(tail), value)
    if isinstance(head, int):
        return {"type": "array", "minItems": head + 1, "items": [{}] * head + [child]}
    return {"type": "object", "required": [head], "properties": {head: child}}


def path_values(
    chart: Chart,
    path: tuple[str | int, ...],
    value: object,
    data: DataObject,
    *,
    generation_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    """
    Place a path value in baseline context, or draw a valid dependent context.

    The path strategy controls the candidate value. If sibling constraints make the
    baseline invalid, draw a complete schema-valid context constrained to that value.
    Impossible combinations reject that example, with normal Hypothesis health checks.

    Args:
        chart (Chart): Loaded chart and its schema and defaults.
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        value (object): Candidate value supplied by the property strategy.
        data (DataObject): Hypothesis draw context for dependent values and parent containers.
        generation_schema (dict[str, object] | None): Inferred parent types for generation;
            the original chart schema remains the validation authority.

    Returns:
        dict[str, object]: Complete values satisfying the original merged contract.
    """
    context_schema = generation_schema if generation_schema is not None else chart.schema
    path = _concrete_path(path, chart.defaults, context_schema, data)
    validator = validators.validator_for(chart.schema)(chart.schema)
    try:
        values = _replace(chart.defaults, path, value, schema=context_schema, data=data)
    except (TypeError, ValueError):
        values = {}
    if not validator.is_valid(json_value(values)):
        constrained = copy.deepcopy(chart.schema)
        sequence(constrained.setdefault("allOf", [])).append(_constraint(path, value))
        # Retain definitions at the root so existing local references still resolve.
        values = mapping(data.draw(schema_strategy(constrained), label="schema-valid context"))
    effective = merge_values(chart.defaults, values)
    assume(validator.is_valid(json_value(effective)))
    note(f"value path: {path!r}")
    note("values override:\n" + yamlio.dump(values))
    return values


def check_path(
    chart: Chart,
    path: tuple[str | int, ...],
    value: object,
    data: DataObject,
    *,
    timeout: float = 30,
    allow_empty: bool = False,
    options: RenderOptions | None = None,
) -> list[dict[str, object]]:
    """
    Render a path candidate in a context satisfying the original chart schema.

    Args:
        chart (Chart): Loaded chart and its authoritative schema and defaults.
        path (tuple[str | int, ...]): Selected symbolic value path.
        value (object): Candidate value from the path's strategy.
        data (DataObject): Hypothesis context for dependent values and wildcard selectors.
        timeout (float): Maximum seconds allowed for each Helm invocation.
        allow_empty (bool): Whether empty rendered output satisfies the contract.
        options (RenderOptions | None): Suite options overriding individual defaults.

    Returns:
        list[dict[str, object]]: Validated rendered resources for this candidate.
    """
    values = path_values(chart, path, value, data)
    dependencies = chart.dependency_model or Dependencies.build(chart.path)
    if dependencies.nodes:
        validator = validators.validator_for(chart.schema)(chart.schema)
        contexts = dependencies.contexts(
            chart.defaults, values, path, lambda candidate: validator.is_valid(json_value(merge_values(chart.defaults, candidate)))
        )
        values = data.draw(st.sampled_from(contexts), label="dependency context")
        note("dependency-aware overrides:\n" + yamlio.dump(values))
    selected = options or RenderOptions(timeout=timeout, allow_empty=allow_empty)
    try:
        resources = render(
            chart,
            values,
            timeout=selected.timeout,
            helm=selected.helm,
            release=selected.release,
            namespace=selected.namespace,
            kube_version=selected.kube_version,
        )
        if not resources and not selected.allow_empty:
            check(False, "HH1009", "chart rendered no resources")
    except RenderFailure as exc:
        if ignored(exc.code):
            raise SkipTest(f"Ignored {exc.code}: dependent checks could not run: {exc}") from exc
        raise
    return resources
