"""
Generate and independently check a fixture with known downstream topology.
"""

from pathlib import Path
from textwrap import dedent

from hypothesis_helm.schemas.contracts import mapping, sequence


def write_topology(chart: Path, offset: int, opaque: bool = False) -> dict[str, object]:
    """
    Add gated resources, shared ports, replica thresholds and a rare nested region.

    Args:
        chart (Path): Generated chart directory.
        offset (int): First of six Boolean topology inputs after quantile selector bits.
        opaque (bool): Include a loop outside the symbolic compiler's supported subset.

    Returns:
        dict[str, object]: Exact input roles and oracle provenance.
    """
    roles = dict(
        zip(
            ("service", "ingress", "alternate_port", "replicas", "rare_a", "rare_b"),
            (f"input{offset + index:03d}" for index in range(6)),
            strict=True,
        )
    )
    gate = "{{ if .Values." + roles["service"] + " }}"
    ingress = "{{ if .Values." + roles["ingress"] + " }}"
    port = "{{ if .Values." + roles["alternate_port"] + " }}8080{{ else }}80{{ end }}"
    replicas = "{{ if .Values." + roles["replicas"] + " }}3{{ else }}1{{ end }}"
    rare = "{{ if .Values." + roles["rare_a"] + " }}{{ if .Values." + roles["rare_b"] + " }}"
    template = dedent(
        f"""
        {gate}
        apiVersion: v1
        kind: Service
        metadata:
          name: topology-service
        spec:
          selector:
            app: topology
          ports:
            - port: {port}
              targetPort: {port}
        {ingress}
        ---
        apiVersion: networking.k8s.io/v1
        kind: Ingress
        metadata:
          name: topology-ingress
        spec:
          defaultBackend:
            service:
              name: topology-service
              port:
                number: {port}
        {{{{ end }}}}
        {{{{ end }}}}
        ---
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: topology-workload
        spec:
          replicas: {replicas}
          selector:
            matchLabels:
              app: topology
          template:
            metadata:
              labels:
                app: topology
            spec:
              containers:
                - name: app
                  image: nginx:1.27
        {gate}
        {ingress}{rare}
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: topology-rare
        data:
          signal: rare
        {{{{ end }}}}{{{{ end }}}}{{{{ end }}}}{{{{ end }}}}
        """
    ).removeprefix("\n")
    if opaque:
        template += dedent(
            """
            {{ range until 1 }}
            ---
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: topology-opaque
            data:
              signal: loop
            {{ end }}
            """
        ).removeprefix("\n")
    (chart / "templates/topology.yaml").write_text(template)
    return {
        "roles": roles,
        "opaque": opaque,
        "rare_region_probability": 1 / 16,
        "concepts": [
            "resource gates",
            "conditional relevance",
            "shared port projection",
            "replica thresholds",
            "nested rare branch",
            "equivalent unused inputs",
        ],
        "oracle": "hypothesis_helm.benchmarking.charts.topology.validate_topology",
    }


def expected_topology(values: dict[str, object], spec: dict[str, object]) -> dict[str, object]:
    """
    Calculate expected projections independently from the template and compiler.

    Args:
        values (dict[str, object]): Effective input values.
        spec (dict[str, object]): Generator metadata including topology roles.

    Returns:
        dict[str, object]: Resource names mapped to their expected downstream projections.
    """
    topology = mapping(spec["topology"])
    roles = mapping(topology["roles"])
    enabled = {role: bool(values[str(path)]) for role, path in roles.items()}
    result: dict[str, object] = {"topology-workload": 3 if enabled["replicas"] else 1}
    port = 8080 if enabled["alternate_port"] else 80
    if enabled["service"]:
        result["topology-service"] = [port, port]
        if enabled["ingress"]:
            result["topology-ingress"] = ["topology-service", port]
            if enabled["rare_a"] and enabled["rare_b"]:
                result["topology-rare"] = "rare"
    if topology["opaque"]:
        result["topology-opaque"] = "loop"
    return result


def validate_topology(resources: list[dict[str, object]], values: dict[str, object], spec: dict[str, object]) -> None:
    """
    Assert resource presence and cross-resource projections against the independent oracle.

    Args:
        resources (list[dict[str, object]]): Actual Helm output documents.
        values (dict[str, object]): Effective Boolean inputs.
        spec (dict[str, object]): Generator metadata.

    Returns:
        None: Topology matches exactly or raises an assertion failure.
    """
    if "topology" not in spec:
        return
    received: dict[str, object] = {}
    for resource in resources:
        name = str(mapping(resource.get("metadata", {})).get("name", ""))
        if not name.startswith("topology-"):
            continue
        if name in received:
            raise AssertionError(f"duplicate topology resource: {name}")
        body = mapping(resource.get("spec", {}))
        if name == "topology-service":
            port = mapping(sequence(body["ports"])[0])
            received[name] = [port["port"], port["targetPort"]]
        elif name == "topology-ingress":
            backend = mapping(mapping(body["defaultBackend"])["service"])
            received[name] = [backend["name"], mapping(backend["port"])["number"]]
        elif name == "topology-workload":
            received[name] = body["replicas"]
        else:
            received[name] = mapping(resource["data"])["signal"]
    if received != expected_topology(values, spec):
        raise AssertionError("rendered topology differs from the independent projection oracle")
