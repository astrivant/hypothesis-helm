"""
Define a deterministic topology stress fixture and its independent manifest oracle.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from attrs import asdict, evolve, frozen

from hypothesis_helm.benchmarking.charts.manifests import configmap
from hypothesis_helm.charts import yamlio
from hypothesis_helm.schemas.contracts import mapping

SIGNALS = (
    "featureEnabled",
    "backendEnabled",
    "routingEnabled",
    "storageEnabled",
    "metricsEnabled",
    "alternateBackend",
    "boundaryLowerHalf",
    "boundaryUpperHalf",
    "equivalentChoiceA",
    "equivalentChoiceB",
    "equivalentChoiceC",
    "equivalentChoiceD",
)
FAMILIES = ("constraints", "control-flow", "dependencies", "interactions", "equivalence", "boundaries")


@frozen
class Stress:
    """
    Configure topology effects while retaining the same twelve candidate input fields.

    Attributes:
        gate_depth (int): Number of nested enablement gates, zero through five.
        shared_output_count (int): Consumers of the shared backend switch, one through four.
        interaction_order (int): Simultaneous switches needed to reach the rare resource, one through five.
        equivalent_inputs (int): Inputs ignored by the output, zero through four.
        boundary_regions (int): Observable regions selected by two boundary bits, one through four.
        coupled_pairs (int): Pairs required to change together, zero through two.
        faults_enabled (bool): Inject known wrong-output markers in all six structural families.
    """

    gate_depth: int = 5
    shared_output_count: int = 4
    interaction_order: int = 5
    equivalent_inputs: int = 4
    boundary_regions: int = 4
    coupled_pairs: int = 2
    faults_enabled: bool = True

    def __attrs_post_init__(self) -> None:
        """
        Validate the bounded topology controls before writing chart files.

        Returns:
            None: All controls fit the fixed input and output structure.
        """
        bounds = {
            "gate_depth": (0, 5),
            "shared_output_count": (1, 4),
            "interaction_order": (1, 5),
            "equivalent_inputs": (0, 4),
            "boundary_regions": (1, 4),
            "coupled_pairs": (0, 2),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in {low}..{high}")
        if type(self.faults_enabled) is not bool:
            raise ValueError("faults_enabled must be Boolean")


def progression(start: Stress) -> list[tuple[str, Stress]]:
    """
    Reduce one control by one at each step without changing seeds or defect triggers.

    Args:
        start (Stress): User-selected worst-case starting configuration.

    Returns:
        list[tuple[str, Stress]]: Fixed ordered parameter sweep, starting with the combined case.
    """
    result = [("00-worst-case", start)]
    current = start
    for field, minimum in (
        ("coupled_pairs", 0),
        ("gate_depth", 0),
        ("interaction_order", 1),
        ("shared_output_count", 1),
        ("boundary_regions", 1),
        ("equivalent_inputs", 0),
    ):
        while getattr(current, field) > minimum:
            current = evolve(current, **{field: getattr(current, field) - 1})
            result.append((f"{len(result):02d}-{field.replace('_', '-')}-{getattr(current, field)}", current))
    return result


def write_stress(chart: Path, settings: Stress) -> dict[str, object]:
    """
    Compile readable topology controls into direct Helm branches that remain analyzable.

    Args:
        chart (Path): Existing twelve-input normal-quantile chart.
        settings (Stress): Combined structural controls.

    Returns:
        dict[str, object]: Exact topology, input names, and defect identifiers.
    """

    def gate(index: int) -> str:
        """
        Name a compiler-visible Boolean input.

        Args:
            index (int): Index in the fixed input inventory.

        Returns:
            str: Direct Helm values reference before readable-name lowering.
        """
        return f".Values.input{index:03d}"

    def marker(family: str, terms: list[int]) -> str:
        """
        Emit one known defect only when its fixed positive trigger is reached.

        Args:
            family (str): Stable bug identity.
            terms (list[int]): Required true inputs.

        Returns:
            str: Observable incorrect/expected marker rather than invalid YAML.
        """
        if not settings.faults_enabled:
            return "expected"
        result = "incorrect"
        for index in reversed(terms):
            result = "{{ if " + gate(index) + " }}" + result + "{{ else }}expected{{ end }}"
        return result

    templates: list[str] = []
    for family, terms in zip(FAMILIES, ([0, 1], [0, 2, 4], [1, 5], [0, 1, 2, 3, 4], [3, 5], [6, 7]), strict=True):
        templates.append(
            dedent(f"""
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: defect-{family}
        data:
          status: "{marker(family, terms)}"
        """)
        )
    nested = "\n".join("{{ if " + gate(index) + " }}" for index in range(settings.gate_depth))
    endings = "\n".join("{{ end }}" for _ in range(settings.gate_depth))
    templates.append(
        nested
        + dedent("""
    ---
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: nested-resource
    data:
      region: enabled
    """)
        + endings
        + "\n"
    )
    for index in range(settings.shared_output_count):
        templates.append(
            dedent(f"""
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: shared-consumer-{index}
        data:
          backend: "{{{{ if {gate(5)} }}}}alternate{{{{ else }}}}primary{{{{ end }}}}"
        """)
        )
    condition = "".join("{{ if " + gate(index) + " }}" for index in range(settings.interaction_order))
    closing = "{{ end }}" * settings.interaction_order
    templates.append(
        dedent(f"""
    {condition}
    ---
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: interaction-resource
    data:
      region: rare
    {closing}
    """)
    )
    for index in range(settings.equivalent_inputs, 4):
        templates.append(
            dedent(f"""
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: distinct-choice-{index}
        data:
          value: "{{{{ {gate(index + 8)} }}}}"
        """)
        )
    labels = [str(min(index, settings.boundary_regions - 1)) for index in range(4)]
    boundary = (
        "{{ if "
        + gate(7)
        + " }}{{ if "
        + gate(6)
        + " }}"
        + labels[3]
        + "{{ else }}"
        + labels[2]
        + "{{ end }}{{ else }}{{ if "
        + gate(6)
        + " }}"
        + labels[1]
        + "{{ else }}"
        + labels[0]
        + "{{ end }}{{ end }}"
    )
    templates.append(
        dedent(f"""
    ---
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: boundary-region
    data:
      region: "{boundary}"
    """)
    )
    (chart / "templates/stress.yaml").write_text("".join(templates))
    schema = mapping(json.loads((chart / "values.schema.json").read_text()))
    if settings.coupled_pairs:
        schema["allOf"] = [
            {
                "if": {"properties": {f"input{index * 2:03d}": {"const": True}}},
                "then": {"properties": {f"input{index * 2 + 1:03d}": {"const": True}}},
                "else": {"properties": {f"input{index * 2 + 1:03d}": {"const": False}}},
            }
            for index in range(settings.coupled_pairs)
        ]
    (chart / "values.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    (chart / "topology-parameters.yaml").write_text(yamlio.dump(asdict(settings)))
    return {"name": "stress", "settings": asdict(settings), "faults": list(FAMILIES)}


def valid_stress(values: dict[str, object], settings: Stress) -> bool:
    """
    Decide valid coupling assignments independently of the generated JSON schema.

    Args:
        values (dict[str, object]): Complete readable input assignment.
        settings (Stress): Fixed topology controls.

    Returns:
        bool: Whether all enabled coupling constraints hold.
    """
    return all(values[SIGNALS[index * 2]] == values[SIGNALS[index * 2 + 1]] for index in range(settings.coupled_pairs))


def stress_manifests(values: dict[str, object], settings: Stress) -> list[dict[str, object]]:
    """
    Predict complete topology resources and known defects independently of template text.

    Args:
        values (dict[str, object]): Complete readable input assignment.
        settings (Stress): Fixed topology controls.

    Returns:
        list[dict[str, object]]: Expected observed manifests, including intentional fault markers.
    """
    bits = [bool(values[name]) for name in SIGNALS]
    terms = ([0, 1], [0, 2, 4], [1, 5], [0, 1, 2, 3, 4], [3, 5], [6, 7])
    resources = [
        configmap("defect-" + family, {"status": "incorrect" if settings.faults_enabled and all(bits[i] for i in trigger) else "expected"})
        for family, trigger in zip(FAMILIES, terms, strict=True)
    ]
    if all(bits[: settings.gate_depth]):
        resources.append(configmap("nested-resource", {"region": "enabled"}))
    resources.extend(
        configmap(f"shared-consumer-{i}", {"backend": "alternate" if bits[5] else "primary"}) for i in range(settings.shared_output_count)
    )
    if all(bits[: settings.interaction_order]):
        resources.append(configmap("interaction-resource", {"region": "rare"}))
    resources.extend(configmap(f"distinct-choice-{i}", {"value": str(bits[i + 8]).lower()}) for i in range(settings.equivalent_inputs, 4))
    resources.append(configmap("boundary-region", {"region": str(min(int(bits[6]) + 2 * int(bits[7]), settings.boundary_regions - 1))}))
    return resources
