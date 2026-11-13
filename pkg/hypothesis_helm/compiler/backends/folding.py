"""
Fold exact finite Boolean identities before admitting new compiler graph nodes.
"""

from __future__ import annotations

from collections.abc import Sequence

from hypothesis_helm.compiler.backends.model import Node, Opcode, State

__all__ = ("fold",)


def fold(node: Node, previous: Sequence[Node]) -> Node | int:
    """
    Simplify one valid operation without changing unknown or duplicate-oneOf semantics.

    Args:
        node (Node): Next valid lowering operation with only backward operands.
        previous (Sequence[Node]): Caller-owned immutable-prefix graph, left unchanged.

    Returns:
        Node | int: Simplified operation or an existing equivalent operand index.
    """
    if node.op == Opcode.LOOKUP and node.table and len(set(node.table)) == 1:
        return Node(Opcode.CONSTANT, table=(node.table[0],), source=node.source)
    if node.op not in {Opcode.AND, Opcode.OR, Opcode.NOT, Opcode.ONE}:
        return node
    states = [previous[index].table[0] if previous[index].op == Opcode.CONSTANT else None for index in node.operands]
    if node.op == Opcode.NOT and states[0] is not None:
        value = states[0]
        return Node(Opcode.CONSTANT, table=(State.UNKNOWN if value == State.UNKNOWN else State(value == State.FALSE),), source=node.source)

    # Decisive constants dominate unknowns; identity constants cannot remove unknowns.
    if node.op in {Opcode.AND, Opcode.OR}:
        decisive = State.FALSE if node.op == Opcode.AND else State.TRUE
        identity = State.TRUE if node.op == Opcode.AND else State.FALSE
        if decisive in states:
            return Node(Opcode.CONSTANT, table=(decisive,), source=node.source)
        operands = tuple(index for index, state in zip(node.operands, states, strict=True) if state != identity)
        if not operands:
            return Node(Opcode.CONSTANT, table=(identity,), source=node.source)
        if len(operands) == 1:
            return operands[0]
        return Node(node.op, operands=operands, source=node.source)

    # oneOf counts occurrences. Two shared TRUE operands still mean two truths.
    if node.op == Opcode.ONE:
        truths = states.count(State.TRUE)
        if truths > 1:
            return Node(Opcode.CONSTANT, table=(State.FALSE,), source=node.source)
        if all(state is not None for state in states):
            value = State.UNKNOWN if State.UNKNOWN in states else State(truths == 1)
            return Node(Opcode.CONSTANT, table=(value,), source=node.source)
    return node
