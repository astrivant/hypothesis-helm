"""
Small Go-template action AST and conservative, scope-aware value discovery.

This is an analyzer, not a Go-template interpreter. Helm remains the renderer.
Unknown contexts are represented by None, never silently treated as the root.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from attrs import define, field

from hypothesis_helm.charts import tpl, yamlio


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


@define(frozen=True)
class Reference:
    """
    Record a resolved value path and its template source location.

    Attributes:
        path (tuple[str, ...]): Resolved value path or chart location.
        file (str): Chart-relative template filename.
        line (int): One-based source line number.
        fallback (bool): Whether the action contains a fallback expression.
    """

    path: tuple[str, ...]
    file: str
    line: int
    fallback: bool = False


@define(frozen=True)
class Diagnostic:
    """
    Describe a template construct requiring manual review.

    Attributes:
        file (str): Chart-relative template filename.
        line (int): One-based source line number.
        message (str): Human-readable diagnostic detail.
    """

    file: str
    line: int
    message: str


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
    pos = 0
    while (start := source.find("{{", pos)) >= 0:
        i = start + 2
        quote = None
        comment = False
        while i < len(source):
            if comment:
                if source.startswith("*/", i):
                    comment = False
                    i += 2
                else:
                    i += 1
                continue
            char = source[i]
            if quote:
                if char == "\\" and quote != "`":
                    i += 2
                    continue
                if char == quote:
                    quote = None
            elif source.startswith("/*", i):
                comment = True
                i += 2
                continue
            elif char in ('"', "`", "'"):
                quote = char
            elif source.startswith("}}", i):
                break
            i += 1
        if i >= len(source):
            raise ValueError(f"unterminated template action at line {source.count(chr(10), 0, start) + 1}")
        text = source[start + 2 : i].strip()
        if text.startswith("-"):
            text = text[1:].lstrip()
        if text.endswith("-"):
            text = text[:-1].rstrip()
        pos = i + 2
        if text.startswith("/*"):
            continue
        tokens = TOKEN.findall(text)
        if not tokens:
            continue
        node = Action(text, source.count("\n", 0, start) + 1, tokens)
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


def discover(path: Path, *, prune_literals: bool = False) -> tuple[list[Reference], list[Diagnostic]]:
    """
    Resolve direct fields, aliases, with/range scopes, and literal key access.

    Args:
        path (Path): Value path or chart location to inspect.
        prune_literals (bool): Skip branches controlled by literal true/false conditions.

    Returns:
        tuple[list[Reference], list[Diagnostic]]: Result of the documented operation.
    """
    values_file = path / "values.yaml"
    defaults = yamlio.load(values_file.read_text()) if values_file.is_file() else {}
    active_tpl: set[tuple[str, tuple[str, ...] | None]] = set()
    refs: list[Reference] = []
    diagnostics: list[Diagnostic] = []
    for file in sorted((path / "templates").rglob("*")):
        if not file.is_file():
            continue
        name = str(file.relative_to(path))
        try:
            nodes = parse(file.read_text())
        except ValueError as exc:
            diagnostics.append(Diagnostic(name, 1, str(exc)))
            continue

        def walk(
            nodes: list[Action],
            dot: tuple[str, ...] | None,
            env: dict[str, tuple[str, ...] | None],
            source_name: str = name,
        ) -> None:
            """
            Resolve value references in the current lexical scope.

            Args:
                nodes (list[Action]): Template actions to inspect in lexical order.
                dot (tuple[str, ...] | None): Current template dot context, or an unresolved
                    context.
                env (dict[str, tuple[str, ...] | None]): Variable aliases available in the current
                    lexical scope.
                source_name (str): Filename captured for this traversal.

            Returns:
                None: None. The operation completes through its documented side effects.
            """
            env = dict(env)
            for node in nodes:
                tokens = node.tokens
                if prune_literals and tokens in (["if", "true"], ["if", "false"]):
                    walk(
                        node.children if tokens[1] == "true" else node.otherwise,
                        dot,
                        env,
                        source_name,
                    )
                    continue
                fallback = any(t in ("default", "coalesce", "dig") for t in tokens)

                def warn(message: str, filename: str = source_name, line: int = node.line) -> None:
                    """
                    Record an unresolved construct at its template source location.

                    Args:
                        message (str): Diagnostic detail for the current source location.
                        filename (str): Filename used by this operation.
                        line (int): Line used by this operation.

                    Returns:
                        None: None. The operation completes through its documented side effects.
                    """
                    diagnostics.append(Diagnostic(filename, line, message))

                def resolve(token: str) -> tuple[str, ...] | None:
                    """
                    Resolve a field token against dot and variable aliases.

                    Args:
                        token (str): Template token to resolve.

                    Returns:
                        tuple[str, ...] | None: Result of the documented operation.
                    """
                    if token == ".":
                        return dot
                    if token.startswith("."):
                        base, suffix = dot, token[1:]
                    elif token.startswith("$"):
                        head, _, suffix = token.partition(".")
                        base = env.get(head)
                    else:
                        return None
                    if base is None:
                        return None
                    return base + tuple(suffix.split(".")) if suffix else base

                def emit(
                    value: tuple[str, ...] | None,
                    filename: str = source_name,
                    line: int = node.line,
                    has_fallback: bool = fallback,
                ) -> None:
                    """
                    Record a resolved reference rooted in chart values.

                    Args:
                        value (tuple[str, ...] | None): Candidate value supplied by the property
                            strategy.
                        filename (str): Filename used by this operation.
                        line (int): Line used by this operation.
                        has_fallback (bool): Has fallback used by this operation.

                    Returns:
                        None: None. The operation completes through its documented side effects.
                    """
                    if value and value[0] == "Values":
                        refs.append(Reference(value[1:], filename, line, has_fallback))

                def literal(token: str) -> str | None:
                    """
                    Decode a literal map key or recognize an array index.

                    Args:
                        token (str): Template token to resolve.

                    Returns:
                        str | None: Result of the documented operation.
                    """
                    if token.startswith('"'):
                        return str(json.loads(token))
                    if token.startswith("`"):
                        return token[1:-1]
                    if token.isdigit():
                        return "*"
                    return None

                def expression(ts: list[str], action_text: str = node.text) -> tuple[str, ...] | None:
                    """
                    Resolve literal lookups and simple template expressions.

                    Args:
                        ts (list[str]): Tokens forming a template expression.
                        action_text (str): Action text used by this operation.

                    Returns:
                        tuple[str, ...] | None: Result of the documented operation.
                    """
                    if not ts:
                        return None
                    if ts[0] == "(":
                        depth = 0
                        for j, t in enumerate(ts):
                            depth += (t == "(") - (t == ")")
                            if depth == 0:
                                base = expression(ts[1:j])
                                if base is not None and j + 1 < len(ts) and ts[j + 1].startswith("."):
                                    return base + tuple(ts[j + 1][1:].split("."))
                                return base
                        return None
                    if ts[0] in ("index", "get") and len(ts) >= 3:
                        base = resolve(ts[1])
                        if base is None:
                            warn("unresolved lookup target: " + action_text)
                            return None
                        keys = []
                        for t in ts[2:]:
                            if t in ("|", ")"):
                                break
                            key = literal(t)
                            if key is None:
                                warn("dynamic key requires manual review: " + action_text)
                                keys.append("*")
                            else:
                                keys.append(key)
                        return base + tuple(keys)
                    if ts[0] == "dig" and len(ts) >= 4:
                        ts = ts[: next((i for i, t in enumerate(ts) if t in ("|", ")")), len(ts))]
                        base = resolve(ts[-1])
                        dig_keys = [literal(t) for t in ts[1:-2]]
                        if base is not None and all(k is not None for k in dig_keys):
                            return base + tuple(k for k in dig_keys if k is not None)
                        warn("unresolved dig: " + action_text)
                        return None
                    if len(ts) == 1:
                        return resolve(ts[0])
                    return None

                for t in tokens:
                    value = resolve(t)
                    emit(value)
                    if t.startswith(".") and value is None:
                        warn("unresolved dot context: " + t)
                    if t.startswith("$") and "." in t and value is None:
                        warn("unresolved variable context: " + t)
                for j, t in enumerate(tokens):
                    if t in ("index", "get", "dig"):
                        emit(expression(tokens[j:]))
                    if t == "(":
                        emit(expression(tokens[j:]))
                    if t == "tpl":
                        try:
                            args = tpl.arguments(tokens[j + 1 :])
                            if len(args) != 2 or (j > 0 and tokens[j - 1] == "|"):
                                raise ValueError("tpl requires a resolvable string and context")
                            content = tpl.source_text(args[0], path, defaults, expression)
                            context = expression(args[1])
                            if context is None:
                                raise ValueError("tpl context is dynamic or unsupported")
                            identity = (content, context)
                            if identity in active_tpl or len(active_tpl) >= 32:
                                raise ValueError("recursive tpl expansion requires review")
                            nested = parse(content)
                            active_tpl.add(identity)
                            try:
                                walk(
                                    nested,
                                    context,
                                    {"$": context},
                                    f"{source_name}:{node.line} (tpl)",
                                )
                            finally:
                                active_tpl.remove(identity)
                        except ValueError as exc:
                            warn(str(exc))
                    if t in (
                        "include",
                        "template",
                        "block",
                        "set",
                        "unset",
                        "merge",
                        "mergeOverwrite",
                    ):
                        warn("dynamic template/context or mutation requires review: " + t)
                head = tokens[0]
                rhs = tokens[1:] if head in ("if", "range", "with") else tokens
                assignment = next((j for j, t in enumerate(rhs) if t in (":=", "=")), None)
                names = []
                if assignment is not None:
                    if rhs[assignment] == "=":
                        warn("variable reassignment requires review: " + node.text)
                    names = [t for t in rhs[:assignment] if t.startswith("$")]
                    rhs = rhs[assignment + 1 :]
                value = expression(rhs)
                emit(value)
                child_env = dict(env)
                for position, variable in enumerate(names):
                    if head == "range" and len(names) == 2 and position == 0:
                        child_env[variable] = None
                        continue
                    child_env[variable] = value + ("*",) if value is not None and head == "range" else value
                if head not in ("if", "range", "with"):
                    env.update(child_env)
                child_dot = dot
                if head in ("with", "range"):
                    child_dot = value
                    if head == "range" and value is not None:
                        child_dot = value + ("*",)
                if head in ("define", "block"):
                    child_dot, child_env = None, {"$": None}
                    warn("named template context is resolved only at runtime")
                walk(node.children, child_dot, child_env, source_name)
                if node.otherwise and node.otherwise[0].tokens[0] in ("if", "with"):
                    warn("chained else context requires review")
                    walk(node.otherwise, None, env, source_name)
                else:
                    walk(node.otherwise, dot, env, source_name)

        walk(nodes, (), {"$": ()})
    return list(dict.fromkeys(refs)), list(dict.fromkeys(diagnostics))
