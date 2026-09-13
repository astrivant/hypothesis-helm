"""
Identify local interaction groups from explicit selectors and structural evidence.
"""

from pathlib import Path

from attrs import field, frozen

from hypothesis_helm.charts.templates import Action, discover, parse
from hypothesis_helm.compiler.passes.dependencies import Dependencies
from hypothesis_helm.schemas.model import ValueReference, ValuesModel


@frozen
class ExhaustiveGroup:
    """
    Describe a candidate group with its provenance and coverage obligation.

    Attributes:
        paths (tuple[tuple[str, ...], ...]): Factor paths or container prefixes.
        source (str): User selection, schema location or template source location.
        explicit (bool): Whether refusing the group must fail planning.
        references (tuple[ValueReference, ...]): Bound fields from the shared values model.
    """

    paths: tuple[tuple[str, ...], ...]
    source: str
    explicit: bool = False
    references: tuple[ValueReference, ...] = field(default=(), eq=False, repr=False)


def parse_group(value: str) -> ExhaustiveGroup:
    """
    Parse comma-separated dotted paths or JSON Pointer prefixes.

    Args:
        value (str): User-provided group selector.

    Returns:
        ExhaustiveGroup: Explicit required group of at least two selectors.
    """
    paths = []
    for selector in value.split(","):
        selector = selector.strip()
        if selector.startswith("/"):
            path = tuple(part.replace("~1", "/").replace("~0", "~") for part in selector[1:].split("/"))
        else:
            path = tuple(selector.removeprefix("$.").split("."))
        if not selector or any(not part for part in path):
            raise ValueError("exhaustive groups require nonempty value paths")
        paths.append(path)
    paths = sorted(set(paths))
    if len(paths) < 2:
        raise ValueError("exhaustive groups require at least two distinct selectors")
    return ExhaustiveGroup(tuple(paths), f"user: {value}", True)


def infer_groups(chart: Path, schema: dict[str, object] | ValuesModel) -> tuple[list[ExhaustiveGroup], list[dict[str, object]]]:
    """
    Propose local hyperedges without merging overlapping groups transitively.

    Args:
        chart (Path): Chart directory containing Helm templates.
        schema (dict[str, object] | ValuesModel): Shared model or declared values schema.

    Returns:
        tuple[list[ExhaustiveGroup], list[dict[str, object]]]: Evidence-backed groups and
            unresolved template diagnostics requiring user review.
    """
    model = schema if isinstance(schema, ValuesModel) else ValuesModel.from_schema(schema)
    groups: list[ExhaustiveGroup] = []

    def add(paths: set[tuple[str, ...]], source: str) -> None:
        """
        Retain specific references rather than redundant container prefixes.

        Args:
            paths (set[tuple[str, ...]]): Value paths referenced by one construct.
            source (str): Provenance of the construct.

        Returns:
            None: A candidate group is appended when multiple references remain.
        """
        precise = tuple(
            sorted(path for path in paths if path and not any(len(other) > len(path) and other[: len(path)] == path for other in paths))
        )
        if len(precise) >= 2:
            groups.append(ExhaustiveGroup(precise, source, references=tuple(model.reference(path) for path in precise)))

    for relationship in model.relationships:
        add({reference.path for reference in relationship.references}, relationship.source)
    dependencies = Dependencies.build(chart)
    for dependency in dependencies.nodes:
        controls = {
            path for ancestor in dependencies.nodes if dependency.path[: len(ancestor.path)] == ancestor.path for path in ancestor.controls
        }
        # Each child field interacts with its activation chain; do not merge sibling
        # fields into one exponentially larger group. Existing group budgets apply.
        for reference in dependency.references:
            add(controls | {reference.path}, "dependency:" + ".".join(dependency.path))
    references, diagnostics = discover(chart)
    for file in sorted((chart / "templates").rglob("*")):
        if not file.is_file():
            continue
        name = str(file.relative_to(chart))
        try:
            nodes = parse(file.read_text())
        except ValueError:
            continue
        by_line: dict[int, set[tuple[str, ...]]] = {}
        for reference in references:
            if reference.file == name:
                by_line.setdefault(reference.line, set()).add(reference.path)

        def walk(
            actions: list[Action],
            source_name: str = name,
            line_refs: dict[int, set[tuple[str, ...]]] = by_line,
        ) -> set[tuple[str, ...]]:
            """
            Group resolved references within expressions and guarded block subtrees.

            Args:
                actions (list[Action]): Parsed actions in lexical order.
                source_name (str): Chart-relative filename for this traversal.
                line_refs (dict[int, set[tuple[str, ...]]]): Resolved references by source line.

            Returns:
                set[tuple[str, ...]]: References mentioned by the subtree.
            """
            subtree: set[tuple[str, ...]] = set()
            for action in actions:
                own = line_refs.get(action.line, set())
                add(own, f"template:{source_name}:{action.line}:expression")
                children = walk(action.children) | walk(action.otherwise)
                if action.tokens[0] in ("if", "with", "range"):
                    add(own | children, f"template:{source_name}:{action.line}:{action.tokens[0]}")
                subtree.update(own | children)
            return subtree

        walk(nodes)
    unresolved = [{"file": item.file, "line": item.line, "message": item.message} for item in diagnostics]
    unresolved.extend(dependencies.diagnostics)
    return list(dict.fromkeys(groups)), unresolved
