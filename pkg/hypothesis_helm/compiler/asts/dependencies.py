"""
Describe dependency activation controls and values namespaces independently of templates.
"""

from attrs import frozen

from hypothesis_helm.charts.templates import Reference


@frozen
class Dependency:
    """
    Represent one dependency instance, including aliases and nested activation controls.

    Attributes:
        path (tuple[str, ...]): Parent-values namespace for this instance.
        name (str): Original chart name before aliasing.
        source (str): Logical chart source using Helm's alias-based template paths.
        conditions (tuple[tuple[str, ...], ...]): Ordered root-relative condition selectors.
        tags (tuple[tuple[str, ...], ...]): Root tag selectors shared by tagged dependencies.
        defaults (dict[str, object]): Supplied child defaults, without parent overrides.
        schema (dict[str, object]): Original child schema, used only for input discovery.
        references (tuple[Reference, ...]): Template references projected into parent values.
        templates (tuple[str, ...]): Logical template paths belonging to this child.
        reason (str | None): Unsupported metadata or loading details that prevent guidance.
    """

    path: tuple[str, ...]
    name: str
    source: str
    conditions: tuple[tuple[str, ...], ...]
    tags: tuple[tuple[str, ...], ...]
    defaults: dict[str, object]
    schema: dict[str, object]
    references: tuple[Reference, ...]
    templates: tuple[str, ...]
    reason: str | None = None

    @property
    def controls(self) -> tuple[tuple[str, ...], ...]:
        """
        Collect metadata paths that can change this dependency's activation state.

        Returns:
            tuple[tuple[str, ...], ...]: Conditions followed by tag paths, retaining order.
        """
        return (*self.conditions, *self.tags)
