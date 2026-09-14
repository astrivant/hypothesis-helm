"""
Vary rendered tree breadth and depth while preserving the same defect triggers.
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from textwrap import dedent, indent

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path, record_change
from hypothesis_helm.schemas.contracts import mapping, sequence


def reshape_faults(path: Path, copies: int, wrappers: int, *, workspace: FixtureWorkspace | None = None) -> None:
    """
    Replicate named fault ConfigMaps and wrap them in explicit Kubernetes List resources.

    Args:
        path (Path): Logical chart with an existing fault template.
        copies (int): Sibling ConfigMap count; each copy has a unique name and identical triggers.
        wrappers (int): Number of nested List envelopes around those siblings.
        workspace (FixtureWorkspace | None): Owner of the invocation's reusable chart.

    Returns:
        None: Replace the fault template and retain a replayable shape recipe.
    """
    if not 1 <= copies <= 16 or not 0 <= wrappers <= 5:
        raise ValueError("shape requires 1..16 copies and 0..5 List wrappers")
    template = chart_path(path, workspace=workspace) / "templates/faults.yaml"
    original = template.read_text()
    resources = [original.replace("name: injected-faults", f"name: injected-faults-{index}", 1) for index in range(copies)]
    # Move the standard output into the same envelopes so depth does not change breadth
    # through accidental overlap with an unwrapped resource at another level.
    others = [item for item in sorted(template.parent.glob("*.yaml")) if item != template]
    resources.extend(item.read_text() for item in others)
    envelope = dedent("""
        apiVersion: v1
        kind: List
        items:
    """).lstrip()
    for _ in range(wrappers):
        resources = [envelope + "".join("  -\n" + indent(resource, "    ") for resource in resources)]
    template.write_text("\n---\n".join(resources))
    for item in others:
        item.unlink()
    record_change(path, "output_shape", {"copies": copies, "wrappers": wrappers}, workspace=workspace)


def fault_outputs(resources: Sequence[object]) -> Iterator[dict[str, object]]:
    """
    Visit every injected ConfigMap, including copies inside nested List envelopes.

    Args:
        resources (Sequence[object]): Parsed Helm resource documents.

    Yields:
        dict[str, object]: Per-defect output fields from each independently named copy.
    """
    for resource in resources:
        node = mapping(resource)
        if node.get("kind") == "List":
            yield from fault_outputs(sequence(node["items"]))
        elif str(mapping(node.get("metadata", {})).get("name", "")).startswith("injected-faults"):
            yield mapping(node["data"])
