"""
Discover dependency controls and guide inputs without treating inactive fields as unused.
"""

from __future__ import annotations

import copy
import json
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from attrs import define, field
from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.templates import Reference, discover
from hypothesis_helm.compiler.asts.dependencies import Dependency
from hypothesis_helm.schemas.contracts import configuration_key, mapping


def lookup(values: object, path: tuple[str | int, ...]) -> object:
    """
    Read a concrete value without mistaking missing or non-Boolean fields for false.

    Args:
        values (object): Nested values document.
        path (tuple[str | int, ...]): Root-relative field selector.

    Returns:
        object: Supplied value, or None when a parent is absent or incompatible.
    """
    for key in path:
        if isinstance(values, dict):
            values = values.get(key)
        elif isinstance(values, list) and isinstance(key, int) and 0 <= key < len(values):
            values = values[key]
        else:
            return None
    return values


def overlaps(left: tuple[str | int, ...], right: tuple[str | int, ...]) -> bool:
    """
    Recognize shared ancestors, including symbolic array or map selectors.

    Args:
        left (tuple[str | int, ...]): Selected input path.
        right (tuple[str | int, ...]): Dependency control or value namespace.

    Returns:
        bool: Whether either selector contains the other.
    """
    return all(a == b or a == "*" or b == "*" for a, b in zip(left, right, strict=False))


def assign(values: dict[str, object], path: tuple[str, ...], value: object) -> bool:
    """
    Set a control in a detached candidate without replacing non-map ancestors.

    Args:
        values (dict[str, object]): Candidate being constructed.
        path (tuple[str, ...]): Concrete metadata control path.
        value (object): Requested control value.

    Returns:
        bool: Whether the assignment could be represented in this input.
    """
    current = values
    for key in path[:-1]:
        child = current.setdefault(key, {})
        if not isinstance(child, dict):
            return False
        current = child
    current[path[-1]] = value
    return True


def fill_defaults(defaults: dict[str, object], supplied: dict[str, object]) -> dict[str, object]:
    """
    Fill missing child defaults while retaining explicit null overrides as deletion markers.

    Args:
        defaults (dict[str, object]): Lower-priority child defaults.
        supplied (dict[str, object]): Parent values or direct overrides.

    Returns:
        dict[str, object]: Detached merged context for activation prediction.
    """
    result = copy.deepcopy(defaults)
    for key, value in supplied.items():
        result[key] = (
            fill_defaults(mapping(result[key]), value)
            if isinstance(result.get(key), dict) and isinstance(value, dict)
            else copy.deepcopy(value)
        )
    return result


def unpack(archive: Path, destination: Path) -> None:
    """
    Materialize bounded regular chart files for existing template discovery, without links.

    Args:
        archive (Path): Local dependency archive already prepared by Helm.
        destination (Path): Fresh temporary directory owned by this compiler invocation.

    Returns:
        None: Chart content is available for recursive metadata and template discovery.
    """
    total = 0
    with tarfile.open(archive) as bundle:
        for index, member in enumerate(bundle):
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
                raise ValueError("dependency archive contains unsafe paths or links")
            total += member.size
            if index >= 10000 or total > 64 * 1024 * 1024:
                raise ValueError("dependency archive exceeds compiler inspection limit")
            if not member.isfile():
                continue
            stream = bundle.extractfile(member)
            if stream is None:
                continue
            target = destination.joinpath(*name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(stream.read())


@define
class Dependencies:
    """
    Hold discovered dependency instances, uncertainty, and generation-context statistics.

    Attributes:
        nodes (list[Dependency]): Dependency instances ordered before their descendants.
        diagnostics (list[dict[str, object]]): Unsupported sources and incomplete mappings.
        guided (int): Candidates for which a valid enabled context was constructed.
        unavailable (int): Candidates whose activation context could not be constructed.
        baseline (dict[str, object]): Original root defaults for inventory reporting.
    """

    nodes: list[Dependency] = field(factory=list)
    diagnostics: list[dict[str, object]] = field(factory=list)
    guided: int = 0
    unavailable: int = 0
    baseline: dict[str, object] = field(factory=dict)

    @classmethod
    def build(cls, chart: Path) -> Dependencies:
        """
        Load installed child charts and discover controls even when their paths lack defaults.

        Args:
            chart (Path): Root chart, with dependencies already present when available.

        Returns:
            Dependencies: Namespaced metadata and template references; no downloads or source edits.
        """
        result = cls()
        if (chart / "values.yaml").is_file():
            result.baseline = mapping(yamlio.load((chart / "values.yaml").read_text()) or {})
        with tempfile.TemporaryDirectory(prefix="helm-dependency-analysis-") as temporary:
            result._walk(chart, (), "", Path(temporary), set())
        return result

    def _walk(self, chart: Path, prefix: tuple[str, ...], source: str, temporary: Path, ancestors: set[Path]) -> None:
        """
        Inspect child instances recursively with bounded depth and explicit loading diagnostics.

        Args:
            chart (Path): Current installed chart directory.
            prefix (tuple[str, ...]): Parent-values scope for this chart instance.
            source (str): Logical source prefix, independent of archive extraction paths.
            temporary (Path): Owned workspace for packed dependency contents.
            ancestors (set[Path]): Real directories already visited on this ancestry chain.

        Returns:
            None: Discovered instances and source limitations are appended.
        """
        if len(prefix) >= 16 or chart.resolve() in ancestors or len(self.nodes) >= 512:
            self.diagnostics.append({"file": source + "Chart.yaml", "message": "Dependency recursion limit reached"})
            return
        metadata_file = chart / "Chart.yaml"
        if not metadata_file.is_file():
            return
        metadata = mapping(yamlio.load(metadata_file.read_text()))
        declared = metadata.get("dependencies", [])
        if metadata.get("apiVersion") == "v1" and (chart / "requirements.yaml").is_file():
            declared = mapping(yamlio.load((chart / "requirements.yaml").read_text())).get("dependencies", [])
        if not isinstance(declared, list):
            self.diagnostics.append({"file": source + "Chart.yaml", "message": "Malformed dependency list"})
            return
        available: dict[str, list[Path]] = {}
        for child in sorted((chart / "charts").glob("*")):
            try:
                roots = [child]
                if child.suffix == ".tgz":
                    extraction = temporary / str(len(list(temporary.iterdir())))
                    extraction.mkdir()
                    unpack(child, extraction)
                    roots = [p.parent for p in extraction.glob("*/Chart.yaml")]
                for candidate_root in roots:
                    if (candidate_root / "Chart.yaml").is_file():
                        name = mapping(yamlio.load((candidate_root / "Chart.yaml").read_text())).get("name")
                        if isinstance(name, str):
                            available.setdefault(name, []).append(candidate_root)
            except (OSError, ValueError, tarfile.TarError, YAMLError) as error:
                self.diagnostics.append({"file": source + "charts/" + child.name, "message": str(error)})
        requested = [mapping(item) for item in declared if isinstance(item, dict)]
        requested += [{"name": name} for name in available if not any(item.get("name") == name for item in requested)]
        for item in requested:
            name, alias = item.get("name"), item.get("alias", item.get("name"))
            if not isinstance(name, str) or not isinstance(alias, str) or not alias or "/" in alias:
                self.diagnostics.append({"file": source + "Chart.yaml", "message": "Unsupported dependency name or alias"})
                continue
            path = (*prefix, alias)
            child_source = source + "charts/" + alias + "/"
            conditions = item.get("condition", "")
            tags = item.get("tags", [])
            reason = None
            if not isinstance(conditions, str) or not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                conditions, tags, reason = "", [], "Malformed dependency controls"
            selectors = tuple((*prefix, *part.split(".")) for part in conditions.strip().split(",") if part)
            tag_paths = tuple(("tags", tag) for tag in tags)
            choices = available.get(name, [])
            root = choices[0] if len(choices) == 1 else None
            defaults: dict[str, object] = {}
            schema: dict[str, object] = {}
            references: list[Reference] = []
            templates: tuple[str, ...] = ()
            if root is None:
                reason = reason or "Dependency source missing or ambiguous; run helm dependency build"
            else:
                try:
                    defaults = mapping(yamlio.load((root / "values.yaml").read_text()) or {}) if (root / "values.yaml").is_file() else {}
                    schema = (
                        mapping(json.loads((root / "values.schema.json").read_text())) if (root / "values.schema.json").is_file() else {}
                    )
                    found, warnings = discover(root, prune_literals=True)
                    references = [Reference((*path, *ref.path), child_source + ref.file, ref.line, ref.fallback) for ref in found]
                    # Globals also have parent/root forwarding paths, so retain both potential sources.
                    references += [
                        Reference(ref.path, child_source + ref.file, ref.line, ref.fallback) for ref in found if ref.path[:1] == ("global",)
                    ]
                    templates = tuple(
                        child_source + p.relative_to(root).as_posix() for p in sorted((root / "templates").rglob("*")) if p.is_file()
                    )
                    self.diagnostics.extend({"file": child_source + warning.file, "message": warning.message} for warning in warnings)
                except (OSError, ValueError, YAMLError) as error:
                    reason = reason or str(error)
            if item.get("import-values"):
                self.diagnostics.append(
                    {"file": source + "Chart.yaml", "path": list(path), "message": "import-values forwarding remains unresolved"}
                )
            if prefix and any("global" in selector for selector in selectors):
                reason = reason or "Nested global activation forwarding remains unresolved"
            if any(node.path == path for node in self.nodes):
                reason = reason or "Duplicate dependency namespace"
            node = Dependency(path, name, child_source, selectors, tag_paths, defaults, schema, tuple(references), templates, reason)
            self.nodes.append(node)
            if reason:
                self.diagnostics.append({"file": source + "Chart.yaml", "path": list(path), "message": reason})
            if root is not None:
                self._walk(root, path, child_source, temporary, ancestors | {chart.resolve()})

    @property
    def references(self) -> list[Reference]:
        """
        Include metadata controls and namespaced child references in the input inventory.

        Returns:
            list[Reference]: Potential value consumers; metadata locations use line one.
        """
        return [
            ref
            for node in self.nodes
            for ref in (
                *node.references,
                *(Reference(path, node.source.rsplit("charts/", 1)[0] + "Chart.yaml", 1) for path in node.controls),
            )
        ]

    def context(self, defaults: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
        """
        Fill installed child defaults before applying parent overrides for activation analysis.

        Args:
            defaults (dict[str, object]): Original root defaults.
            overrides (dict[str, object]): Current generated overrides, including null markers.

        Returns:
            dict[str, object]: Predicted activation input; Helm still performs authoritative coalescing.
        """
        result: dict[str, object] = {}
        for node in self.nodes:
            current = lookup(result, node.path)
            assign(result, node.path, fill_defaults(node.defaults, current if isinstance(current, dict) else {}))
        result = fill_defaults(fill_defaults(result, defaults), overrides)
        for node in self.nodes:
            parent_globals = lookup(result, (*node.path[:-1], "global"))
            child_values = lookup(result, node.path)
            if isinstance(parent_globals, dict) and isinstance(child_values, dict):
                child_globals = child_values.get("global", {})
                if isinstance(child_globals, dict):
                    child_values["global"] = fill_defaults(child_globals, parent_globals)
        return result

    def states(self, defaults: dict[str, object], overrides: dict[str, object]) -> dict[tuple[str, ...], bool | None]:
        """
        Resolve conditions before tags and preserve uncertainty instead of assuming inactivity.

        Args:
            defaults (dict[str, object]): Original root defaults.
            overrides (dict[str, object]): Candidate overrides.

        Returns:
            dict[tuple[str, ...], bool | None]: Predicted enabled states including ancestor gates.
        """
        context = self.context(defaults, overrides)
        states: dict[tuple[str, ...], bool | None] = {}
        for node in self.nodes:
            parent = states.get(node.path[:-1], True)
            if parent is False:
                states[node.path] = False
            elif node.reason or parent is None:
                states[node.path] = None
            else:
                controls = [lookup(context, path) for path in node.conditions]
                condition = next((value for value in controls if type(value) is bool), None)
                tags = [lookup(context, path) for path in node.tags]
                states[node.path] = (
                    condition
                    if isinstance(condition, bool)
                    else not (any(value is False for value in tags) and not any(value is True for value in tags))
                )
        return states

    def contexts(
        self,
        defaults: dict[str, object],
        values: dict[str, object],
        selected: tuple[str | int, ...],
        accept: Callable[[dict[str, object]], bool],
    ) -> list[dict[str, object]]:
        """
        Prefer enabled child contexts while retaining original inputs and selected path values.

        Args:
            defaults (dict[str, object]): Original root defaults.
            values (dict[str, object]): Candidate produced by the path strategy.
            selected (tuple[str | int, ...]): Path that must not be changed by guidance.
            accept (Callable[[dict[str, object]], bool]): Original parent schema validation.

        Returns:
            list[dict[str, object]]: Enabled context first when feasible, then the original context.
        """
        targets = [
            node
            for node in self.nodes
            if overlaps(selected, node.path)
            or any(overlaps(selected, ref.path) for ref in node.references)
            or any(overlaps(selected, path) for path in node.controls)
        ]
        relevant = [node for node in self.nodes if any(target.path[: len(node.path)] == node.path for target in targets)]
        candidate = copy.deepcopy(values)
        for node in relevant:
            selected_condition = next((index for index, path in enumerate(node.conditions) if overlaps(selected, path)), None)
            selected_tag = any(overlaps(selected, path) for path in node.tags)
            if selected_condition is not None or selected_tag:
                # Expose a later condition or tag without allowing an earlier Boolean
                # condition to mask it. Null is a Helm override deletion marker.
                trial = copy.deepcopy(candidate)
                context = self.context(defaults, candidate)
                earlier = node.conditions[:selected_condition] if selected_condition is not None else node.conditions
                for control in earlier:
                    if not overlaps(selected, control) and type(lookup(context, control)) is bool:
                        assign(trial, control, None)
                if selected_tag and selected_condition is None:
                    for control in node.tags:
                        if not overlaps(selected, control) and lookup(context, control) is True:
                            assign(trial, control, False)
                if accept(trial):
                    candidate = trial
                else:
                    self.unavailable += 1
                continue
            if self.states(defaults, candidate).get(node.path) is not False:
                continue
            context = self.context(defaults, candidate)
            condition = next((path for path in node.conditions if type(lookup(context, path)) is bool), None)
            options = (condition,) if condition is not None else (*node.conditions, *node.tags)
            for control in options:
                if overlaps(selected, control):
                    continue
                trial = copy.deepcopy(candidate)
                if assign(trial, control, True) and accept(trial) and self.states(defaults, trial).get(node.path) is True:
                    candidate = trial
                    break
        desired = [node for node in relevant if not any(overlaps(selected, control) for control in node.controls)]
        if desired and any(self.states(defaults, candidate).get(node.path) is not True for node in desired):
            self.unavailable += 1
        if configuration_key(candidate) != configuration_key(values):
            self.guided += 1
            return [candidate, values]
        return [values]

    def report(self, defaults: dict[str, object]) -> dict[str, object]:
        """
        Report activation relationships without claiming exhaustive or render-proven coverage.

        Args:
            defaults (dict[str, object]): Original baseline for predicted dependency states.

        Returns:
            dict[str, object]: Dependency controls, namespaces, uncertainty, and guidance counts.
        """
        states = self.states(defaults, {})
        return {
            "dependencies": [
                {
                    "path": list(node.path),
                    "name": node.name,
                    "source": node.source,
                    "conditions": [list(path) for path in node.conditions],
                    "tags": [list(path) for path in node.tags],
                    "baseline_enabled": states[node.path],
                    "reason": node.reason,
                }
                for node in self.nodes
            ],
            "guided_contexts": self.guided,
            "unavailable_contexts": self.unavailable,
            "diagnostics": self.diagnostics,
            "scope": "Activation predictions guide generation; Helm validates each rendered input. Inactive fields remain testable.",
        }
