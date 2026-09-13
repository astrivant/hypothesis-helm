"""
Parse the shared template token stream into a scope-aware action tree.
"""

from __future__ import annotations

import re

from attrs import define, field

from hypothesis_helm.compiler.asts.lexing import lex


@define
class Action:
    """
    Represent a parsed template action and its nested branches.

    Attributes:
        text (str): Original template action text.
        line (int): One-based source line number.
        tokens (list[str]): Lexed action tokens.
        children (list[Action]): Actions in the primary branch.
        otherwise (list[Action]): Actions in the alternative branch.
    """

    text: str
    line: int
    tokens: list[str]
    children: list[Action] = field(factory=list)
    otherwise: list[Action] = field(factory=list)


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|`[^`]*`|\x27(?:\\.|[^\x27\\])*\x27|:=|[()|,=]|[^\s()|,=]+')


def parse(source: str) -> list[Action]:
    """
    Parse actions and block nesting, respecting quoted delimiters and comments.

    Args:
        source (str): Source chart location or template text.

    Returns:
        list[Action]: Result of the documented operation.
    """
    root: list[Action] = []
    current = root
    stack: list[tuple[Action, list[Action]]] = []
    for token in lex(source):
        if not token.action:
            continue
        text = token.text
        tokens = TOKEN.findall(text)
        if not tokens:
            continue
        node = Action(text, token.line, tokens)
        if tokens[0] == "end":
            if not stack:
                raise ValueError(f"unmatched end at line {node.line}")
            _, current = stack.pop()
        elif tokens[0] == "else":
            if not stack:
                raise ValueError(f"unmatched else at line {node.line}")
            current = stack[-1][0].otherwise
            if len(tokens) > 1:
                # Keep chained conditions visible; their dot context is conservatively unknown.
                current.append(Action(" ".join(tokens[1:]), node.line, tokens[1:]))
        else:
            current.append(node)
            if tokens[0] in ("if", "with", "range", "define", "block"):
                stack.append((node, current))
                current = node.children
    if stack:
        raise ValueError(f"unclosed block at line {stack[-1][0].line}")
    return root
