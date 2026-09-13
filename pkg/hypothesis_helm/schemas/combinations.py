"""
Construct bounded suites covering finite schema interactions.
"""

from __future__ import annotations

import copy
import itertools
import math
import random
from collections.abc import Callable

from attrs import define, field
from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.finite import NonFiniteSchema
from hypothesis_helm.schemas.groups import ExhaustiveGroup
from hypothesis_helm.schemas.model import ValuesModel


@define
class InteractionPlan:
    """
    Store configurations and the finite factors whose interactions they cover.

    Attributes:
        values (list[dict[str, object]]): Complete schema-valid configurations.
        factors (list[tuple[str, ...]]): Paths treated as independent factors.
        domains (list[list[dict[str, object]]]): Per-factor assignments, including omission.
        strength (int): Effective interaction strength, capped at the factor count.
        interactions (int): Number of valid interactions covered by the suite.
        candidates (int): Complete configurations examined during planning.
        strategy (str): Full enumeration or interaction coverage with targeted groups.
        group_reports (list[dict[str, object]]): Accepted and skipped group provenance.
        raw_cases (int): Selected assignments before effective-value deduplication.
        duplicate_cases_removed (int): Assignments already covered by another configuration.
    """

    values: list[dict[str, object]]
    factors: list[tuple[str, ...]]
    domains: list[list[dict[str, object]]]
    strength: int
    interactions: int
    candidates: int
    strategy: str = "interactions"
    group_reports: list[dict[str, object]] = field(factory=list)
    raw_cases: int = 0
    duplicate_cases_removed: int = 0


def plan_interactions(
    schema: dict[str, object] | ValuesModel,
    strength: int,
    *,
    max_cases: int = 10000,
    max_candidates: int = 100000,
    accept: Callable[[dict[str, object]], bool] | None = None,
    exhaustive_threshold: int = 10000,
    exhaustive_groups: tuple[ExhaustiveGroup, ...] = (),
    max_group_cases: int = 256,
) -> InteractionPlan:
    """
    Cover every feasible t-way assignment without materializing the Cartesian product.

    Required closed objects are flattened into leaf factors. Optional objects and
    arrays are atomic finite factors. Constraints are checked on complete inputs;
    an interaction is infeasible only after all its completions have been rejected.
    Planning limits refuse incomplete coverage before any configuration is rendered.

    Args:
        schema (dict[str, object] | ValuesModel): Shared model or finite domain schema.
        strength (int): Number of factors in each interaction to cover.
        max_cases (int): Maximum configurations and values per factor.
        max_candidates (int): Maximum complete assignments examined during planning.
        accept (Callable[[dict[str, object]], bool] | None): Additional context validation.
        exhaustive_threshold (int): Enumerate smaller Cartesian spaces; zero disables promotion.
        exhaustive_groups (tuple[ExhaustiveGroup, ...]): Required or inferred local groups.
        max_group_cases (int): Maximum Cartesian size of an inferred group.

    Returns:
        InteractionPlan: Complete coverage plan for the declared finite factors.
    """
    if strength < 1 or max_cases < 1 or max_candidates < 1:
        raise ValueError("permutations, max_cases and max_candidates must be positive")
    if exhaustive_threshold < 0 or max_group_cases < 1:
        raise ValueError("exhaustive threshold must be nonnegative and group limit positive")
    model = schema if isinstance(schema, ValuesModel) else ValuesModel.from_schema(schema)
    schema = model.root.schema
    space = factor_space(model, max_cases)
    factors, domains = space.paths, space.domains
    skeleton = model.structure(space.skeleton, validate=False)
    validator = validators.validator_for(schema)(schema)
    width = min(strength, len(factors))
    cartesian_size = math.prod(len(domain) for domain in domains)
    if cartesian_size < exhaustive_threshold and cartesian_size <= max_cases:
        width = len(factors)
    strategy = "exhaustive" if width == len(factors) else "interactions"
    # Bound the interaction inventory independently of the full Cartesian domain.
    groups = []
    inventory_size = 0
    for group in itertools.combinations(range(len(factors)), width):
        size = 1
        for index in group:
            size *= len(domains[index])
        inventory_size += size
        if inventory_size > max_candidates:
            raise NonFiniteSchema("interaction inventory exceeds --max-candidates")
        groups.append(group)
    group_reports: list[dict[str, object]] = []

    def matches_factor(index: int, prefix: tuple[str, ...]) -> bool:
        """
        Resolve a selector against a factor, checking descendants of atomic values.

        Args:
            index (int): Candidate finite factor index.
            prefix (tuple[str, ...]): User or inferred selector path.

        Returns:
            bool: Whether the selector denotes a container, factor or existing descendant.
        """
        target = model.reference(prefix).target
        if target is None:
            return False
        path = space.nodes[index].path
        return path[: len(target.path)] == target.path or target.path[: len(path)] == path

    for requested in exhaustive_groups:
        indices: set[int] = set()
        missing = []
        for prefix in requested.paths:
            matches = {index for index in range(len(factors)) if matches_factor(index, prefix)}
            if not matches:
                missing.append(list(prefix))
            indices.update(matches)
        group = tuple(sorted(indices))
        size = math.prod(len(domains[index]) for index in group)
        reason = None
        if missing:
            reason = f"selectors have no finite factors: {missing!r}"
        elif not group:
            reason = "no finite factors"
        elif strategy != "exhaustive" and not requested.explicit and size > max_group_cases:
            reason = f"group exceeds inferred group limit {max_group_cases}"
        elif strategy != "exhaustive" and group not in groups and inventory_size + size > max_candidates:
            reason = "group exceeds interaction inventory limit --max-candidates"
        if reason is not None and requested.explicit:
            raise NonFiniteSchema(f"required exhaustive group {requested.source}: {reason}")
        group_reports.append(
            {
                "source": requested.source,
                "explicit": requested.explicit,
                "factors": [list(factors[index]) for index in group],
                "candidate_assignments": size,
                "status": "skipped" if reason else "exhaustive",
                "reason": reason,
            }
        )
        if reason is None and strategy != "exhaustive" and group not in groups:
            groups.append(group)
            inventory_size += size
    uncovered = {
        tuple(zip(group, choices, strict=True))
        for group in groups
        for choices in itertools.product(*(range(len(domains[index])) for index in group))
    }
    values: list[dict[str, object]] = []
    covered = 0
    candidates = 0
    targets = iter(sorted(uncovered))
    while uncovered:
        target = next(target for target in targets if target in uncovered)
        fixed = dict(target)
        choices = [[fixed[index]] if index in fixed else range(len(domain)) for index, domain in enumerate(domains)]
        for row in itertools.product(*choices):
            candidates += 1
            if candidates > max_candidates:
                raise NonFiniteSchema("interaction completion search exceeds --max-candidates")
            typed_candidate = copy.deepcopy(skeleton)
            for node, domain, choice in zip(space.nodes, domains, row, strict=True):
                name = node.path[-1]
                if name in domain[choice]:
                    model.assign(typed_candidate, node, domain[choice][name])
            candidate = model.unstructure(typed_candidate)
            if not validator.is_valid(json_value(candidate)) or (accept is not None and not accept(candidate)):
                continue
            if len(values) >= max_cases:
                raise NonFiniteSchema("interaction suite exceeds --max-cases")
            values.append(candidate)
            for group in groups:
                interaction = tuple((index, row[index]) for index in group)
                if interaction in uncovered:
                    uncovered.remove(interaction)
                    covered += 1
            break
        else:
            uncovered.remove(target)
    if not values:
        raise NonFiniteSchema("schema has no feasible configurations for permutations")
    return InteractionPlan(
        values,
        factors,
        domains,
        width,
        covered,
        candidates,
        strategy,
        group_reports,
        raw_cases=len(values),
    )


def trim_values(values: list[dict[str, object]], steps: int, seed: int) -> list[dict[str, object]]:
    """
    Retain nested seeded subsets, keeping one quarter per step rounded upward.

    Args:
        values (list[dict[str, object]]): Distinct non-default planned configurations.
        steps (int): Nonnegative thinning depth; zero preserves the original order.
        seed (int): Seed shared across trim levels for reproducible nested subsets.

    Returns:
        list[dict[str, object]]: Retained configurations in their original execution order.
    """
    if type(steps) is not int or steps < 0:
        raise ValueError("trim must be a nonnegative integer")
    if not steps or not values:
        return values
    count = len(values)
    for _ in range(steps):
        count = (count + 3) // 4
        if count == 1:
            break
    indices = list(range(len(values)))
    random.Random(seed).shuffle(indices)
    return [values[index] for index in sorted(indices[:count])]
