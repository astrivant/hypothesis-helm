"""
Generate isolated structural cases and independent exact manifest oracles.
"""

import json
from pathlib import Path
from textwrap import dedent

from hypothesis_helm.benchmarking.charts.manifests import configmap as configmap
from hypothesis_helm.benchmarking.charts.workload import expected_output
from hypothesis_helm.schemas.contracts import mapping, sequence

STRUCTURES = (
    "constraints",
    "control-flow",
    "dependencies",
    "interactions",
    "equivalence",
    "boundaries",
)


def write_structure(chart: Path, name: str, offset: int, *, paths: list[str] | None = None, prefix: str = "case-") -> dict[str, object]:
    """
    Add one isolated structure while retaining the common normal-quantile observable.

    Args:
        chart (Path): Existing generated chart.
        name (str): Structural case name.
        offset (int): First input after the quantile bits.
        paths (list[str] | None): Explicit input wiring for a distributed component.
        prefix (str): Unique resource and template prefix.

    Returns:
        dict[str, object]: Structural metadata and finite domain size.
    """
    if name not in STRUCTURES:
        raise ValueError(f"unknown structure: {name}")
    schema_path = chart / "values.schema.json"
    schema = mapping(json.loads(schema_path.read_text()))
    properties = mapping(schema["properties"])
    paths = paths or [f"input{offset + bit:03d}" for bit in range(4)]
    if any(path not in properties for path in paths):
        raise ValueError("structural cases require four inputs beyond quantile selectors")
    a, b, c, d = [".Values." + path for path in paths]
    if name == "constraints":
        constraints = schema.setdefault("allOf", [])
        assert isinstance(constraints, list)
        constraints.extend(
            [
                {
                    "if": {"properties": {paths[0]: {"const": True}}},
                    "then": {"properties": {paths[1]: {"const": True}}},
                    "else": {"properties": {paths[1]: {"const": False}}},
                }
            ]
        )
        template = dedent(
            f"""
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-state
            data:
              coupled: "{{{{ {a} }}}}"
            """
        ).removeprefix("\n")
    elif name == "control-flow":
        template = dedent(
            f"""
            {{{{ if {a} }}}}
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-state
            data:
              gate: open
            {{{{ end }}}}
            {{{{ range until (ternary 3 1 {b}) }}}}
            ---
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-loop-{{{{ . }}}}
            data:
              member: present
            {{{{ end }}}}
            """
        ).removeprefix("\n")
    elif name == "dependencies":
        port = "{{ if " + a + " }}8080{{ else }}80{{ end }}"
        template = dedent(
            f"""
            apiVersion: v1
            kind: Service
            metadata:
              name: case-service
            spec:
              ports:
                - port: {port}
                  targetPort: {port}
            ---
            apiVersion: networking.k8s.io/v1
            kind: Ingress
            metadata:
              name: case-ingress
            spec:
              defaultBackend:
                service:
                  name: case-service
                  port:
                    number: {port}
            """
        ).removeprefix("\n")
    elif name == "interactions":
        template = dedent(
            """
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-state
            data:
              base: present
            """
        ).removeprefix("\n")
        template += "".join("{{ if " + path + " }}" for path in (a, b, c, d))
        template += dedent(
            f"""

            ---
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-rare
            data:
              region: rare
            {"{{ end }}" * 4}
            """
        ).removeprefix("\n")
    elif name == "equivalence":
        template = dedent(
            """
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-state
            data:
              constant: unchanged
            """
        ).removeprefix("\n")
    else:
        properties[paths[0]] = {"type": "integer", "enum": [0, 1, 2]}
        template = dedent(
            f"""
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-state
            data:
              replicas: "{{{{ {a} }}}}"
            {{{{ if ge (int {a}) 2 }}}}
            ---
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: case-boundary
            data:
              region: high
            {{{{ end }}}}
            """
        ).removeprefix("\n")
        defaults = (chart / "values.yaml").read_text().replace(paths[0] + ": false", paths[0] + ": 0")
        (chart / "values.yaml").write_text(defaults)
    schema["properties"] = properties
    schema_path.write_text(json.dumps(schema, indent=2) + "\n")
    filename = "structure.yaml" if prefix == "case-" else f"structure-{prefix.rstrip('-')}.yaml"
    (chart / "templates" / filename).write_text(template.replace("case-", prefix))
    return {
        "name": name,
        "paths": paths,
        "prefix": prefix,
        "oracle": "hypothesis_helm.benchmarking.charts.structures.expected_manifests",
    }


def valid_assignment(values: dict[str, object], spec: dict[str, object]) -> bool:
    """
    Independently decide the fixture's cross-input constraint.

    Args:
        values (dict[str, object]): Complete candidate assignment.
        spec (dict[str, object]): Generator metadata.

    Returns:
        bool: Assignment is allowed by the fixture contract.
    """
    structure = mapping(spec["structure"])
    if structure["name"] == "error-surface":
        return True
    if structure["name"] == "stress":
        import cattrs

        from hypothesis_helm.benchmarking.charts.stress import Stress, valid_stress

        return valid_stress(values, cattrs.structure(structure["settings"], Stress))
    if structure["name"] == "mixed":
        components = structure["components"]
        assert isinstance(components, list)
        return all(valid_assignment(values, {**spec, "structure": item}) for item in components)
    paths = structure["paths"]
    assert isinstance(paths, list)
    return structure["name"] != "constraints" or values[str(paths[0])] == values[str(paths[1])]


def expected_manifests(values: dict[str, object], spec: dict[str, object]) -> list[dict[str, object]]:
    """
    Calculate exact expected outputs for each structural fixture.

    Args:
        values (dict[str, object]): Complete valid input assignment.
        spec (dict[str, object]): Generator metadata.

    Returns:
        list[dict[str, object]]: Full expected manifest bundle, independent of Helm and compiler.
    """
    structure = mapping(spec["structure"])
    if structure["name"] == "error-surface":
        from hypothesis_helm.benchmarking.charts.error_surface import surface_manifests

        return surface_manifests(values, spec)
    if structure["name"] == "stress":
        import cattrs

        from hypothesis_helm.benchmarking.charts.stress import Stress, stress_manifests

        return [
            configmap("matrix", {"value": expected_output(values, spec)}),
            *stress_manifests(values, cattrs.structure(structure["settings"], Stress)),
        ]
    if any(not values[str(path)] for path in sequence(structure.get("gate_paths", []))):
        return [configmap("matrix", {"value": expected_output(values, spec)})]
    if structure["name"] == "mixed":
        components = structure["components"]
        assert isinstance(components, list)
        return [
            configmap("matrix", {"value": expected_output(values, spec)}),
            *(resource for item in components for resource in expected_manifests(values, {**spec, "structure": item})[1:]),
        ]
    paths = structure["paths"]
    assert isinstance(paths, list)
    a, b, c, d = [values[str(path)] for path in paths]
    result = [configmap("matrix", {"value": expected_output(values, spec)})]
    match structure["name"]:
        case "constraints":
            result.append(configmap("case-state", {"coupled": str(a).lower()}))
        case "control-flow":
            if a:
                result.append(configmap("case-state", {"gate": "open"}))
            result.extend(configmap(f"case-loop-{index}", {"member": "present"}) for index in range(3 if b else 1))
        case "dependencies":
            port = 8080 if a else 80
            result.extend(
                [
                    {
                        "apiVersion": "v1",
                        "kind": "Service",
                        "metadata": {"name": "case-service"},
                        "spec": {"ports": [{"port": port, "targetPort": port}]},
                    },
                    {
                        "apiVersion": "networking.k8s.io/v1",
                        "kind": "Ingress",
                        "metadata": {"name": "case-ingress"},
                        "spec": {"defaultBackend": {"service": {"name": "case-service", "port": {"number": port}}}},
                    },
                ]
            )
        case "interactions":
            result.append(configmap("case-state", {"base": "present"}))
            if a and b and c and d:
                result.append(configmap("case-rare", {"region": "rare"}))
        case "equivalence":
            result.append(configmap("case-state", {"constant": "unchanged"}))
        case "boundaries":
            result.append(configmap("case-state", {"replicas": str(a)}))
            if int(str(a)) >= 2:
                result.append(configmap("case-boundary", {"region": "high"}))
        case _:
            raise ValueError("unknown structural oracle")
    return [mapping(item) for item in sequence(json.loads(json.dumps(result).replace("case-", str(structure.get("prefix", "case-")))))]
