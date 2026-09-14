"""
Propagate lattice facts through pure branches and remove only established unreachable alternatives.
"""

from attrs import frozen

from hypothesis_helm.compiler.asts.conditions import parse_condition
from hypothesis_helm.compiler.asts.lattice import State
from hypothesis_helm.compiler.asts.templates import Node, value_path


@frozen
class BranchAnalysis:
    """
    Retain transformed output, merged knowledge and source-level decisions.

    Attributes:
        nodes (tuple[Node, ...]): Equivalent template IR under the entry assumptions.
        state (State): Knowledge valid after all surviving branches rejoin.
        decisions (tuple[dict[str, object], ...]): Predicate locations and reachability evidence.
    """

    nodes: tuple[Node, ...]
    state: State
    decisions: tuple[dict[str, object], ...] = ()


def analyze(nodes: tuple[Node, ...], state: State) -> BranchAnalysis:
    """
    Narrow each branch, merge its exit state and invalidate facts across opaque operations.

    Args:
        nodes (tuple[Node, ...]): Folded symbolic output IR.
        state (State): Conservative entry knowledge, usually derived from the schema.

    Returns:
        BranchAnalysis: Equivalent output and an auditable record of each supported decision.
    """
    output: list[Node] = []
    decisions: list[dict[str, object]] = []
    if not state.reachable:
        return BranchAnalysis((), state)
    for node in nodes:
        if node.kind == "if" and (condition := parse_condition(node.text)) is not None:
            positive = state.assume(condition, True)
            negative = state.assume(condition, False)
            left = analyze(node.children, positive)
            right = analyze(node.otherwise, negative)
            domain = state.fields.get(condition.path) if condition.path is not None else None
            decisions.append(
                {
                    "line": node.line,
                    "condition": node.text,
                    "possible_values": sorted(domain.values, key=repr) if domain is not None and domain.values is not None else None,
                    "true_reachable": positive.reachable,
                    "false_reachable": negative.reachable,
                    "action": "keep-both"
                    if positive.reachable and negative.reachable
                    else "keep-true"
                    if positive.reachable
                    else "keep-false",
                }
            )
            decisions.extend(left.decisions)
            decisions.extend(right.decisions)
            if not positive.reachable:
                output.extend(right.nodes)
            elif not negative.reachable:
                output.extend(left.nodes)
            else:
                output.append(Node(node.kind, node.text, node.line, left.nodes, right.nodes))
            state = left.state.join(right.state)
        else:
            output.append(node)
            pure = node.kind == "text" or (
                node.kind == "emit"
                and (value_path(node.text) is not None or node.text in {"true", "false", ".Release.Name", ".Release.Namespace"})
            )
            if not pure:
                # Calls, scopes and arbitrary expressions may mutate .Values.
                # Keeping their original trees also preserves errors and evaluation order.
                state = State()
    return BranchAnalysis(tuple(output), state, tuple(decisions))
