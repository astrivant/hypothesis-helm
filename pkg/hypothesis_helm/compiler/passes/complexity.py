"""
Maximize supported manifest topology using sound component bounds and deterministic search.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from collections.abc import Sequence
from pathlib import Path

from attrs import frozen
from jsonschema import validators
from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.testing.rendering import validate_resources
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.compiler.asts.conditions import condition_path
from hypothesis_helm.compiler.asts.templates import Node, specialize, value_path, walk
from hypothesis_helm.compiler.complexity import maximum_score, output_profile
from hypothesis_helm.compiler.limits import active_limits
from hypothesis_helm.compiler.lua.bounds import BoundEvaluator
from hypothesis_helm.compiler.passes.pruning import Pruner, safe_values
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.exceptions.rendering import ManifestParseError, RenderFailure
from hypothesis_helm.exceptions.schemas import NonFiniteSchema
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping
from hypothesis_helm.schemas.generation.factors import FactorSpace, factor_space
from hypothesis_helm.schemas.generation.finite import enumerate_values
from hypothesis_helm.schemas.generation.replay import select
from hypothesis_helm.schemas.model import ValuesModel

__all__ = ("Component", "OutputCase", "bound", "main", "measure")


@frozen
class OutputCase:
    """
    Retain one template's output for one assignment of its influencing factors.

    Attributes:
        choices (tuple[int, ...]): Domain indices for the component's factors.
        resources (tuple[object, ...] | None): Parsed resources, or None for an invalid envelope.
        levels (tuple[int, ...]): Number of output nodes at each one-based depth.
    """

    choices: tuple[int, ...]
    resources: tuple[object, ...] | None
    levels: tuple[int, ...]


@frozen
class Component:
    """
    Index independent output evidence by the factors that can affect this template.

    Attributes:
        factors (tuple[int, ...]): Positions in the chart's shared finite factor space.
        cases (tuple[OutputCase, ...]): Complete local table, including invalid output states.
    """

    factors: tuple[int, ...]
    cases: tuple[OutputCase, ...]


def _values(model: ValuesModel, space: FactorSpace, choices: Sequence[int]) -> dict[str, object]:
    """
    Assemble a complete assignment through the shared typed values model.

    Args:
        model (ValuesModel): Typed input model.
        space (FactorSpace): Finite domains and required object skeleton.
        choices (Sequence[int]): One domain index for each factor.

    Returns:
        dict[str, object]: Original-key overrides, preserving optional omission.
    """
    values = model.structure(space.skeleton, validate=False)
    for node, domain, index in zip(space.nodes, space.domains, choices, strict=True):
        if not node.path:
            return mapping(domain[index])
        name = node.path[-1]
        if name in domain[index]:
            model.assign(values, node, domain[index][name])
    return model.unstructure(values)


def _resources(program: tuple[Node, ...], values: dict[str, object], model: ValuesModel) -> tuple[object, ...]:
    """
    Materialize the compiler's admitted scalar and Boolean output subset.

    Args:
        program (tuple[Node, ...]): One template's folded output IR.
        values (dict[str, object]): Admitted merged values.
        model (ValuesModel): Declarations referenced by the IR.

    Returns:
        tuple[object, ...]: Parsed output documents before resource validation.
    """
    output = specialize(program, values, model)
    if output.reason:
        raise ValueError(output.reason)
    fragments = []
    for kind, text in output.atoms:
        if kind == "text":
            fragments.append(text)
        elif kind == "context":
            fragments.append("hypothesis" if text == ".Release.Name" else "default")
        elif kind == "scalar":
            value = mapping(json.loads(text))["value"]
            fragments.append(str(value).lower() if type(value) is bool else str(value))
        else:
            raise ValueError(f"unsupported output atom {kind}")
    return tuple(item for item in yamlio.load_all("".join(fragments)) if item is not None)


def _levels(resources: Sequence[object]) -> tuple[int, ...]:
    """
    Count nodes per depth after the profile checker has rejected cycles and oversized trees.

    Args:
        resources (Sequence[object]): Acyclic resource forest inside the output-size limit.

    Returns:
        tuple[int, ...]: Per-depth counts beginning with resource roots.
    """
    current = list(resources)
    result = []
    while current:
        result.append(len(current))
        current = [
            child
            for value in current
            for child in (value.values() if isinstance(value, dict) else value if isinstance(value, list) else [])
        ]
    return tuple(result)


def bound(components: Sequence[Component], assigned: dict[int, int]) -> int:
    """
    Bound every completion by summing component-wise maxima at each output depth.

    Maxima may come from incompatible rows, which can only overestimate the output.
    Shared-factor assignments restrict every component consistently. Both breadth
    and depth are monotone in these nonnegative level counts.

    Args:
        components (Sequence[Component]): Complete local output tables.
        assigned (dict[int, int]): Factor choices fixed by the current search branch.

    Returns:
        int: Admissible score upper bound, or -1 if a component has no valid completion.
    """
    totals: list[int] = []
    for component in components:
        possible = [
            case
            for case in component.cases
            if case.resources is not None
            and all(
                index not in assigned or assigned[index] == choice for index, choice in zip(component.factors, case.choices, strict=True)
            )
        ]
        if not possible:
            return -1
        depth = max((len(case.levels) for case in possible), default=0)
        totals.extend([0] * max(0, depth - len(totals)))
        for level in range(depth):
            totals[level] += max((case.levels[level] if level < len(case.levels) else 0) for case in possible)
    return max(totals, default=0) * len(totals)


def measure(chart: Chart, *, max_cases: int | None = None, time_limit: float | None = None) -> dict[str, object]:
    """
    Maximize allowed output structure using template influence tables and branch-and-bound.

    All component tables must be complete. Unsupported cases or exhausted budgets
    prevent an established maximum. Feasible full assignments are schema-checked,
    merged with defaults, and validated as complete resource bundles before they
    become witnesses. The search order and tie-breaking are deterministic.

    Args:
        chart (Chart): Loaded schema, defaults and chart source.
        max_cases (int | None): Assignments and witnesses allowed; defaults to compiler.max_complexity_cases.
        time_limit (float | None): Seconds checked between work units; defaults to compiler.max_complexity_seconds.

    Returns:
        dict[str, object]: Compiled maximum or explicit uncertainty, with search accounting.
    """
    limits = active_limits(chart.path)
    max_cases = limits["max_complexity_cases"] if max_cases is None else max_cases
    time_limit = float(limits["max_complexity_seconds"]) if time_limit is None else time_limit
    if max_cases < 1 or not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("complexity limits must be positive and finite")
    started = time.perf_counter()
    result: dict[str, object] = {
        "metric": "potential-manifest-breadth-depth-v1",
        "algorithm": "component-branch-and-bound-v1",
        "status": "unknown",
        "maximum_score": None,
        "lower_bound": None,
        "maximizing_values": None,
        "template_evaluations": 0,
        "examined_configurations": 0,
        "search_nodes": 0,
        "pruned_configurations": 0,
        "invalid_outputs": 0,
        "limits": {"max_cases": max_cases, "seconds": time_limit},
        "scope": "Maximum breadth × depth of valid manifest trees over allowed values, after Helm defaults merging.",
        "context": {"release": "hypothesis", "namespace": "default"},
        "verification": "Compiled pure-template subset; no Helm invocation or Kubernetes API validation.",
        "limitations": [
            "Unsupported schemas, dependencies, dynamic operations or incomplete component tables prevent an established maximum.",
            "The size ceiling bounds the output tree shape. Bug discovery, runtime and test count require separate analysis.",
            "Unknown does not establish unbounded output; any lower bound describes a fully checked configuration only.",
        ],
    }
    evaluated = 0

    def budget(*, evaluation: bool = False) -> None:
        """
        Check the analysis deadline and optionally charge one bounded evaluation.

        Args:
            evaluation (bool): Charge a template assignment or complete configuration.

        Returns:
            None: The next unit of work is within the configured limits.
        """
        nonlocal evaluated
        if time.perf_counter() - started >= time_limit:
            raise ValueError("complexity analysis time limit reached")
        if evaluation:
            if evaluated >= max_cases:
                raise ValueError("complexity analysis case limit reached")
            evaluated += 1

    compiler: Pruner | None = None
    bounds: BoundEvaluator | None = None
    try:
        model = ValuesModel.from_schema(chart.schema)
        compiler = Pruner(chart.path, chart.defaults, model)
        if compiler.disabled:
            raise ValueError(compiler.disabled)
        if "enum" in chart.schema or "const" in chart.schema:
            # A constrained root document is one atomic factor, not independently variable fields.
            space = FactorSpace([()], [enumerate_values(chart.schema, max_cases)], {}, [model.root])
        else:
            space = factor_space(model, max_cases)
        # Stable domain ordering also defines the canonical values for unused factors.
        for index, domain in enumerate(space.domains):
            space.domains[index] = select(domain, sorted(range(len(domain)), key=lambda position: configuration_key(domain[position])))
        sizes = [len(domain) for domain in space.domains]
        result["candidate_configurations"] = math.prod(sizes)
        base = [0] * len(sizes)
        # Coalescing safety must hold for every factor choice, including unused fields.
        for index, domain in enumerate(space.domains):
            for choice in range(len(domain)):
                budget()
                selected = [*base]
                selected[index] = choice
                if not safe_values(chart.defaults, _values(model, space, selected)):
                    raise ValueError("factor coalescing is outside the supported compiler contract")
        validator = validators.validator_for(chart.schema)(chart.schema)
        best: dict[str, int] | None = None
        baseline_checked = False
        baseline_values = _values(model, space, base)
        baseline_effective = merge_values(chart.defaults, baseline_values)
        budget(evaluation=True)
        baseline_checked = True
        result["examined_configurations"] = 1
        if validator.is_valid(json_value(baseline_values)) and validator.is_valid(json_value(baseline_effective)):
            try:
                baseline_resources = [
                    resource
                    for name, program in sorted(compiler.programs.items())
                    if not name.rsplit("/", 1)[-1].startswith("_") and not name.endswith("/NOTES.txt")
                    for resource in _resources(program, baseline_effective, model)
                ]
                validate_resources(baseline_resources)
                best = output_profile(baseline_resources, node_limit=limits["max_output_nodes"])
            except (YAMLError, RenderFailure, ValueError):
                # An opaque first candidate is not evidence about another branch.
                pass
            else:
                result["lower_bound"] = best
                result["maximizing_values"] = baseline_values
        components = []
        control_uses = [0] * len(sizes)
        for name, program in sorted(compiler.programs.items()):
            if name.rsplit("/", 1)[-1].startswith("_") or name.endswith("/NOTES.txt"):
                continue
            references = {
                path
                for node in walk(program)
                if (path := condition_path(node.text) if node.kind == "if" else value_path(node.text) if node.kind == "emit" else None)
                is not None
            }
            factors = tuple(
                index
                for index, path in enumerate(space.paths)
                if any(reference[: len(path)] == path or path[: len(reference)] == reference for reference in references)
            )
            for node in walk(program):
                path = condition_path(node.text) if node.kind == "if" else None
                if path is not None:
                    for index in factors:
                        control_uses[index] += int(path[: len(space.paths[index])] == space.paths[index])
            cases = []
            for local in itertools.product(*(range(sizes[index]) for index in factors)):
                budget(evaluation=True)
                selected = [*base]
                for index, choice in zip(factors, local, strict=True):
                    selected[index] = choice
                values = merge_values(chart.defaults, _values(model, space, selected))
                try:
                    resources = _resources(program, values, model)
                    validate_resources(resources)
                except (YAMLError, ManifestParseError, RenderFailure):
                    cases.append(OutputCase(local, None, ()))
                    result["invalid_outputs"] = int(str(result["invalid_outputs"])) + 1
                else:
                    output_profile(resources, node_limit=limits["max_output_nodes"])
                    cases.append(OutputCase(local, resources, _levels(resources)))
                result["template_evaluations"] = int(str(result["template_evaluations"])) + 1
            components.append(Component(factors, tuple(cases)))
        use_counts = [sum(index in component.factors for component in components) for index in range(len(sizes))]
        # Resolve widely shared inputs first so each choice can tighten several output bounds at once.
        order = sorted(range(len(sizes)), key=lambda index: (-use_counts[index], -control_uses[index], space.paths[index]))
        result["factor_order"] = [list(space.paths[index]) for index in order]
        result["unused_factors"] = [list(space.paths[index]) for index, count in enumerate(use_counts) if not count]
        bounds = BoundEvaluator(components, max_memory_bytes=limits["max_lua_memory_bytes"])
        pending: list[tuple[dict[int, int], int]] = [({}, bounds({}))]
        while pending:
            budget()
            assigned, upper = pending.pop()
            result["search_nodes"] = int(str(result["search_nodes"])) + 1
            if upper < 0 or (best is not None and upper <= best["score"]):
                # Every completion below this partial assignment is impossible or cannot improve the best valid result.
                result["pruned_configurations"] = (
                    int(str(result["pruned_configurations"]))
                    + math.prod(sizes[index] for index in order[len(assigned) :])
                    - int(baseline_checked and all(choice == base[index] for index, choice in assigned.items()))
                )
                continue
            if len(assigned) < len(order):
                index = order[len(assigned)]
                children = []
                for choice in range(sizes[index]):
                    budget()
                    child = {**assigned, index: choice}
                    children.append((child, bounds(child)))
                # LIFO stack visits highest bounds first, then lowest canonical domain index.
                pending.extend(sorted(children, key=lambda item: (item[1], -item[0][index])))
                continue
            if baseline_checked and all(choice == base[index] for index, choice in assigned.items()):
                continue
            budget(evaluation=True)
            result["examined_configurations"] = int(str(result["examined_configurations"])) + 1
            values = _values(model, space, [assigned[index] for index in range(len(sizes))])
            if not validator.is_valid(json_value(values)) or not validator.is_valid(json_value(merge_values(chart.defaults, values))):
                continue
            bundle = [
                resource
                for component in components
                for case in component.cases
                if case.choices == tuple(assigned[index] for index in component.factors)
                for resource in (case.resources or ())
            ]
            try:
                validate_resources(bundle)
            except RenderFailure:
                result["invalid_outputs"] = int(str(result["invalid_outputs"])) + 1
                continue
            profile = output_profile(bundle, node_limit=limits["max_output_nodes"])
            if best is None or profile["score"] > best["score"]:
                best = profile
                result["lower_bound"] = best
                result["maximizing_values"] = values
        if best is None:
            result["status"] = "no-valid-output"
        else:
            result.update({"status": "compiled-maximum", "maximum_score": best["score"], "maximum_output": best})
    except (NonFiniteSchema, ValueError, RecursionError) as exc:
        result["reason"] = str(exc) or "recursive chart could not be analyzed"
    if compiler is not None and compiler.disabled is None and not compiler.unchanged():
        result.update({"status": "unknown", "maximum_score": None, "lower_bound": None, "maximizing_values": None})
        result.pop("maximum_output", None)
        result["reason"] = "chart source changed during complexity analysis"
    result["branch_analysis"] = compiler.branch_analysis if compiler is not None else {}
    if bounds is not None:
        result["bound_backend"] = bounds.report()
    result["analysis_seconds"] = time.perf_counter() - started
    return result


def main(argv: list[str] | None = None) -> int:
    """
    Compute a chart's potential output maximum or the mathematical ceiling for a tree size.

    Args:
        argv (list[str] | None): Explicit arguments or the process command line.

    Returns:
        int: Zero after emitting the structured complexity result.
    """
    refresh_env()
    from hypothesis_helm.compiler.passes.inputs import load_input_chart

    parser = argparse.ArgumentParser(description="Compute potential rendered-chart complexity with the supported compiler subset.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chart", type=Path, help="Chart whose complete allowed output space should be analyzed")
    group.add_argument("--nodes", type=int, help="Compute only the unrestricted tree ceiling for this number of output nodes")
    parser.add_argument("--max-cases", type=int, default=4096)
    parser.add_argument("--time-limit", type=float, default=5.0)
    args = parser.parse_args(argv)
    try:
        result = (
            {"nodes": args.nodes, "size_ceiling": maximum_score(args.nodes)}
            if args.nodes is not None
            else measure(load_input_chart(args.chart), max_cases=args.max_cases, time_limit=args.time_limit)
        )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0
