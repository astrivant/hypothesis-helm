"""
Lower finite schema predicates into exact dictionary tables and a pure Boolean DAG.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from jsonschema import validators

from hypothesis_helm.compiler.backends.model import DEFAULT_LIMITS, Factor, Limits, Node, Opcode, Plan, State, digest
from hypothesis_helm.exceptions.backends import InvalidPlan
from hypothesis_helm.schemas.contracts import json_value
from hypothesis_helm.schemas.generation.factors import FactorSpace

__all__ = ("compile_plan",)

ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "default", "examples", "deprecated", "readOnly", "writeOnly"}
SCALARS = {"type", "enum", "const", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}


def compile_plan(
    schema: dict[str, object],
    space: FactorSpace,
    *,
    context_digest: str | None = None,
    limits: Limits = DEFAULT_LIMITS,
    clock: Callable[[], float] = time.monotonic,
    encoding: str = "mixed-radix-i64",
) -> Plan:
    """
    Compile once per finite context without enumerating the Cartesian domain.

    Finite leaf tables preserve JSON Schema Boolean/integer/null semantics on the
    host. Device code sees dictionary indices and total truth operations only.
    Unsupported fragments remain UNKNOWN; they cannot authorize a successful test.

    Args:
        schema (dict[str, object]): Validated canonical input schema.
        space (FactorSpace): Existing planner's ordered finite dictionaries and skeleton.
        context_digest (str | None): Source/context identity; defaults to schema and skeleton.
        limits (Limits): Independent compilation and execution bounds.
        clock (Callable[[], float]): Monotonic deadline source owned by orchestration.
        encoding (str): Compact finite IDs or explicit factor dictionary rows.

    Returns:
        Plan: Validated pure program with explicit source-mapped host fallbacks.
    """
    started = clock()
    nodes: list[Node] = []
    fallbacks: list[str] = []
    indices = {path: index for index, path in enumerate(space.paths)}
    validator = validators.validator_for(schema)(schema)
    entries = 0

    def append(node: Node) -> int:
        """
        Admit one node under independent work, memory and deadline bounds.

        Args:
            node (Node): Immutable next operation.

        Returns:
            int: Stable topological node index.
        """
        nonlocal entries
        entries += len(node.operands) + len(node.table)
        if len(nodes) >= limits.nodes or entries > limits.edges or clock() - started > limits.timeout:
            raise InvalidPlan("plan compilation exceeded its node, entry or time budget")
        nodes.append(node)
        return len(nodes) - 1

    def constant(state: State, source: str) -> int:
        """
        Retain constant semantics and source mapping.

        Args:
            state (State): Known truth or host fallback.
            source (str): Schema location.

        Returns:
            int: Constant node index.
        """
        if state == State.UNKNOWN:
            fallbacks.append(source)
        return append(Node(Opcode.CONSTANT, table=(state,), source=source))

    def present(path: tuple[str, ...], source: str) -> int:
        """
        Distinguish omitted choices from present null and false values.

        Args:
            path (tuple[str, ...]): Exact property path.
            source (str): Required-property assertion location.

        Returns:
            int: Presence predicate node.
        """
        if path in indices:
            index = indices[path]
            table = tuple(State.TRUE if path[-1] in value else State.FALSE for value in space.domains[index])
            return append(Node(Opcode.LOOKUP, factor=index, table=table, source=source))
        value: object = space.skeleton
        for name in path:
            if not isinstance(value, dict) or name not in value:
                return constant(State.FALSE, source)
            value = value[name]
        return constant(State.TRUE, source)

    def lower(fragment: object, path: tuple[str, ...], source: str, depth: int) -> int:
        """
        Lower only proven schema operations, preserving unknown branches.

        Args:
            fragment (object): A Boolean or mapping schema fragment.
            path (tuple[str, ...]): Instance location within the immutable factor space.
            source (str): Schema pointer for diagnostics.
            depth (int): Source traversal depth.

        Returns:
            int: Topological result node for this fragment.
        """
        if depth > limits.depth:
            raise InvalidPlan("schema exceeds compilation depth")
        if isinstance(fragment, bool):
            return constant(State.TRUE if fragment else State.FALSE, source)
        if not isinstance(fragment, dict):
            return constant(State.UNKNOWN, source)
        results: list[int] = []
        scalar = {key: value for key, value in fragment.items() if key in SCALARS}
        if path in indices and scalar:
            index = indices[path]
            table: list[State] = []
            for assignment in space.domains[index]:
                value = assignment.get(path[-1])
                # Collections and nonfinite-width numerical values retain their host route.
                if isinstance(value, (dict, list, float)) or (type(value) is int and not -(2**63) <= value < 2**63):
                    state = State.UNKNOWN
                else:
                    state = (
                        State.TRUE
                        if path[-1] not in assignment or validator.evolve(schema=scalar).is_valid(json_value(value))
                        else State.FALSE
                    )
                table.append(state)
                if clock() - started > limits.timeout:
                    raise InvalidPlan("finite dictionary compilation exceeded time budget")
            if State.UNKNOWN in table:
                fallbacks.append(source)
            results.append(append(Node(Opcode.LOOKUP, factor=index, table=tuple(table), source=source)))
        elif scalar:
            # Only the required object skeleton is statically known away from atomic factors.
            value = space.skeleton
            for name in path:
                value = value.get(name) if isinstance(value, dict) else None
            if scalar == {"type": "object"} and isinstance(value, dict):
                results.append(constant(State.TRUE, source))
            else:
                results.append(constant(State.UNKNOWN, source))
        for key, value in fragment.items():
            location = source + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key in ANNOTATIONS or key in SCALARS or key in {"then", "else"}:
                continue
            if key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
                operands = tuple(lower(child, path, location + f"/{i}", depth + 1) for i, child in enumerate(value))
                op = {"allOf": Opcode.AND, "anyOf": Opcode.OR, "oneOf": Opcode.ONE}[key]
                results.append(append(Node(op, operands, source=location)))
            elif key == "not":
                results.append(append(Node(Opcode.NOT, (lower(value, path, location, depth + 1),), source=location)))
            elif key == "if":
                condition = lower(value, path, location, depth + 1)
                yes = lower(fragment.get("then", True), path, source + "/then", depth + 1)
                no = lower(fragment.get("else", True), path, source + "/else", depth + 1)
                inverse = append(Node(Opcode.NOT, (condition,), source=location))
                left = append(Node(Opcode.AND, (condition, yes), source=location))
                right = append(Node(Opcode.AND, (inverse, no), source=location))
                results.append(append(Node(Opcode.OR, (left, right), source=location)))
            elif key == "properties" and isinstance(value, dict) and path not in indices:
                for name, child in value.items():
                    child_path = (*path, str(name))
                    child_source = location + "/" + str(name).replace("~", "~0").replace("/", "~1")
                    exists = present(child_path, child_source)
                    absent = append(Node(Opcode.NOT, (exists,), source=child_source))
                    check = lower(child, child_path, child_source, depth + 1)
                    results.append(append(Node(Opcode.OR, (absent, check), source=child_source)))
            elif key == "required" and isinstance(value, list) and path not in indices:
                results.extend(present((*path, str(name)), location) for name in value)
            elif key == "additionalProperties" and value is True:
                continue
            elif key == "additionalProperties" and value is False and path not in indices:
                # A fragment can narrow properties relative to the enclosing declaration.
                declared = fragment.get("properties", {})
                names = set(declared) if isinstance(declared, dict) else set()
                children = {item[len(path)] for item in space.paths if item[: len(path)] == path and len(item) > len(path)}
                skeleton: object = space.skeleton
                for name in path:
                    skeleton = skeleton.get(name) if isinstance(skeleton, dict) else None
                if isinstance(skeleton, dict):
                    children.update(skeleton)
                results.extend(
                    append(Node(Opcode.NOT, (present((*path, name), location),), source=location)) for name in sorted(children - names)
                )
            else:
                results.append(constant(State.UNKNOWN, location))
        return append(Node(Opcode.AND, tuple(results), source=source))

    root = lower(schema, (), "", 0)
    factors = tuple(
        Factor(path, len(domain), digest([json_value(value) for value in domain]))
        for path, domain in zip(space.paths, space.domains, strict=True)
    )
    plan = Plan(
        context_digest or digest([schema, space.skeleton]),
        factors,
        tuple(nodes),
        root,
        tuple(sorted(set(fallbacks))),
        limits,
        encoding=encoding,
    )
    plan.validate()
    return plan
