"""
Construct bounded suites covering finite schema interactions.
"""

from __future__ import annotations

import copy
import itertools
import math
import random
from collections.abc import Callable, Sequence

from attrs import define, field
from jsonschema import validators

from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.factors import factor_space
from hypothesis_helm.schemas.finite import NonFiniteSchema
from hypothesis_helm.schemas.groups import ExhaustiveGroup
from hypothesis_helm.schemas.model import ValuesModel
from hypothesis_helm.schemas.replay import Replay, select


@define
class InteractionPlan:
    """
    Store configurations and the finite factors whose interactions they cover.

    Attributes:
        values (Sequence[dict[str, object]]): Complete schema-valid configurations.
        factors (list[tuple[str, ...]]): Paths treated as independent factors.
        domains (list[Sequence[dict[str, object]]]): Per-factor assignments, including omission.
        strength (int): Effective interaction strength, capped at the factor count.
        interactions (int): Number of valid interactions covered by the suite.
        candidates (int): Complete configurations examined during planning.
        strategy (str): Full enumeration or interaction coverage with targeted groups.
        group_reports (list[dict[str, object]]): Accepted and skipped group provenance.
        raw_cases (int): Selected assignments before effective-value deduplication.
        duplicate_cases_removed (int): Assignments already covered by another configuration.
    """

    values: Sequence[dict[str, object]]
    factors: list[tuple[str, ...]]
    domains: list[Sequence[dict[str, object]]]
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
    assignments: list[int] = []

    def candidate_at(number: int) -> dict[str, object]:
        """
        Reconstruct an accepted assignment from its compact mixed-radix ID.

        Args:
            number (int): Position in the full finite Cartesian domain.

        Returns:
            dict[str, object]: Fresh configuration with the original typed object structure.
        """
        row = []
        for domain in reversed(domains):
            number, choice = divmod(number, len(domain))
            row.append(choice)
        typed_candidate = copy.deepcopy(skeleton)
        for node, domain, choice in zip(space.nodes, domains, reversed(row), strict=True):
            name = node.path[-1]
            assignment = domain[choice]
            if name in assignment:
                model.assign(typed_candidate, node, assignment[name])
        return model.unstructure(typed_candidate)

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
            number = 0
            for domain, choice in zip(domains, row, strict=True):
                number = number * len(domain) + choice
            candidate = candidate_at(number)
            if not validator.is_valid(json_value(candidate)) or (accept is not None and not accept(candidate)):
                continue
            if len(assignments) >= max_cases:
                raise NonFiniteSchema("interaction suite exceeds --max-cases")
            assignments.append(number)
            for group in groups:
                interaction = tuple((index, row[index]) for index in group)
                if interaction in uncovered:
                    uncovered.remove(interaction)
                    covered += 1
            break
        else:
            uncovered.remove(target)
    if not assignments:
        raise NonFiniteSchema("schema has no feasible configurations for permutations")
    values = Replay(len(assignments), lambda index: candidate_at(assignments[index]))
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


def trim_values(values: Sequence[dict[str, object]], steps: int, seed: int) -> Sequence[dict[str, object]]:
    """
    Retain nested seeded subsets, keeping one quarter per step rounded upward.

    Args:
        values (Sequence[dict[str, object]]): Distinct non-default planned configurations.
        steps (int): Nonnegative thinning depth; zero preserves the original order.
        seed (int): Seed shared across trim levels for reproducible nested subsets.

    Returns:
        Sequence[dict[str, object]]: Retained configurations in their original execution order.
    """
    positions = trim_indices(len(values), steps, seed)
    return values if not steps or not values else select(values, positions)


def trim_indices(size: int, steps: int, seed: int) -> Sequence[int]:
    """
    Select the historical seeded subset without constructing its configurations.

    Args:
        size (int): Available population size.
        steps (int): Quarter-retention steps.
        seed (int): Shared deterministic shuffle seed.

    Returns:
        Sequence[int]: Selected positions in original population order.
    """
    if type(steps) is not int or steps < 0:
        raise ValueError("trim must be a nonnegative integer")
    if not steps or not size:
        return range(size)
    count = size
    for _ in range(steps):
        count = (count + 3) // 4
        if count == 1:
            break
    indices = list(range(size))
    random.Random(seed).shuffle(indices)
    return sorted(indices[:count])
