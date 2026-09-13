"""
Bound the largest rendered manifest tree across a chart's allowed values.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from collections.abc import Sequence

from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.charts.rendering import RenderFailure, validate_resources
from hypothesis_helm.compiler.asts.templates import specialize
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.finite import NonFiniteSchema, enumerate_values
from hypothesis_helm.schemas.model import ValuesModel


def maximum_score(nodes: int) -> int:
    """
    Bound breadth times depth for any tree with N nodes below its synthetic root.

    A deepest path uses D nodes; the other B-1 nodes on its widest level require
    distinct nodes. Thus B+D-1 <= N and B*D <= floor((N+1)^2/4).

    Args:
        nodes (int): Number of non-root nodes, including containers and leaves.

    Returns:
        int: Exact maximum across unrestricted trees of this size; zero for an empty tree.
    """
    if nodes < 0:
        raise ValueError("node count must be nonnegative")
    return (nodes + 1) ** 2 // 4 if nodes else 0


def output_profile(resources: Sequence[object], *, node_limit: int = 100000) -> dict[str, int]:
    """
    Score the rendered forest, counting resource roots, field values and array entries.

    Keys label edges rather than adding extra nodes. Scalars count once regardless
    of text length. Aliases are expanded by occurrence; cyclic output is unsupported.

    Args:
        resources (Sequence[object]): Parsed manifest documents, excluding empty documents.
        node_limit (int): Maximum output nodes inspected before declining analysis.

    Returns:
        dict[str, int]: Measured size, breadth, depth, score and unrestricted size ceiling.
    """
    counts: Counter[int] = Counter()
    pending: list[tuple[object, int, frozenset[int]]] = [(resource, 1, frozenset()) for resource in resources]
    visited = 0
    while pending:
        value, depth, ancestors = pending.pop()
        visited += 1
        if visited > node_limit:
            raise ValueError("manifest tree exceeds the complexity node limit")
        counts[depth] += 1
        if isinstance(value, (dict, list)):
            if id(value) in ancestors:
                raise ValueError("cyclic YAML aliases have no finite expanded tree")
            children = value.values() if isinstance(value, dict) else value
            pending.extend((child, depth + 1, ancestors | {id(value)}) for child in children)
    depth = max(counts, default=0)
    breadth = max(counts.values(), default=0)
    return {"nodes": visited, "breadth": breadth, "depth": depth, "score": breadth * depth, "size_ceiling": maximum_score(visited)}


def _compiled_resources(compiler: Pruner, effective: dict[str, object]) -> list[object]:
    """
    Materialize only the compiler's proved scalar and Boolean template subset.

    Args:
        compiler (Pruner): Chart snapshot inside the existing pure-output contract.
        effective (dict[str, object]): Admitted merged values for this candidate.

    Returns:
        list[object]: Parsed documents, before resource-envelope validation.
    """
    resources: list[object] = []
    for name, program in compiler.programs.items():
        if name.rsplit("/", 1)[-1].startswith("_") or name.endswith("/NOTES.txt"):
            continue
        output = specialize(program, effective, compiler.model)
        if output.reason:
            raise ValueError(f"{name}: {output.reason}")
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
        resources.extend(item for item in yamlio.load_all("".join(fragments)) if item is not None)
    return resources


def measure(chart: Chart, *, max_cases: int = 4096, time_limit: float = 5.0) -> dict[str, object]:
    """
    Find the greatest possible output score when the complete finite domain is supported.

    This reuses the existing compiler's strict schema, coalescing and pure-template
    contract. It does not invoke Helm or extrapolate from defaults. Any unsupported
    candidate prevents an exact maximum; completed supported candidates supply only
    a lower bound. Invalid resource envelopes do not contribute a valid output tree.

    Args:
        chart (Chart): Loaded chart, its complete values schema and defaults.
        max_cases (int): Maximum finite-domain assignments analyzed without truncation.
        time_limit (float): Budget for bounded compiler analysis, excluding chart loading.

    Returns:
        dict[str, object]: Output maximum or unknown status, evidence and explicit analysis scope.
    """
    if max_cases < 1 or not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("complexity limits must be positive")
    started = time.perf_counter()
    result: dict[str, object] = {
        "metric": "potential-manifest-breadth-depth-v1",
        "status": "unknown",
        "maximum_score": None,
        "lower_bound": None,
        "maximizing_values": None,
        "examined_configurations": 0,
        "invalid_outputs": 0,
        "limits": {"max_cases": max_cases, "seconds": time_limit},
        "scope": "Maximum breadth × depth of valid manifest trees over the declared values domain, after Helm defaults merging.",
        "context": {"release": "hypothesis", "namespace": "default"},
        "verification": "Compiled pure-template subset; no Helm invocation or Kubernetes API validation.",
        "limitations": [
            "Dependencies, dynamic template operations and open-ended input domains may prevent a finite maximum from being established.",
            "The size ceiling is a tree-shape bound, not a prediction of bugs, runtime or number of tests.",
            "An unknown maximum is not zero and does not establish unbounded output.",
        ],
    }
    try:
        compiler = Pruner(chart.path, chart.defaults, ValuesModel.from_schema(chart.schema))
        if compiler.disabled:
            raise ValueError(compiler.disabled)
        candidates = enumerate_values(chart.schema, max_cases)
        result["domain_configurations"] = len(candidates)
        best: dict[str, int] | None = None
        for values in candidates:
            if time.perf_counter() - started >= time_limit:
                raise ValueError("complexity analysis time limit reached before completing the input domain")
            effective = merge_values(chart.defaults, values)
            if compiler.candidate(values, effective, "complexity:hypothesis:default") is None:
                raise ValueError(next(reversed(compiler.reasons), "candidate is outside the supported compiler contract"))
            try:
                resources = _compiled_resources(compiler, effective)
                validate_resources(resources)
            except (YAMLError, RenderFailure):
                result["invalid_outputs"] = int(str(result["invalid_outputs"])) + 1
            else:
                profile = output_profile(resources)
                if best is None or profile["score"] > best["score"]:
                    best = profile
                    result["lower_bound"] = best
                    result["maximizing_values"] = values
            result["examined_configurations"] = int(str(result["examined_configurations"])) + 1
        if not compiler.unchanged():
            result["lower_bound"] = None
            result["maximizing_values"] = None
            raise ValueError("chart source changed during complexity analysis")
        if best is None:
            result["status"] = "no-valid-output"
        else:
            result.update({"status": "compiled-maximum", "maximum_score": best["score"], "maximum_output": best})
    except (NonFiniteSchema, ValueError, RecursionError) as exc:
        result["reason"] = str(exc) or "recursive chart could not be analyzed"
    result["analysis_seconds"] = time.perf_counter() - started
    return result


def main() -> int:
    """
    Compute a chart's potential output maximum or the mathematical ceiling for a tree size.

    Returns:
        int: Zero after emitting the structured complexity result.
    """
    from hypothesis_helm.compiler.passes.inputs import load_input_chart

    parser = argparse.ArgumentParser(description="Compute potential rendered-chart complexity with the supported compiler subset.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chart", help="Chart whose complete allowed output space should be analyzed")
    group.add_argument("--nodes", type=int, help="Compute only the unrestricted tree ceiling for this number of output nodes")
    parser.add_argument("--max-cases", type=int, default=4096)
    parser.add_argument("--time-limit", type=float, default=5.0)
    args = parser.parse_args()
    try:
        result = (
            {"nodes": args.nodes, "size_ceiling": maximum_score(args.nodes)}
            if args.nodes is not None
            else measure(load_input_chart(args.chart), max_cases=args.max_cases, time_limit=args.time_limit)
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0
