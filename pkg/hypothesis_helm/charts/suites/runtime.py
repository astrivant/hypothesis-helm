"""
Runtime helpers used by generated, editable Python property tests.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import SkipTest

from attrs import frozen
from hypothesis import assume, note
from hypothesis import strategies as st
from hypothesis.strategies import DataObject
from jsonschema import validators

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.charts.values.parsers import SUITE_YAML_PARSER, validate_backend
from hypothesis_helm.compiler.passes.dependencies import Dependencies, lookup
from hypothesis_helm.compiler.randomness.model import RandomInputs
from hypothesis_helm.compiler.randomness.policy import prepare as prepare_renderer
from hypothesis_helm.compiler.randomness.rendering import enabled as random_enabled
from hypothesis_helm.exceptions.rendering import RenderFailure
from hypothesis_helm.findings.policy import RuleScope
from hypothesis_helm.findings.severity import blocks, level
from hypothesis_helm.reporting.console.logs import FindingLog, chart_name
from hypothesis_helm.rules import check, ignored
from hypothesis_helm.schemas.configuration.characters import SUITE_CHARACTER_SETS, validate_character_sets
from hypothesis_helm.schemas.configuration.selectors import SourceScope, source_identity
from hypothesis_helm.schemas.contracts import json_value, mapping, sequence
from hypothesis_helm.schemas.dialects import DRAFT2020, dialect
from hypothesis_helm.schemas.generation.strategies import schema_strategy
from hypothesis_helm.schemas.kubernetes.resources import SUITE_RESOURCE_SCHEMAS, SUITE_STRICT_SCHEMAS

__all__ = ("RenderOptions", "check_path", "path_values", "prepared_chart")


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
    metadata = generated / "chart-source.json"
    provenance = mapping(json.loads(metadata.read_text())) if metadata.is_file() else {}
    with (
        SourceScope(str(provenance.get("source", source_identity(source)))),
        ExitStack() as contracts,
        tempfile.TemporaryDirectory(prefix="hypothesis-helm-generated-") as directory,
    ):
        character_token = None
        target = Path(directory) / "chart"
        shutil.copytree(source, target)
        shutil.copyfile(generated / "values.coalesced.yaml", target / "values.yaml")
        shutil.copyfile(generated / "values.inferred.schema.json", target / "values.schema.json")
        chart = Chart.load(target)
        chart.dependency_model = Dependencies.build(target)
        snapshot = generated / "input-domains.json"
        if snapshot.is_file():
            from hypothesis_helm.schemas.generation.domains import InputDomains

            frozen = mapping(json.loads(snapshot.read_text()))
            parser_token = SUITE_YAML_PARSER.set(validate_backend(frozen.get("yaml_parser", "ruamel")))
            contracts.callback(SUITE_YAML_PARSER.reset, parser_token)
            resource_token = SUITE_RESOURCE_SCHEMAS.set(
                {**(SUITE_RESOURCE_SCHEMAS.get() or {}), **mapping(frozen.get("resource_schemas", {}))}
            )
            contracts.callback(SUITE_RESOURCE_SCHEMAS.reset, resource_token)
            strict_token = SUITE_STRICT_SCHEMAS.set(bool(frozen.get("strict", False)))
            contracts.callback(SUITE_STRICT_SCHEMAS.reset, strict_token)
            current = chart.input_domains()
            rules = [mapping(rule) for rule in sequence(frozen.get("constraints", []))]
            rules.extend(rule for rule in current.rules if rule not in rules)
            selected = validate_character_sets(frozen.get("character_sets", current.character_sets))
            generation = mapping(frozen.get("generation", current.generation))
            identity = hashlib.sha256(
                json.dumps(
                    {"rules": rules, "character_sets": selected, "generation": generation, "yaml_parser": current.yaml_parser},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            chart.domains = InputDomains(rules, current.diagnostics, identity, selected, generation, current.yaml_parser)
            character_token = SUITE_CHARACTER_SETS.set(selected)

        try:
            prepare_renderer(chart, str(provenance.get("helm", "helm")))
            yield chart
        finally:
            if character_token is not None:
                SUITE_CHARACTER_SETS.reset(character_token)


def _replace(
    values: dict[str, object],
    path: tuple[str | int, ...],
    value: object,
    *,
    schema: dict[str, object] | None = None,
    data: DataObject | None = None,
    generation: dict[str, object] | None = None,
    context_defaults: dict[str, object] | None = None,
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
        generation (dict[str, object] | None): Branch text settings for generated sibling values.
        context_defaults (dict[str, object] | None): Installed child defaults available through Helm's map merging.

    Returns:
        dict[str, object]: Resulting schema, values mapping, or structured report.
    """
    if not path:
        return copy.deepcopy(mapping(value))
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
        installed = lookup(context_defaults, prefix)
        if isinstance(installed, dict) and not isinstance(next_segment, int):
            # Helm fills omitted map siblings; do not generate or redundantly override them.
            return {}
        if isinstance(installed, list) and isinstance(next_segment, int):
            # Helm replaces arrays, so retain existing entries when changing a selected item.
            return copy.deepcopy(installed)
        if data is not None and schema is not None:
            from hypothesis_helm.charts.model import _schema_nodes

            symbolic = tuple(str(p) for p in prefix)
            nodes = _schema_nodes(schema, symbolic, schema)
            if nodes:
                fragment: dict[str, object] = {"allOf": nodes}
                fragment["$schema"] = dialect(schema)
                for key in ("$defs", "definitions"):
                    if key in schema:
                        fragment[key] = schema[key]
                return data.draw(schema_strategy(fragment, generation=generation, path=prefix), label="missing parent context")
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
        child = current[segment] if isinstance(current, list) and isinstance(segment, int) else mapping(current)[str(segment)]
        # Helm expands aliases while loading values; overriding one path must not
        # mutate another path that shared the same YAML anchor in the source.
        detached = dict(child) if isinstance(child, dict) else list(child) if isinstance(child, list) else child
        if isinstance(current, list) and isinstance(segment, int):
            current[segment] = detached
        else:
            mapping(current)[str(segment)] = detached
        current = detached
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
    generation: dict[str, object] | None = None,
) -> tuple[str | int, ...]:
    """
    Resolve wildcard entries using defaults and schema-defined container shapes.

    Args:
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        defaults (dict[str, object]): Existing chart defaults that take precedence during
            coalescing.
        schema (dict[str, object]): JSON Schema defining the accepted value domain.
        data (DataObject): Hypothesis draw context for dependent values and parent containers.
        generation (dict[str, object] | None): Branch text settings for generated collection keys.

    Returns:
        tuple[str | int, ...]: Concrete keys and array indices for a candidate that still requires full-schema validation.
    """
    from hypothesis import strategies as st

    from hypothesis_helm.charts.model import _schema_nodes

    concrete: list[str | int] = []
    current: object = defaults
    for segment in path:
        if segment == "*":
            nodes = _schema_nodes(schema, tuple(str(p) for p in concrete), schema, include_conditionals=True)
            # Nullable arrays and item-only applicators still describe array members.
            # An unknown wildcard must not erase that structural evidence.
            array = any(
                "array" in ([n["type"]] if isinstance(n.get("type"), str) else sequence(n.get("type", [])))
                or "items" in n
                or "prefixItems" in n
                for n in nodes
            )
            if isinstance(current, list) or array:
                # A wildcard beside tuple positions describes the tail, not the prefix.
                start = max(
                    (
                        len(sequence(n.get("prefixItems", n.get("items", []))))
                        for n in nodes
                        if isinstance(n.get("prefixItems", n.get("items", [])), list)
                    ),
                    default=0,
                )
                segment = (
                    data.draw(st.integers(min_value=start, max_value=max(start, len(current) - 1)))
                    if isinstance(current, list) and current
                    else start
                )
            elif isinstance(current, dict) and current:
                segment = data.draw(st.sampled_from(sorted(current)))
            else:
                patterns = [p for n in nodes for p in mapping(n.get("patternProperties", {}))]
                segment = (
                    str(data.draw(schema_strategy({"type": "string", "pattern": patterns[0]}, generation=generation, path=tuple(concrete))))
                    if patterns
                    else "__hypothesis_key__"
                )
        concrete.append(segment)
        try:
            current = current[segment] if isinstance(current, list) and isinstance(segment, int) else mapping(current)[str(segment)]
        except (TypeError, KeyError, IndexError, ValueError):
            current = None
    return tuple(concrete)


def _constraint(path: tuple[str | int, ...], value: object, *, positional_keyword: str = "items") -> dict[str, object]:
    """
    Require a candidate value at one concrete path in the selected schema dialect.

    Args:
        path (tuple[str | int, ...]): Value path or chart location to inspect.
        value (object): Candidate value supplied by the property strategy.
        positional_keyword (str): Tuple keyword supported by the validating dialect, items or prefixItems.

    Returns:
        dict[str, object]: Constraint that fixes only the selected array index and required parent fields.
    """
    if not path:
        # enum expresses exact equality in every supported draft, including Draft 4.
        return {"enum": [value]}
    head, *tail = path
    child = _constraint(tuple(tail), value, positional_keyword=positional_keyword)
    if isinstance(head, int):
        return {"type": "array", "minItems": head + 1, positional_keyword: [{} for _ in range(head)] + [child]}
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
    context_schema = generation_schema if generation_schema is not None else chart.generation_schema()
    domains = chart.input_domains()
    dependencies = chart.dependency_model
    baseline = dependencies.context(chart.defaults, {}) if dependencies is not None and dependencies.nodes else chart.defaults
    path = _concrete_path(path, baseline, context_schema, data, domains.generation)
    validator = validators.validator_for(chart.generation_schema())(chart.generation_schema())

    def effective(candidate: dict[str, object]) -> dict[str, object]:
        """
        Validate supplied overrides with the installed defaults Helm will make available.

        Args:
            candidate (dict[str, object]): Overrides being tested for schema compatibility.

        Returns:
            dict[str, object]: Candidate context including dependency defaults when present.
        """
        if dependencies is not None and dependencies.nodes:
            return merge_values(dependencies.context(chart.defaults, candidate), candidate)
        return merge_values(chart.defaults, candidate)

    needs_context = False
    try:
        values = _replace(
            chart.defaults, path, value, schema=context_schema, data=data, generation=domains.generation, context_defaults=baseline
        )
    except (TypeError, ValueError):
        values = {}
        needs_context = True
    if needs_context or not validator.is_valid(json_value(effective(values))):
        constrained = copy.deepcopy(context_schema)
        keyword = "prefixItems" if dialect(context_schema) == DRAFT2020 else "items"
        sequence(constrained.setdefault("allOf", [])).append(_constraint(path, value, positional_keyword=keyword))
        # Retain definitions at the root so existing local references still resolve.
        values = mapping(data.draw(schema_strategy(constrained, generation=domains.generation), label="schema-valid context"))
    assume(validator.is_valid(json_value(effective(values))))
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
        validator = validators.validator_for(chart.generation_schema())(chart.generation_schema())
        contexts = dependencies.contexts(
            chart.defaults,
            values,
            path,
            lambda candidate: validator.is_valid(json_value(merge_values(dependencies.context(chart.defaults, candidate), candidate))),
        )
        values = data.draw(st.sampled_from(contexts), label="dependency context")
        note("dependency-aware overrides:\n" + yamlio.dump(values))
    selected = options or RenderOptions(timeout=timeout, allow_empty=allow_empty)
    from contextlib import nullcontext

    scope = RandomInputs(lambda strategy, label: data.draw(strategy, label=label)) if random_enabled(chart) else nullcontext()
    with scope, RuleScope.for_values(chart, values):
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
                check(False, "HH1107", "chart rendered no resources")
        except RenderFailure as exc:
            if ignored(exc.code):
                raise SkipTest(f"Ignored {exc.code}: dependent checks could not run: {exc}") from exc
            from hypothesis_helm.findings.suppressions import observe

            observe(exc.code, chart.defaults, values)
            if not blocks(exc.code):
                FindingLog(chart_name(chart.path), chart.defaults, paths=(path,)).observed(exc.code, str(exc), values)
                raise SkipTest(f"Finding below failure threshold [{exc.code}] ({level(exc.code)}): {exc}") from exc
            raise
        return resources
