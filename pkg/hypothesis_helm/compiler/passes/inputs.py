"""
Inventory known template inputs and measure render-input coverage against them.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import asdict, define, field
from jsonschema import validators

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.presence import has_path
from hypothesis_helm.charts.templates import Reference, discover
from hypothesis_helm.schemas.contracts import configuration_key, json_value
from hypothesis_helm.schemas.model import ValueReference, ValuesModel

if TYPE_CHECKING:
    from hypothesis_helm.charts.runner import Chart


def load_input_chart(path: Path) -> Chart:
    """
    Load original values for inventory even when a chart has no values schema.

    Args:
        path (Path): Chart directory containing metadata and values.yaml.

    Returns:
        Chart: Original defaults with the declared schema or an open object contract.
    """
    from hypothesis_helm.charts.runner import Chart
    from hypothesis_helm.schemas.contracts import mapping

    path = path.resolve()
    if (path / "values.schema.json").is_file():
        return Chart.load(path)
    metadata = yamlio.load((path / "Chart.yaml").read_text())
    if not isinstance(metadata, dict) or not metadata.get("name"):
        raise ValueError("Chart.yaml must contain a chart name")
    return Chart(path, {"type": "object"}, mapping(yamlio.load((path / "values.yaml").read_text()) or {}))


def leaves(paths: set[tuple[str, ...]]) -> set[tuple[str, ...]]:
    """
    Count a container once only when no more specific path is known.

    Args:
        paths (set[tuple[str, ...]]): Named input selectors.

    Returns:
        set[tuple[str, ...]]: Selectors without a known descendant.
    """
    parents = {path[:index] for path in paths for index in range(1, len(path))}
    return paths - parents


@define
class InputField:
    """
    Bind one inventory entry to the shared typed model and source evidence.

    Attributes:
        reference (ValueReference): Model node or explicit unresolved binding.
        in_values (bool): Whether the original values document supplies this path.
        in_schema (bool): Whether the original schema documents this path.
        locations (list[Reference]): Template references to this exact path.
    """

    reference: ValueReference
    in_values: bool
    in_schema: bool
    locations: list[Reference]


@define
class InputInventory:
    """
    Preserve a conservative lower bound of identified named template inputs.

    Attributes:
        model (ValuesModel): Shared attrs/cattrs representation of the original schema.
        fields (list[InputField]): Evidence for supplied, declared, and referenced fields.
        known (set[tuple[str, ...]]): Leaf-most statically named reference paths.
        dynamic (set[tuple[str, ...]]): Prefixes with unresolved map or collection access.
        unresolved (list[dict[str, object]]): Constructs preventing complete inventory claims.
        usage_unknown (bool): Whether unmatched values may be consumed by opaque contexts.
    """

    model: ValuesModel
    fields: list[InputField]
    known: set[tuple[str, ...]]
    dynamic: set[tuple[str, ...]]
    unresolved: list[dict[str, object]]
    usage_unknown: bool

    @classmethod
    def build(cls, chart: Chart) -> InputInventory:
        """
        Compare original values and schema with scope-aware template references.

        Args:
            chart (Chart): Source chart; inferred defaults never replace original evidence.

        Returns:
            InputInventory: Named-field baseline with explicit uncertainty regions.
        """
        from hypothesis_helm.charts.generate import enumerate_paths
        from hypothesis_helm.charts.runner import _default_paths, _schema_nodes

        references, warnings = discover(chart.path, prune_literals=True)
        unresolved = [asdict(warning) for warning in warnings]
        model = ValuesModel.from_schema(chart.schema)
        defaults = set(_default_paths(chart.defaults))
        try:
            declared = {tuple(str(part) for part in item.path) for item in enumerate_paths(chart.schema)}
        except (ValueError, KeyError, TypeError) as exc:
            declared = {node.path for node in model.root.walk() if node.path}
            unresolved.append({"message": f"Schema inventory incomplete: {exc}"})
        named = {ref.path for ref in references if ref.path and "*" not in ref.path}
        dynamic = {ref.path[: ref.path.index("*")] for ref in references if "*" in ref.path}
        if any(not ref.path for ref in references):
            dynamic.add(())
        fields = []
        for path in sorted(defaults | declared | named):
            documented = path in declared or bool(_schema_nodes(chart.schema, path, chart.schema))
            fields.append(
                InputField(
                    model.reference(path),
                    has_path(chart.defaults, path),
                    documented,
                    [ref for ref in references if ref.path == path],
                )
            )
        # Dependency/global forwarding is not resolved by the parent template analyzer.
        metadata = chart.path / "Chart.yaml"
        dependencies = yamlio.load(metadata.read_text()) if metadata.is_file() else {}
        if isinstance(dependencies, dict) and dependencies.get("dependencies"):
            unresolved.append({"message": "Dependency value forwarding requires downstream analysis"})
        unknown = bool(unresolved) or () in dynamic
        return cls(model, fields, leaves(named), dynamic, unresolved, unknown)

    def report(self) -> dict[str, object]:
        """
        Serialize original-document discrepancies without claiming unusedness or influence.

        Returns:
            dict[str, object]: Field evidence, named denominator, and unresolved regions.
        """
        supplied = leaves({item.reference.path for item in self.fields if item.in_values})
        referenced = {item.reference.path for item in self.fields if item.locations}
        unmatched = {
            path for path in supplied if not any(path[: len(ref)] == ref or ref[: len(path)] == path for ref in referenced | self.dynamic)
        }
        rows = [
            {
                "path": list(item.reference.path),
                "in_values": item.in_values,
                "in_schema": item.in_schema,
                "references": [{**asdict(ref), "path": list(ref.path)} for ref in item.locations],
            }
            for item in self.fields
        ]
        return {
            "fields": rows,
            "known_fields": [list(path) for path in sorted(self.known)],
            "lower_bound_fields": len(self.known),
            "bound_scope": "identified leaf-most named template selectors after literal dead-branch elimination",
            "inventory_complete": False,
            "output_influence_proven": False,
            "missing_values": [row for row in rows if row["references"] and not row["in_values"]],
            "undocumented_template_fields": [row for row in rows if row["references"] and not row["in_schema"]],
            "template_only_fields": [row for row in rows if row["references"] and not row["in_schema"] and not row["in_values"]],
            "schema_fields_without_values": [row["path"] for row in rows if row["in_schema"] and not row["in_values"]],
            "unreferenced_values": [list(path) for path in sorted(unmatched)],
            "unreferenced_usage": "unknown" if self.usage_unknown else "possibly unused; not proven",
            "dynamic_regions": [list(path) for path in sorted(self.dynamic)],
            "unresolved": self.unresolved,
        }

    def dump(
        self,
        chart: Chart,
        target: Path | None = None,
        *,
        directory: Path = Path("."),
        verification: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Export example values, missing-field metadata, and a stable JSON proof record.

        Args:
            chart (Chart): Original values and authoritative validation schema.
            target (Path | None): Optional YAML filename; source chart inputs are never overwritten.
            directory (Path): Destination directory when generating the filename.
            verification (dict[str, object] | None): Render checks; preserve values exactly.

        Returns:
            dict[str, object]: Dump paths and limits of the reduction.
        """
        retained = {item.reference.path for item in self.fields if item.locations} | self.dynamic

        def project(value: object, path: tuple[str, ...]) -> object:
            """
            Preserve selected subtrees without synthesizing any absent values.

            Args:
                value (object): Original subtree.
                path (tuple[str, ...]): Current selector.

            Returns:
                object: Conservative projection of this subtree.
            """
            if path in retained or not isinstance(value, dict):
                return copy.deepcopy(value)
            return {
                key: project(child, (*path, str(key)))
                for key, child in value.items()
                if any(ref[: len(path) + 1] == (*path, str(key)) for ref in retained)
            }

        values = copy.deepcopy(chart.defaults) if self.usage_unknown or verification is not None else project(chart.defaults, ())
        reason = "Unresolved access prevents reduction" if self.usage_unknown else "Known references and dynamic subtrees retained"
        validator = validators.validator_for(chart.schema)(chart.schema)
        if not validator.is_valid(json_value(values)):
            values = copy.deepcopy(chart.defaults)
            reason = "Projection violates schema constraints; original values retained"
        inventory = self.report()
        missing = {
            "missing_values": inventory["missing_values"],
            "schema_fields_without_values": inventory["schema_fields_without_values"],
        }
        content = (
            "# Minimal input example; missing fields follow in document 2.\n"
            + "# See the companion .proof for verification evidence and limits.\n"
            + yamlio.dump(values, explicit_null=verification is not None)
            + "---\n"
            + "# Missing input fields: diagnostic metadata, not chart values.\n"
            + yamlio.dump(missing, explicit_null=verification is not None)
        ).encode("utf-8")
        checksum = hashlib.sha256(content).hexdigest()
        epoch = int(time.time())
        if target is None:
            target = directory / f"values-minimal-{checksum}-{epoch}.yaml"
        if target.resolve() in {(chart.path / name).resolve() for name in ("values.yaml", "values.schema.json", "Chart.yaml")}:
            raise ValueError("Minimal-values output must not overwrite source chart inputs")
        proof = target.with_suffix(".proof")
        if target.resolve() == proof.resolve():
            raise ValueError("Values filename must differ from its .proof companion")
        if target.is_symlink() or proof.is_symlink():
            raise ValueError("Minimal-values outputs must not overwrite symbolic links")
        result = {
            "yaml": str(target),
            "proof": str(proof),
            "sha256": checksum,
            "exported_epoch": epoch,
            "values_document": 1,
            "missing_fields_document": 2,
            "reason": reason,
            "schema_valid": validator.is_valid(json_value(values)),
            "globally_minimal_proven": False,
            "render_equivalence_proven": False,
            "input_inventory": inventory,
        }
        if verification is not None:
            result["verification"] = verification
            result["reason"] = (
                "Concrete baseline verified with Helm; see the scoped minimality result"
                if verification.get("verified")
                else "Configuration example; validation did not pass"
            )
        # Only stable evidence belongs in a committed proof. Runtime timing stays in CLI reports.
        evidence = {key: value for key, value in result.items() if key not in {"yaml", "proof", "exported_epoch", "verification"}}
        evidence.update(format_version=1, yaml=target.name)
        if verification is not None:
            evidence["verification"] = {key: value for key, value in verification.items() if key != "elapsed_seconds"}
        else:
            evidence["verification"] = {"verified": False, "checks": [], "reason": "Static inventory only; verification not run"}
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".minimal-values-", dir=target.parent) as temporary:
            staged = Path(temporary)
            (staged / "values").write_bytes(content)
            (staged / "proof").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
            (staged / "values").replace(target)
            (staged / "proof").replace(proof)
        return result


@define
class FieldCoverage:
    """
    Count presence and variation in actual render attempts, without branch coverage claims.

    Attributes:
        inventory (InputInventory): Stable field denominator shared across phases.
        defaults (dict[str, object]): Original baseline used to detect changed values.
        present (set[tuple[str, ...]]): Known fields supplied to at least one render attempt.
        varied (set[tuple[str, ...]]): Known fields changed or removed from the baseline.
        statistics (dict[str, object]): Live JSON-safe counters included in runner reports.
    """

    inventory: InputInventory
    defaults: dict[str, object]
    present: set[tuple[str, ...]] = field(factory=set)
    varied: set[tuple[str, ...]] = field(factory=set)
    statistics: dict[str, object] = field(factory=dict)

    def __attrs_post_init__(self) -> None:
        """
        Initialize zero-coverage reports before any render is attempted.

        Returns:
            None: The live statistics mapping is populated.
        """
        self.refresh()

    def refresh(self) -> None:
        """
        Refresh serializable counters while keeping their shared mapping identity.

        Returns:
            None: Reports reference the latest observed coverage.
        """
        count = len(self.inventory.known)
        self.statistics.update(
            {
                "lower_bound_fields": count,
                "present_fields": [list(path) for path in sorted(self.present)],
                "varied_fields": [list(path) for path in sorted(self.varied)],
                "unvaried_fields": [list(path) for path in sorted(self.inventory.known - self.varied)],
                "present_count": len(self.present),
                "varied_count": len(self.varied),
                "varied_fraction": len(self.varied) / count if count else None,
                "scope": "render inputs; includes failed renders, excludes equivalence-pruned candidates",
                "branch_coverage_proven": False,
            }
        )

    def observe(self, values: dict[str, object]) -> None:
        """
        Credit schema-accepted inputs only when they are handed to the renderer.

        Args:
            values (dict[str, object]): Effective merged values for this render attempt.

        Returns:
            None: Presence and baseline-relative variation are updated.
        """

        def identity(root: object, path: tuple[str, ...]) -> str:
            """
            Preserve omission and scalar type distinctions when comparing field values.

            Args:
                root (object): Values document.
                path (tuple[str, ...]): Named selector without wildcards.

            Returns:
                str: Tagged identity or an explicit missing marker.
            """
            for part in path:
                if not isinstance(root, dict) or part not in root:
                    return "missing"
                root = root[part]
            return configuration_key({"value": root})

        for path in self.inventory.known:
            if has_path(values, path):
                self.present.add(path)
            if identity(values, path) != identity(self.defaults, path):
                self.varied.add(path)
        self.refresh()
