"""
Place a fixed Boolean problem inside large values trees without changing its domain.
"""

import json
import random
from pathlib import Path
from textwrap import dedent

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path, record_change
from hypothesis_helm.charts import yamlio
from hypothesis_helm.schemas.contracts import mapping, sequence

PLACEMENTS = ("near", "split", "far", "disconnected")


def read(values: dict[str, object], path: list[str]) -> bool:
    """
    Resolve a known Boolean leaf independently of Helm.

    Args:
        values (dict[str, object]): Complete fixture configuration.
        path (list[str]): Nested field names.

    Returns:
        bool: Leaf value.
    """
    current: object = values
    for key in path:
        current = mapping(current)[key]
    return bool(current)


def expected(values: dict[str, object], spec: dict[str, object]) -> list[dict[str, object]]:
    """
    Define two fixed pairwise defects and their resource projections.

    Args:
        values (dict[str, object]): Complete values tree.
        spec (dict[str, object]): Active paths and projection grouping.

    Returns:
        list[dict[str, object]]: Exact expected manifests, including deliberately incorrect statuses.
    """
    settings = mapping(spec["structural_sparsity"])
    paths = [[str(key) for key in sequence(path)] for path in sequence(settings["active_paths"])]
    bits = [read(values, path) for path in paths]
    resources: list[dict[str, object]] = []
    for index, pair in enumerate(((0, 3), (1, 2))):
        visible = pair if settings["placement"] == "disconnected" else tuple(range(4))
        data = {f"signal{bit}": str(bits[bit]).lower() for bit in visible}
        data["status"] = "incorrect" if all(bits[bit] for bit in pair) else "expected"
        resources.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": f"defect-{index}"}, "data": data})
    return resources


def configure(logical: Path, breadth: int, depth: int, placement: str, seed: int, *, workspace: FixtureWorkspace | None = None) -> None:
    """
    Reconfigure the shared chart, retaining its recipe for replay.

    Args:
        logical (Path): Generated chart identity.
        breadth (int): Number of root branches, each with four terminal fields.
        depth (int): Number of intermediate maps per branch.
        placement (str): Near, split, far, or disconnected resource projections.
        seed (int): Reproducible choice of branch identities.
        workspace (FixtureWorkspace | None): Owner of the single disposable chart.

    Returns:
        None: Writes schema, values, templates and structural metrics.
    """
    if breadth < 4 or not 0 <= depth <= 64 or placement not in PLACEMENTS:
        raise ValueError("require breadth >= 4, depth 0..64, and a known placement")
    chart = chart_path(logical, workspace=workspace)
    branches = random.Random(seed).sample(range(breadth), 4)
    groups = [0, 0, 0, 0] if placement == "near" else [0, 0, 1, 1] if placement == "split" else [0, 1, 2, 3]
    paths = [
        [f"branch{branches[group]:04d}", *(f"level{level:02d}" for level in range(depth)), f"signal{index}"]
        for index, group in enumerate(groups)
    ]
    active = {tuple(path) for path in paths}
    values: dict[str, object] = {}
    schema: dict[str, object] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    for branch in range(breadth):
        prefix = [f"branch{branch:04d}", *(f"level{level:02d}" for level in range(depth))]
        value_cursor, schema_cursor = values, schema
        for key in prefix:
            value_cursor = mapping(value_cursor.setdefault(key, {}))
            sequence(schema_cursor["required"]).append(key)
            child: dict[str, object] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
            mapping(schema_cursor["properties"])[key] = child
            schema_cursor = child
        for index in range(4):
            key = f"signal{index}"
            value_cursor[key] = False
            sequence(schema_cursor["required"]).append(key)
            mapping(schema_cursor["properties"])[key] = {
                "type": "boolean",
                "enum": [False, True] if tuple([*prefix, key]) in active else [False],
            }
    distances = []
    for left in range(4):
        for right in range(left + 1, 4):
            common = 0
            for a, b in zip(paths[left], paths[right], strict=True):
                if a != b:
                    break
                common += 1
            distances.append(len(paths[left]) + len(paths[right]) - 2 * common)
    settings: dict[str, object] = {
        "breadth": breadth,
        "depth": depth,
        "placement": placement,
        "seed": seed,
        "active_paths": paths,
        "value_nodes": 1 + breadth * (depth + 5),
        "value_leaves": breadth * 4,
        "active_density": 4 / (1 + breadth * (depth + 5)),
        "mean_path_distance": sum(distances) / len(distances),
        "max_path_distance": max(distances),
        "projection_components": 2 if placement == "disconnected" else 1,
        "variable_fields": 4,
        "valid_inputs": 16,
        "erroneous_inputs": 7,
        "defects": 2,
    }
    spec_path = chart / "benchmark.json"
    spec = mapping(json.loads(spec_path.read_text()))
    spec.update(structural_sparsity=settings, structure={"name": "structural-sparsity"})
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    (chart / "values.yaml").write_text(yamlio.dump(values))
    (chart / "values.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    for template in (chart / "templates").glob("*"):
        if template.is_file():
            template.unlink()
    documents = []
    for index, pair in enumerate(((0, 3), (1, 2))):
        visible = pair if placement == "disconnected" else tuple(range(4))
        header = dedent(f"""
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: defect-{index}
            data:
            """)
        lines = [header.rstrip()]
        for bit in visible:
            lines.append(f'  signal{bit}: "{{{{ if .Values.{".".join(paths[bit])} }}}}true{{{{ else }}}}false{{{{ end }}}}"')
        left_path, right_path = (".".join(paths[bit]) for bit in pair)
        lines.append(
            f'  status: "{{{{ if .Values.{left_path} }}}}{{{{ if .Values.{right_path} }}}}incorrect{{{{ else }}}}expected{{{{ end }}}}'
            '{{ else }}expected{{ end }}"'
        )
        documents.append("\n".join(lines))
    (chart / "templates/sparsity.yaml").write_text("\n---\n".join(documents) + "\n")
    record_change(
        logical, "structural_sparsity", {"breadth": breadth, "depth": depth, "placement": placement, "seed": seed}, workspace=workspace
    )
