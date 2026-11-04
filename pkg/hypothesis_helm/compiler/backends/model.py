"""
Define immutable, bounded finite-domain programs shared by CPU and GPU engines.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import IntEnum

from attrs import asdict, frozen
from cattrs import Converter

from hypothesis_helm.exceptions.backends import InvalidPlan

__all__ = ("DEFAULT_LIMITS", "INT64_MAX", "Factor", "Limits", "Node", "Opcode", "Plan", "State", "digest", "load_plan")

INT64_MAX = 2**63 - 1


class State(IntEnum):
    """
    Distinguish definitive input decisions from required host evaluation.

    Attributes:
        FALSE: Definitively invalid input predicate.
        TRUE: Definitively valid input predicate.
        UNKNOWN: Host evaluation is required.
    """

    FALSE = 0
    TRUE = 1
    UNKNOWN = 2


class Opcode(IntEnum):
    """
    Admit only total, pure Boolean operations and exact finite lookup tables.

    Attributes:
        CONSTANT: One constant truth state.
        LOOKUP: Exact finite dictionary lookup.
        AND: Conjunction with decisive false.
        OR: Disjunction with decisive true.
        NOT: Negation preserving unknown.
        ONE: Exactly one true operand.
    """

    CONSTANT = 0
    LOOKUP = 1
    AND = 2
    OR = 3
    NOT = 4
    ONE = 5


@frozen
class Limits:
    """
    Bound compilation, upload and per-lane work independently of Cartesian size.

    Attributes:
        nodes (int): Maximum graph nodes and per-candidate operations.
        edges (int): Maximum operand and table entries.
        depth (int): Maximum source and graph nesting.
        batch_size (int): Maximum candidate IDs in a batch.
        memory_bytes (int): Maximum combined plan, scratch and result bytes per attempt.
        plan_bytes (int): Maximum serialized plan bytes.
        timeout (float): Maximum seconds per compilation or worker request.
    """

    nodes: int = 4096
    edges: int = 262144
    depth: int = 64
    batch_size: int = 256
    memory_bytes: int = 64 * 1024 * 1024
    plan_bytes: int = 8 * 1024 * 1024
    timeout: float = 60.0


DEFAULT_LIMITS = Limits()


@frozen
class Factor:
    """
    Bind a finite dictionary to its stable path without copying values to a device.

    Attributes:
        path (tuple[str, ...]): Exact source path, including non-identifier keys.
        radix (int): Number of choices, including omission where supported.
        domain_digest (str): Digest of exact ordered typed assignments.
    """

    path: tuple[str, ...]
    radix: int
    domain_digest: str


@frozen
class Node:
    """
    Store a pure operation whose operands precede it in topological order.

    Attributes:
        op (Opcode): Allowlisted operation.
        operands (tuple[int, ...]): Earlier node indices.
        factor (int): Factor index for a lookup, otherwise -1.
        table (tuple[State, ...]): Exact per-choice truth values or one constant.
        source (str): JSON Pointer into the schema for diagnostics.
    """

    op: Opcode
    operands: tuple[int, ...] = ()
    factor: int = -1
    table: tuple[State, ...] = ()
    source: str = ""


@frozen
class Plan:
    """
    Bind a reusable program to ordered domains and an immutable host context.

    Attributes:
        context_digest (str): Caller-owned chart, dependencies, schema and renderer context identity.
        factors (tuple[Factor, ...]): Ordered finite dictionaries retained on the host.
        nodes (tuple[Node, ...]): Topologically ordered total predicate graph.
        root (int): Schema predicate result node.
        fallbacks (tuple[str, ...]): Source pointers for unsupported semantics.
        limits (Limits): Admission and execution bounds.
        version (str): Semantic and encoding version.
        encoding (str): Compact signed IDs or explicit dictionary rows for wider Cartesian spaces.
    """

    context_digest: str
    factors: tuple[Factor, ...]
    nodes: tuple[Node, ...]
    root: int
    fallbacks: tuple[str, ...] = ()
    limits: Limits = Limits()
    version: str = "PlanIR/v1"
    encoding: str = "mixed-radix-i64"

    @property
    def cardinality(self) -> int:
        """
        Return the exact Python-integer Cartesian size before fixed-width admission.

        Returns:
            int: Number of complete assignments, one for an empty factor list.
        """
        return math.prod(factor.radix for factor in self.factors)

    def encode(self) -> bytes:
        """
        Encode data canonically without native pointers or executable chart content.

        Returns:
            bytes: Stable UTF-8 representation suitable for digesting or private export.
        """
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

    @property
    def identity(self) -> str:
        """
        Identify the complete immutable plan including semantics and limits.

        Returns:
            str: SHA-256 of the canonical encoding.
        """
        return hashlib.sha256(self.encode()).hexdigest()

    def validate(self) -> None:
        """
        Reject malformed graphs and allocation bounds before any native operation.

        Returns:
            None: The program is within its declared and hard admission bounds.
        """
        limits = self.limits
        if (
            self.version != "PlanIR/v1"
            or self.encoding not in {"mixed-radix-i64", "dictionary-rows"}
            or not 0 < limits.nodes <= 16384
            or not 0 < limits.edges <= 1048576
            or not 0 < limits.depth <= 128
            or not 0 < limits.batch_size <= 16384
            or not 0 < limits.memory_bytes <= 1024**3
            or not 0 < limits.plan_bytes <= 16 * 1024**2
            or not 0 < limits.timeout <= 300
        ):
            raise InvalidPlan("unsupported plan version or limits")
        if (
            not self.nodes
            or len(self.nodes) > limits.nodes
            or len(self.factors) > limits.nodes
            or not 0 <= self.root < len(self.nodes)
            or len(self.encode()) > limits.plan_bytes
            or len(self.context_digest) != 64
        ):
            raise InvalidPlan("invalid plan identity, size or root")
        paths = [factor.path for factor in self.factors]
        if len(set(paths)) != len(paths):
            raise InvalidPlan("duplicate factor path")
        if any(factor.radix < 1 or factor.radix > limits.edges or len(factor.domain_digest) != 64 for factor in self.factors):
            raise InvalidPlan("invalid finite dictionary")
        if self.encoding == "mixed-radix-i64" and self.cardinality > INT64_MAX:
            raise InvalidPlan("assignment cardinality exceeds signed 64-bit support")
        depths: list[int] = []
        entries = 0
        for index, node in enumerate(self.nodes):
            if not isinstance(node.op, Opcode) or any(not isinstance(state, State) for state in node.table):
                raise InvalidPlan("unknown opcode or result state")
            if any(operand < 0 or operand >= index for operand in node.operands):
                raise InvalidPlan("graph contains forward, cyclic or invalid references")
            depths.append(1 + max((depths[operand] for operand in node.operands), default=0))
            entries += len(node.operands) + len(node.table)
            if depths[-1] > limits.depth or entries > limits.edges:
                raise InvalidPlan("graph exceeds depth or entry budget")
            if node.op == Opcode.CONSTANT:
                valid = len(node.table) == 1 and not node.operands and node.factor == -1
            elif node.op == Opcode.LOOKUP:
                valid = 0 <= node.factor < len(self.factors) and len(node.table) == self.factors[node.factor].radix and not node.operands
            else:
                valid = not node.table and node.factor == -1 and (node.op != Opcode.NOT or len(node.operands) == 1)
            if not valid:
                raise InvalidPlan("opcode operands do not match the declared contract")


def digest(value: object) -> str:
    """
    Hash exact JSON types and ordering without conflating Boolean and integer data.

    Args:
        value (object): JSON-compatible context or finite dictionary.

    Returns:
        str: Canonical SHA-256 identity.
    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_plan(data: bytes, context_digest: str) -> Plan:
    """
    Decode bounded untrusted data and require the current host's context identity.

    Args:
        data (bytes): UTF-8 plan data, never a pickle or native artifact.
        context_digest (str): Independently recomputed current source and execution context.

    Returns:
        Plan: Validated immutable plan matching the current context.
    """
    if len(data) > 16 * 1024**2:
        raise InvalidPlan("plan exceeds hard byte limit")
    try:
        raw = json.loads(data)
        converter = Converter(forbid_extra_keys=True, detailed_validation=False)
        plan = converter.structure(raw, Plan)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise InvalidPlan("malformed plan data") from exc
    plan.validate()
    # Canonical re-encoding rejects coercions such as bool-as-int, floats and numeric strings.
    if json.loads(plan.encode()) != raw or digest(raw) != digest(json.loads(plan.encode())):
        raise InvalidPlan("plan fields must have their exact declared JSON types")
    if plan.context_digest != context_digest:
        raise InvalidPlan("plan source/context digest is stale")
    return plan
