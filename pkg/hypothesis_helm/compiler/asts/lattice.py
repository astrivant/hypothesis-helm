"""
Represent branch knowledge as a product of finite scalar sets with explicit top and bottom.
"""

from __future__ import annotations

from attrs import field, frozen
from immutables import Map

from hypothesis_helm.compiler.asts.conditions import Condition
from hypothesis_helm.schemas.model import ValuesModel

type Path = tuple[str, ...]
type Scalar = str | bool


@frozen
class Domain:
    """
    Bound a field's possible values under set inclusion.

    Attributes:
        values (frozenset[Scalar] | None): Finite possibilities; None is unknown and the empty set is impossible.
    """

    values: frozenset[Scalar] | None = None

    def join(self, other: Domain) -> Domain:
        """
        Merge alternative possibilities by union.

        Args:
            other (Domain): Knowledge from another branch.

        Returns:
            Domain: Least upper bound of both sets.
        """
        return Domain() if self.values is None or other.values is None else Domain(self.values | other.values)

    def meet(self, other: Domain) -> Domain:
        """
        Combine simultaneous constraints by intersection.

        Args:
            other (Domain): Additional constraint on the field.

        Returns:
            Domain: Greatest lower bound of both sets.
        """
        if self.values is None:
            return other
        return self if other.values is None else Domain(self.values & other.values)


@frozen
class State:
    """
    Share immutable field knowledge across branches without retaining correlations.

    Attributes:
        fields (Map[Path, Domain]): Finite field constraints; absent fields are unknown.
        reachable (bool): False denotes an impossible environment, independent of its fields.
    """

    fields: Map[Path, Domain] = field(factory=Map)
    reachable: bool = True

    def __attrs_post_init__(self) -> None:
        """
        Canonicalize unknown fields and impossible environments for algebraic equality.

        Returns:
            None: Equivalent states have identical representations.
        """
        if not self.reachable or any(domain.values == frozenset() for domain in self.fields.values()):
            object.__setattr__(self, "reachable", False)
            object.__setattr__(self, "fields", Map())
        elif any(domain.values is None for domain in self.fields.values()):
            object.__setattr__(self, "fields", Map((path, domain) for path, domain in self.fields.items() if domain.values is not None))

    @classmethod
    def from_model(cls, model: ValuesModel) -> State:
        """
        Read finite scalar bounds only through explicitly required object paths.

        Args:
            model (ValuesModel): Shared schema model; defaults do not constrain possible inputs.

        Returns:
            State: Conservative domain bounds, leaving optional paths and references unknown.
        """
        fields: Map[Path, Domain] = Map()
        pending = [model.root]
        while pending:
            node = pending.pop()
            schema = node.schema
            if "$ref" in schema:
                continue
            if schema.get("type") == "object":
                pending.extend(child for child in node.children.values() if child.required)
            raw = [schema["const"]] if "const" in schema else schema.get("enum")
            if raw is None and schema.get("type") == "boolean":
                raw = [False, True]
            if node.path and isinstance(raw, list) and raw and all(type(value) in (str, bool) for value in raw):
                fields = fields.set(node.path, Domain(frozenset(raw)))
        return cls(fields)

    def join(self, other: State) -> State:
        """
        Merge reachable branches without carrying either branch's exclusive assumptions forward.

        Args:
            other (State): Alternative branch environment.

        Returns:
            State: Pointwise union; correlations between fields are deliberately forgotten.
        """
        if not self.reachable:
            return other
        if not other.reachable:
            return self
        return State(Map((path, domain.join(other.fields.get(path, Domain()))) for path, domain in self.fields.items()))

    def meet(self, other: State) -> State:
        """
        Apply simultaneous field constraints and detect contradictions.

        Args:
            other (State): Additional environment constraints.

        Returns:
            State: Pointwise intersection or the impossible state.
        """
        if not self.reachable or not other.reachable:
            return State(reachable=False)
        result = self.fields
        for path, domain in other.fields.items():
            result = result.set(path, result.get(path, Domain()).meet(domain))
        return State(result)

    def assume(self, condition: Condition, truth: bool) -> State:
        """
        Narrow a branch using a successful supported predicate evaluation.

        Args:
            condition (Condition): Parsed pure predicate.
            truth (bool): Which branch is being analyzed.

        Returns:
            State: Narrowed knowledge; incompatible or unknown truthiness stays conservative.
        """
        if not self.reachable:
            return self
        if condition.path is None:
            return self if bool(condition.literal) == truth else State(reachable=False)
        domain = self.fields.get(condition.path, Domain())
        direct = condition.operator in {"truth", "not"}
        literal = True if direct else condition.literal
        if direct and domain.values is None:
            return self
        if domain.values is not None and any(type(value) is not type(literal) for value in domain.values):
            return self
        equal = truth if condition.operator in {"truth", "eq"} else not truth
        if equal:
            narrowed = domain.meet(Domain(frozenset({literal})))
        else:
            narrowed = Domain(None if domain.values is None else domain.values - {literal})
        return State(self.fields.set(condition.path, narrowed))
