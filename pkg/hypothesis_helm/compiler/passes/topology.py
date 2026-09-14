"""
Select sparse cases within statically projected output and control-flow regions.
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hypothesis_helm.compiler.asts.templates import specialize
from hypothesis_helm.compiler.passes.pruning import Pruner, safe_values
from hypothesis_helm.schemas.combinations import trim_indices
from hypothesis_helm.schemas.contracts import configuration_key, mapping
from hypothesis_helm.schemas.model import ValuesModel
from hypothesis_helm.schemas.replay import select


def trim_topology(
    chart: Path,
    defaults: dict[str, object],
    values: Sequence[dict[str, object]],
    effective: Sequence[dict[str, object]],
    steps: int,
    seed: int,
    *,
    random_steps: int = 0,
    fixed_names: bool = True,
    memberships: dict[str, str] | None = None,
) -> tuple[Sequence[dict[str, object]], dict[str, object]]:
    """
    Thin repeated symbolic regions while preserving representatives and unknown cases.

    Args:
        chart (Path): Source chart supplying schema and templates.
        defaults (dict[str, object]): Chart defaults under the fixed render context.
        values (Sequence[dict[str, object]]): Distinct non-default overrides in execution order.
        effective (Sequence[dict[str, object]]): Corresponding merged, schema-valid values.
        steps (int): Quarter-retention depth inside each projected region.
        seed (int): Reproducible selection seed shared across depths.
        random_steps (int): Additional random thinning within regions, preserving their floor.
        fixed_names (bool): Whether renderer names meet the compiler contract.
        memberships (dict[str, str] | None): Optional override-to-region output mapping.

    Returns:
        tuple[Sequence[dict[str, object]], dict[str, object]]: Selected overrides and topology evidence.
    """
    if memberships is not None:
        memberships.clear()
    trim_indices(0, steps, seed)
    trim_indices(0, random_steps, seed)
    model = ValuesModel.from_schema(mapping(json.loads((chart / "values.schema.json").read_text())))
    compiler = Pruner(chart, defaults, model)
    fallback = compiler.disabled or (None if fixed_names else "renderer names are not fixed")
    groups: dict[str, list[int]] = {}
    evidence: dict[str, dict[str, object]] = {}
    protected: list[int] = []
    for index, (overrides, merged) in enumerate(zip(values, effective, strict=True)):
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
                groups.setdefault(identity, []).append(index)
                if memberships is not None:
                    memberships[configuration_key(overrides)] = identity
                evidence[identity] = {"region": identity, "connections": connections}
                continue
        protected.append(index)
    selected = set(protected)
    regions: list[dict[str, object]] = []
    for identity, members in groups.items():
        retained = trim_indices(len(members), steps + random_steps, seed)
        selected.update(members[position] for position in retained)
        regions.append({**evidence[identity], "candidates": len(members), "retained": len(retained)})
    if not compiler.unchanged():
        fallback = "chart changed during topology analysis"
        selected = set(range(len(values)))
        if memberships is not None:
            memberships.clear()
    result = values if len(selected) == len(values) else select(values, sorted(selected))
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
