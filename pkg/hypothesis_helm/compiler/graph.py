"""
Export compiler references and observed Helm output without claiming opaque field causality.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, validate_resources
from hypothesis_helm.compiler.inputs import InputInventory
from hypothesis_helm.compiler.ir import fold, lower, specialize, value_path, walk
from hypothesis_helm.schemas.contracts import mapping


def export_graph(
    chart: Chart,
    target: Path | None = None,
    *,
    directory: Path = Path("."),
    helm: str = "helm",
    timeout: float = 30,
) -> dict[str, object]:
    """
    Export a JSON graph and DOT companion with static evidence and baseline manifest field paths.

    Args:
        chart (Chart): Values and templates to inspect using the shared typed input model.
        target (Path | None): Optional JSON filename.
        directory (Path): Generated-filename destination.
        helm (str): Helm executable used to observe baseline outputs.
        timeout (float): Baseline rendering timeout in seconds.

    Returns:
        dict[str, object]: Graph artifact paths, checksums, and observation status.
    """
    inventory = InputInventory.build(chart)
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    static_inventory = inventory.report()
    limitations: list[dict[str, object]] = [
        {
            **{key: value for key, value in item.items() if key in {"file", "line"}},
            "reason": "Unresolved template or schema access",
        }
        for item in inventory.unresolved
    ]
    static_inventory["unresolved"] = list(limitations)

    def node(identifier: str, kind: str, **attributes: object) -> str:
        """
        Register a stable graph node.

        Args:
            identifier (str): Namespaced identity.
            kind (str): Node category.
            **attributes (object): Evidence excluding actual input or manifest values.

        Returns:
            str: Node identifier used by edges.
        """
        nodes[identifier] = {"id": identifier, "kind": kind, **attributes}
        return identifier

    for item in inventory.fields:
        identifier = node(
            "values:" + json.dumps(item.reference.path),
            "value",
            path=list(item.reference.path),
            in_values=item.in_values,
            in_schema=item.in_schema,
        )
        for ref in item.locations:
            template = node("template:" + ref.file, "template", path=ref.file)
            edges.append(
                {
                    "from": identifier,
                    "to": template,
                    "kind": "potential-reference",
                    "line": ref.line,
                }
            )
    for path in sorted(chart.path.rglob("*")):
        if not path.is_file() or "templates" not in path.relative_to(chart.path).parts:
            continue
        relative = path.relative_to(chart.path).as_posix()
        template = node("template:" + relative, "template", path=relative)
        try:
            program = fold(lower(path.read_text()))
            output = specialize(program, chart.defaults, inventory.model)
            nodes[template]["baseline_influences_proven"] = output.reason is None
            nodes[template]["baseline_influences"] = [list(item) for item in output.influences]
            nodes[template]["baseline_partition"] = list(output.partition)
            if output.reason:
                limitations.append({"file": relative, "reason": output.reason.split(":", 1)[0]})
            for branch in walk(program):
                if branch.kind not in {"if", "opaque"}:
                    continue
                control = node(
                    f"control:{relative}:{branch.line}",
                    branch.kind,
                    line=branch.line,
                    file=relative,
                )
                edges.append({"from": control, "to": template, "kind": "control-flow"})
                selector = value_path(branch.text)
                if selector is not None:
                    value = "values:" + json.dumps(selector)
                    if value not in nodes:
                        node(value, "value", path=list(selector))
                    edges.append({"from": value, "to": control, "kind": "condition"})
        except (ValueError, UnicodeError) as exc:
            limitations.append({"file": relative, "reason": str(exc)})

    def fields(value: object, resource: str, prefix: tuple[str, ...] = ()) -> None:
        """
        Record observed field paths and types without serializing possibly secret contents.

        Args:
            value (object): Rendered subtree.
            resource (str): Owning manifest identity.
            prefix (tuple[str, ...]): Field path within that manifest.

        Returns:
            None: Field nodes and containment edges are appended.
        """
        entries = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
        for key, child in entries:
            path = (*prefix, str(key))
            field = node(
                resource + ":field:" + json.dumps(path),
                "manifest-field",
                path=list(path),
                value_type=type(child).__name__,
            )
            edges.append({"from": resource, "to": field, "kind": "contains"})
            fields(child, resource, path)

    observed: dict[str, object] = {"status": "unavailable"}
    try:
        process = subprocess.run(
            [helm, "template", "hypothesis", str(chart.path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if process.returncode:
            raise ValueError(process.stderr.strip())
        documents = yamlio.load_all(process.stdout)
        validate_resources([item for item in documents if item is not None])
        resources = 0
        for document in re.split(r"(?m)^---\s*$", process.stdout):
            parsed = yamlio.load(document)
            if parsed is None:
                continue
            manifest = mapping(parsed)
            resource = node(
                f"manifest:{resources}",
                "manifest",
                resource_kind=manifest.get("kind"),
                api_version=manifest.get("apiVersion"),
            )
            resources += 1
            source = re.search(r"(?m)^# Source: [^/]+/(.+)$", document)
            if source:
                template = "template:" + source[1]
                if template not in nodes:
                    node(template, "template", path=source[1])
                edges.append({"from": template, "to": resource, "kind": "observed-render"})
            fields(manifest, resource)
        observed = {"status": "rendered", "resources": resources}
    except (ValueError, AssertionError, OSError, subprocess.TimeoutExpired, YAMLError) as exc:
        # Do not publish raw invalid YAML or secret-bearing Helm stderr in this artifact.
        observed = {"status": "unavailable", "reason": type(exc).__name__}
    graph = {
        "version": 1,
        "nodes": list(nodes.values()),
        "edges": edges,
        "baseline": observed,
        "unresolved": limitations,
        "input_inventory": static_inventory,
        "complete_influence_map_proven": False,
        "edge_contract": "References are potential dependencies; observed-render edges describe "
        "this baseline only. No exact values-to-manifest-field causality is claimed.",
    }
    content = json.dumps(graph, indent=2) + "\n"
    checksum = hashlib.sha256(content.encode()).hexdigest()
    target = target or directory / f"topological-graph-{checksum}-{int(time.time())}.json"
    if target.suffix != ".json":
        raise ValueError("Topological graph filename must end in .json")
    protected = {(chart.path / name).resolve() for name in ("Chart.yaml", "values.yaml", "values.schema.json")}
    if target.resolve() in protected or target.is_symlink() or target.with_suffix(".dot").is_symlink():
        raise ValueError("Graph export must not overwrite source chart inputs or symbolic links")
    target.parent.mkdir(parents=True, exist_ok=True)
    dot = ["digraph helm {"]
    for identity, attributes in nodes.items():
        label = str(attributes.get("path", attributes.get("resource_kind", attributes["kind"])))
        dot.append(f"  {json.dumps(identity)} [label={json.dumps(label)}];")
    for edge in edges:
        dot.append(f"  {json.dumps(edge['from'])} -> {json.dumps(edge['to'])} [label={json.dumps(edge['kind'])}];")
    dot.append("}")
    target.write_text(content)
    target.with_suffix(".dot").write_text("\n".join(dot) + "\n")
    return {
        "json": str(target),
        "dot": str(target.with_suffix(".dot")),
        "sha256": checksum,
        "baseline": observed,
    }
