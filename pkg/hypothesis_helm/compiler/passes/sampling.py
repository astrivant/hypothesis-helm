"""
Describe supported chart topology for empirical sampling calibration.
"""

import hashlib
import time

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.compiler.asts.templates import Node, value_path, walk
from hypothesis_helm.compiler.passes.complexity import measure
from hypothesis_helm.compiler.passes.pruning import Pruner, snapshot
from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.model import ValuesModel

VERSION = "sampling-topology-v1"


def fingerprint(chart: Chart) -> str:
    """
    Identify source bytes and effective contracts without including the checkout location.

    Args:
        chart (Chart): Chart snapshot used by the current visit.

    Returns:
        str: Digest shared by identical prepared charts on independent machines.
    """
    digest = hashlib.sha256(repr(sorted(snapshot(chart.path).items())).encode())
    digest.update(configuration_key({"schema": chart.schema, "defaults": chart.defaults}).encode())
    return digest.hexdigest()


def gate_depth(nodes: tuple[Node, ...], depth: int = 0) -> int:
    """
    Count the greatest number of nested conditional decisions in supported IR.

    Args:
        nodes (tuple[Node, ...]): One symbolic template block.
        depth (int): Decisions enclosing this block.

    Returns:
        int: Maximum conditional nesting depth.
    """
    return max(
        [
            depth,
            *(
                max(gate_depth(node.children, depth + (node.kind == "if")), gate_depth(node.otherwise, depth + (node.kind == "if")))
                for node in nodes
            ),
        ]
    )


def profile(chart: Chart, complexity: dict[str, object] | None = None) -> dict[str, object]:
    """
    Recompute maximum complexity and structural descriptors for one prepared chart.

    Args:
        chart (Chart): Effective chart immediately before property-test planning.
        complexity (dict[str, object] | None): Fresh result from the same audit, when already computed.

    Returns:
        dict[str, object]: Source identity, measured features and explicit uncertainty.
    """
    started = time.perf_counter()
    result: dict[str, object] = {"version": VERSION, "status": "unknown", "features": None, "fingerprint": None}
    try:
        before = fingerprint(chart)
        result["fingerprint"] = before
        measured = measure(chart) if complexity is None else complexity
        result["complexity"] = measured
        if measured["status"] != "compiled-maximum":
            raise ValueError(str(measured.get("reason", "maximum output complexity is unknown")))
        model = ValuesModel.from_schema(chart.schema)
        space = factor_space(model, 4096)
        compiler = Pruner(chart.path, chart.defaults, model)
        if compiler.disabled:
            raise ValueError(compiler.disabled)
        programs = list(compiler.programs.values())
        result["features"] = {
            "maximum_score": measured["maximum_score"],
            "input_fields": len(space.paths),
            "domain_sizes": sorted(len(domain) for domain in space.domains),
            "domain_kinds": sorted({type(value).__name__ for domain in space.domains for item in domain for value in item.values()}),
            "gate_depth": max((gate_depth(program) for program in programs), default=0),
            "interaction_order": max(
                (len({path for node in walk(program) if (path := value_path(node.text)) is not None}) for program in programs),
                default=0,
            ),
        }
        if fingerprint(chart) != before:
            raise ValueError("chart changed during sampling analysis")
        result["status"] = "supported"
    except (ValueError, OSError, RecursionError) as exc:
        result.update(status="unknown", features=None, reason=str(exc))
    result["analysis_seconds"] = time.perf_counter() - started
    return result
