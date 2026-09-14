"""
Lower a closed, pure Go-template subset into text-preserving symbolic output.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from attrs import frozen

from hypothesis_helm.compiler.asts.lexing import SPACE
from hypothesis_helm.compiler.asts.lexing import Token as Token
from hypothesis_helm.compiler.asts.lexing import lex as lex
from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.model import ValuesModel

VALUE = re.compile(r"\.Values((?:\.[A-Za-z_][A-Za-z_0-9]*)+)\Z")


@frozen
class Node:
    """
    Represent output, a pure conditional, or an explicitly opaque action.

    Attributes:
        kind (str): Text, emit, if or opaque.
        text (str): Literal output or original expression.
        line (int): Original source location.
        children (tuple[Node, ...]): Conditional true branch.
        otherwise (tuple[Node, ...]): Conditional false branch.
    """

    kind: str
    text: str
    line: int
    children: tuple[Node, ...] = ()
    otherwise: tuple[Node, ...] = ()


def lower(source: str) -> tuple[Node, ...]:
    """
    Parse balanced blocks, retaining unsupported constructs as opaque proof barriers.

    Args:
        source (str): Complete source with literal text intact.

    Returns:
        tuple[Node, ...]: Structured symbolic output before constant folding.
    """
    tokens = lex(source)
    position = 0

    def alternatives(closing: str) -> tuple[tuple[Node, ...], str]:
        """
        Lower chained else-if syntax as nested conditional nodes sharing one end.

        Args:
            closing (str): Already consumed else or else-if action.

        Returns:
            tuple[tuple[Node, ...], str]: Alternative branch and its final terminator.
        """
        if closing == "else":
            return block()
        if closing.startswith("else if "):
            line = tokens[position - 1].line
            children, ending = block()
            tail: tuple[Node, ...] = ()
            if ending.startswith("else"):
                tail, ending = alternatives(ending)
            return (Node("if", closing[len("else if ") :], line, children, tail),), ending
        raise ValueError("unsupported alternative branch")

    def block() -> tuple[tuple[Node, ...], str]:
        """
        Consume a lexical block without interpreting unsupported commands.

        Returns:
            tuple[tuple[Node, ...], str]: Nodes and closing action, if any.
        """
        nonlocal position
        nodes: list[Node] = []
        while position < len(tokens):
            token = tokens[position]
            position += 1
            if not token.action:
                nodes.append(Node("text", token.text, token.line))
                continue
            head = token.text.split(maxsplit=1)[0] if token.text else ""
            if head in ("else", "end"):
                return tuple(nodes), token.text
            if head in ("if", "with", "range", "define", "block"):
                children, closing = block()
                otherwise: tuple[Node, ...] = ()
                supported = head == "if"
                if closing.startswith("else"):
                    otherwise, closing = alternatives(closing)
                if closing != "end":
                    raise ValueError("unbalanced or unsupported template block")
                expression = token.text[len(head) :].strip(SPACE)
                nodes.append(
                    Node(
                        "if" if supported else "opaque",
                        expression if supported else token.text,
                        token.line,
                        children,
                        otherwise,
                    )
                )
            else:
                nodes.append(Node("emit", token.text, token.line))
        return tuple(nodes), ""

    nodes, closing = block()
    if closing:
        raise ValueError("unmatched template block terminator")
    return nodes


def fold(nodes: tuple[Node, ...]) -> tuple[Node, ...]:
    """
    Propagate literal Boolean conditions and eliminate only their unreachable branches.

    Args:
        nodes (tuple[Node, ...]): Lowered template output.

    Returns:
        tuple[Node, ...]: Equivalent output with literal dead branches removed.
    """
    result: list[Node] = []
    for node in nodes:
        if node.kind == "if" and node.text in ("true", "false"):
            result.extend(fold(node.children if node.text == "true" else node.otherwise))
        else:
            result.append(Node(node.kind, node.text, node.line, fold(node.children), fold(node.otherwise)))
    return tuple(result)


def walk(nodes: tuple[Node, ...]) -> Iterator[Node]:
    """
    Traverse surviving symbolic output and control nodes.

    Args:
        nodes (tuple[Node, ...]): Folded template output.

    Yields:
        Node: Each surviving node and its nested branches.
    """
    for node in nodes:
        yield node
        yield from walk(node.children)
        yield from walk(node.otherwise)


def value_path(expression: str) -> tuple[str, ...] | None:
    """
    Recognize only direct ASCII values lookups in the proved expression subset.

    Args:
        expression (str): Complete action or condition expression.

    Returns:
        tuple[str, ...] | None: Exact field path, or an unsupported expression.
    """
    match = VALUE.fullmatch(expression)
    return tuple(match[1][1:].split(".")) if match else None


@frozen
class SymbolicOutput:
    """
    Store an exact-equality witness without pretending to implement Helm formatting.

    Attributes:
        atoms (tuple[tuple[str, str], ...]): Literal text and typed scalar output identities.
        partition (tuple[tuple[int, bool], ...]): Executed conditional decisions.
        influences (tuple[tuple[str, ...], ...]): Live input fields for this candidate.
        reason (str | None): Why output behavior could not be proved.
    """

    atoms: tuple[tuple[str, str], ...] = ()
    partition: tuple[tuple[int, bool], ...] = ()
    influences: tuple[tuple[str, ...], ...] = ()
    reason: str | None = None


def specialize(nodes: tuple[Node, ...], values: dict[str, object], model: ValuesModel) -> SymbolicOutput:
    """
    Bind candidate constants, partition Boolean control flow and project live influences.

    Equal atom sequences imply equal output bytes; unequal atoms do not imply
    unequal manifests. Opaque evaluated code never receives an equality witness.

    Args:
        nodes (tuple[Node, ...]): Folded pure template IR.
        values (dict[str, object]): Admitted, coalesced candidate values.
        model (ValuesModel): Shared schema-derived field identities.

    Returns:
        SymbolicOutput: Equality witness or an explicit unknown result.
    """
    from hypothesis_helm.compiler.asts.conditions import parse_condition

    atoms: list[tuple[str, str]] = []
    partition: list[tuple[int, bool]] = []
    influences: set[tuple[str, ...]] = set()

    def evaluate(expression: str) -> object:
        """
        Bind a proved scalar expression without emulating general template functions.

        Args:
            expression (str): Complete expression in the restricted language.

        Returns:
            object: Exact Boolean, string or integer input; unsupported cases raise.
        """
        if expression in ("true", "false"):
            return expression == "true"
        path = value_path(expression)
        if path is None or model.reference(path).target is None:
            raise ValueError(f"unsupported expression: {expression}")
        current: object = values
        for name in path:
            if not isinstance(current, dict) or name not in current:
                raise ValueError(f"missing or non-object lookup: {expression}")
            current = current[name]
        if type(current) not in (bool, int, str):
            raise ValueError(f"unsupported scalar type: {expression}")
        influences.add(path)
        return current

    def visit(items: tuple[Node, ...]) -> None:
        """
        Specialize executed branches and append exact scalar output identities.

        Args:
            items (tuple[Node, ...]): Current control-flow region.

        Returns:
            None: Output atoms, path signature and live fields are collected.
        """
        for node in items:
            if node.kind == "text":
                atoms.append(("text", node.text))
            elif node.kind == "if":
                predicate = parse_condition(node.text)
                if predicate is None:
                    raise ValueError(f"unsupported condition: {node.text}")
                condition = predicate.evaluate(evaluate)
                partition.append((node.line, condition))
                visit(node.children if condition else node.otherwise)
            elif node.kind == "emit":
                if node.text in (".Release.Name", ".Release.Namespace"):
                    # These inputs belong to the fixed execution context, not chart values.
                    atoms.append(("context", node.text))
                else:
                    atoms.append(("scalar", configuration_key({"value": evaluate(node.text)})))
            else:
                raise ValueError(f"opaque template construct at line {node.line}")

    try:
        visit(nodes)
    except ValueError as exc:
        return SymbolicOutput(reason=str(exc))
    return SymbolicOutput(tuple(atoms), tuple(partition), tuple(sorted(influences)))
