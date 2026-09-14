"""
Recognize pure Boolean and scalar-equality predicates with explicit type contracts.
"""

import json
import re
from collections.abc import Callable

from attrs import frozen

from hypothesis_helm.compiler.asts.lexing import SPACE
from hypothesis_helm.compiler.asts.templates import value_path


@frozen
class Condition:
    """
    Describe a restricted predicate without accepting arbitrary Helm functions.

    Attributes:
        path (tuple[str, ...] | None): Direct values selector, absent for a Boolean literal.
        operator (str): Literal, truth, not, eq or ne.
        literal (str | bool): Comparison operand or Boolean constant.
    """

    path: tuple[str, ...] | None
    operator: str
    literal: str | bool = True

    def evaluate(self, read: Callable[[str], object]) -> bool:
        """
        Evaluate only compatible types, preserving unsupported cases as uncertainty.

        Args:
            read (Callable[[str], object]): Existing compiler scalar lookup, including its safety checks.

        Returns:
            bool: Exact result, or ValueError when the restricted type contract does not apply.
        """
        if self.path is None:
            return bool(self.literal)
        value = read(".Values." + ".".join(self.path))
        if self.operator in {"truth", "not"}:
            if type(value) is not bool:
                raise ValueError("only Boolean truth conditions have a control-flow proof")
            return bool(value) if self.operator == "truth" else not value
        if type(value) is not type(self.literal):
            raise ValueError("equality operands are outside the same-type string/Boolean contract")
        equal = value == self.literal
        return equal if self.operator == "eq" else not equal


def parse_condition(expression: str) -> Condition | None:
    """
    Parse direct predicates while leaving pipelines, escaped literals and compound expressions opaque.

    Args:
        expression (str): Complete condition expression.

    Returns:
        Condition | None: Pure predicate, or no supported interpretation.
    """
    if expression in {"true", "false"}:
        return Condition(None, "literal", expression == "true")
    if (path := value_path(expression)) is not None:
        return Condition(path, "truth")
    if expression.startswith("not ") and (path := value_path(expression[4:].strip(SPACE))) is not None:
        return Condition(path, "not")
    match = re.fullmatch(r'(eq|ne)[ \t\r\n]+(\S+)[ \t\r\n]+(true|false|"[^"\\\x00-\x1f]*")', expression)
    if match is not None and (path := value_path(match[2])) is not None:
        literal = json.loads(match[3])
        if type(literal) in (str, bool):
            return Condition(path, match[1], literal)
    return None


def condition_path(expression: str) -> tuple[str, ...] | None:
    """
    Expose the values dependency of a supported condition to other compiler passes.

    Args:
        expression (str): Complete predicate.

    Returns:
        tuple[str, ...] | None: Referenced field, if known.
    """
    condition = parse_condition(expression)
    return condition.path if condition is not None else None
