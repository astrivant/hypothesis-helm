"""
Select sparse cases within statically projected output and control-flow regions.
"""

import hashlib
import json
from pathlib import Path

from hypothesis_helm.compiler.ir import specialize
from hypothesis_helm.compiler.pruning import Pruner, safe_values
from hypothesis_helm.schemas.combinations import trim_values
from hypothesis_helm.schemas.contracts import configuration_key, mapping
from hypothesis_helm.schemas.model import ValuesModel


def trim_topology(
    chart: Path,
    defaults: dict[str, object],
    values: list[dict[str, object]],
    effective: list[dict[str, object]],
    steps: int,
    seed: int,
    *,
    random_steps: int = 0,
    fixed_names: bool = True,
    memberships: dict[str, str] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """
    Thin repeated symbolic regions while preserving representatives and unknown cases.

    Args:
        chart (Path): Source chart supplying schema and templates.
        defaults (dict[str, object]): Chart defaults under the fixed render context.
        values (list[dict[str, object]]): Distinct non-default overrides in execution order.
        effective (list[dict[str, object]]): Corresponding merged, schema-valid values.
        steps (int): Quarter-retention depth inside each projected region.
        seed (int): Reproducible selection seed shared across depths.
        random_steps (int): Additional random thinning within regions, preserving their floor.
        fixed_names (bool): Whether renderer names meet the compiler contract.
        memberships (dict[str, str] | None): Optional override-to-region output mapping.

    Returns:
        tuple[list[dict[str, object]], dict[str, object]]: Selected overrides and topology evidence.
    """
    if memberships is not None:
        memberships.clear()
    trim_values([], steps, seed)
    trim_values([], random_steps, seed)
    model = ValuesModel.from_schema(mapping(json.loads((chart / "values.schema.json").read_text())))
    compiler = Pruner(chart, defaults, model)
    fallback = compiler.disabled or (None if fixed_names else "renderer names are not fixed")
    groups: dict[str, list[dict[str, object]]] = {}
    evidence: dict[str, dict[str, object]] = {}
    protected: list[dict[str, object]] = []
    for overrides, merged in zip(values, effective, strict=True):
        projections: list[object] = []
        connections: list[dict[str, object]] = []
        if fallback is None and safe_values(defaults, overrides):
            for name, nodes in compiler.programs.items():
                output = specialize(nodes, merged, compiler.model)
                if output.reason is not None:
                    break
                projections.append((name, output.atoms, output.partition))
                connections.append(
                    {
                        "template": name,
                        "branches": [list(branch) for branch in output.partition],
                        "influences": [list(path) for path in output.influences],
                    }
                )
            else:
                identity = hashlib.sha256(configuration_key({"projection": projections}).encode()).hexdigest()
                groups.setdefault(identity, []).append(overrides)
                if memberships is not None:
                    memberships[configuration_key(overrides)] = identity
                evidence[identity] = {"region": identity, "connections": connections}
                continue
        protected.append(overrides)
    selected = list(protected)
    regions: list[dict[str, object]] = []
    for identity, members in groups.items():
        retained = trim_values(members, steps + random_steps, seed)
        selected.extend(retained)
        regions.append({**evidence[identity], "candidates": len(members), "retained": len(retained)})
    if not compiler.unchanged():
        fallback = "chart changed during topology analysis"
        selected = values
        if memberships is not None:
            memberships.clear()
    identities = {configuration_key(item) for item in selected}
    result = [item for item in values if configuration_key(item) in identities]
    return result, {
        "basis": "static symbolic output and branch regions; not observed test success",
        "regions": regions,
        "region_count": len(groups),
        "unknown_cases_retained": len(protected),
        "retained_cases": len(result),
        "omitted_cases": len(values) - len(result),
        "fallback": fallback,
        "minimum_representatives_per_region": 1,
        "coverage_guarantee": False,
    }
