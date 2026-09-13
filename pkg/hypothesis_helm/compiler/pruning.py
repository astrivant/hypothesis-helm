"""
Prune only with successful representatives and sound exact-equivalence certificates.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import re
from pathlib import Path

from attrs import define, field, frozen
from jsonschema import validators
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from ruamel.yaml.nodes import Node as YamlNode

from hypothesis_helm.charts import yamlio
from hypothesis_helm.compiler.ir import Node, fold, lower, specialize, value_path, walk
from hypothesis_helm.schemas.contracts import configuration_key, json_value, mapping
from hypothesis_helm.schemas.model import ValuesModel

LOGGER = logging.getLogger(__name__)
VERSION = "helm-pure-equivalence-v1"
EPSILON = 0.5


@frozen
class DistanceBounds:
    """
    Bound discrete manifest distance: zero for equality and one otherwise.

    Attributes:
        lower (float): Sound lower distance bound.
        upper (float): Sound upper distance bound.
    """

    lower: float = 0.0
    upper: float = 1.0

    def decision(self, epsilon: float = EPSILON) -> str:
        """
        Apply strict bound comparisons without interpreting uncertainty as equivalence.

        Args:
            epsilon (float): Exact-equivalence threshold within the discrete metric.

        Returns:
            str: Discard, render-novel, or render-ambiguous.
        """
        if not (0 <= self.lower <= self.upper <= 1) or not math.isfinite(epsilon) or not 0 < epsilon <= 1:
            raise ValueError("invalid discrete distance bounds or epsilon")
        if self.upper < epsilon:
            return "discard"
        if self.lower > epsilon:
            return "render-novel"
        return "render-ambiguous"


def compatible_defaults(source: str, defaults: dict[str, object]) -> bool:
    """
    Reject YAML resolution ambiguities before treating local defaults as Helm inputs.

    Args:
        source (str): Original values file, including lexical scalar forms.
        defaults (dict[str, object]): Values parsed by the ordinary chart loader.

    Returns:
        bool: Defaults lie in the shared JSON-like YAML subset without aliases or merge keys.
    """
    if re.search(r"(?m)^%", source):
        return False
    parser = yamlio.yaml()
    parser.version = (1, 1)
    if configuration_key(mapping(parser.load(source) or {})) != configuration_key(defaults):
        return False
    root = parser.compose(source)
    seen: set[int] = set()

    def admitted(node: YamlNode) -> bool:
        """
        Check scalar lexical forms and disallow aliased or application-tagged nodes.

        Args:
            node (YamlNode): Current composed YAML node.

        Returns:
            bool: This subtree has unambiguous scalar and container semantics.
        """
        if id(node) in seen:
            return False
        seen.add(id(node))
        if isinstance(node, MappingNode):
            return node.tag == "tag:yaml.org,2002:map" and all(
                key.tag == "tag:yaml.org,2002:str" and admitted(key) and admitted(value) for key, value in node.value
            )
        if isinstance(node, SequenceNode):
            return node.tag == "tag:yaml.org,2002:seq" and all(admitted(item) for item in node.value)
        if isinstance(node, ScalarNode):
            if node.tag == "tag:yaml.org,2002:str":
                return True
            if node.tag == "tag:yaml.org,2002:bool":
                return node.value in ("true", "false")
            if node.tag == "tag:yaml.org,2002:int":
                return re.fullmatch(r"-?(0|[1-9][0-9]*)", node.value) is not None
        return False

    return root is None or admitted(root)


def exact_literal(value: object) -> bool:
    """
    Admit exact schema enum constants without floating-point boundary disagreements.

    Args:
        value (object): JSON Schema literal or enum collection.

    Returns:
        bool: Every numeric leaf is an exactly representable bounded integer.
    """
    if value is None or isinstance(value, str) or type(value) is bool:
        return True
    if type(value) is int:
        return abs(value) <= 2**53 - 1
    if isinstance(value, list):
        return all(exact_literal(item) for item in value)
    if isinstance(value, dict):
        return all(exact_literal(item) for item in value.values())
    return False


def safe_schema(schema: object) -> bool:
    """
    Admit only constraints with the same acceptance rules in Python and Helm validators.

    Format checks, regex dialects, references and composition are intentionally
    opaque. All candidate values are still validated before proof lookup.

    Args:
        schema (object): Schema fragment whose validation behavior must be preserved.

    Returns:
        bool: Whether the conservative validation contract covers this schema.
    """
    if isinstance(schema, bool):
        return True
    if not isinstance(schema, dict):
        return False
    dialect = schema.get("$schema")
    if dialect is not None and dialect not in {
        f"{scheme}://json-schema.org/draft-{version}/schema#" for scheme in ("http", "https") for version in ("04", "06", "07")
    }:
        return False
    allowed = {
        "$schema",
        "title",
        "description",
        "default",
        "examples",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }
    for name in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
        if name in schema and (type(schema[name]) is not int or not exact_literal(schema[name])):
            return False
    if any(name in schema and not exact_literal(schema[name]) for name in ("enum", "const")):
        return False
    if set(schema) - allowed or not isinstance(schema.get("additionalProperties", True), bool):
        return False
    return all(safe_schema(child) for child in schema.get("properties", {}).values()) and (
        "items" not in schema or safe_schema(schema["items"])
    )


def safe_values(defaults: object, overrides: object) -> bool:
    """
    Admit ordinary non-null coalescing with exact JSON integers and stable container types.

    Args:
        defaults (object): Original values at the current merge location.
        overrides (object): Incoming candidate override at that location.

    Returns:
        bool: Whether Helm coalescing and scalar representation are within the proof contract.
    """
    if isinstance(overrides, dict):
        if not isinstance(defaults, dict):
            return False
        return all(
            isinstance(key, str) and safe_values(defaults.get(key, {} if isinstance(value, dict) else value), value)
            for key, value in overrides.items()
        )
    if isinstance(defaults, dict):
        return False
    if isinstance(overrides, list):
        return all(safe_values({} if isinstance(value, dict) else value, value) for value in overrides)
    if type(overrides) is bool:
        return True
    if type(overrides) is int:
        return abs(overrides) <= 2**53 - 1
    if isinstance(overrides, str):
        try:
            overrides.encode("utf-8")
        except UnicodeError:
            return False
        return True
    return False


def snapshot(chart: Path) -> dict[str, bytes]:
    """
    Capture chart bytes exactly, refusing links and oversized proof inputs.

    Args:
        chart (Path): Chart directory to guard against mutation during a run.

    Returns:
        dict[str, bytes]: Complete relative file inventory for equality comparisons.
    """
    result = {}
    size = 0
    for path in sorted(chart.rglob("*")):
        if path.is_symlink():
            raise ValueError("chart symlinks are outside the proof contract")
        if path.is_file():
            size += path.stat().st_size
            if size > 16 * 1024 * 1024:
                raise ValueError("chart exceeds the 16 MiB proof input limit")
            result[str(path.relative_to(chart))] = path.read_bytes()
    return result


@frozen
class Witness:
    """
    Identify exact symbolic output and its control-flow partition.

    Attributes:
        key (str): Complete canonical equality key, never a probabilistic digest.
        partition (list[object]): Per-file executed branch decisions.
        influences (list[list[str]]): Candidate-live schema fields.
    """

    key: str
    partition: list[object]
    influences: list[list[str]]


@frozen
class Representative:
    """
    Retain a rendered success; failed or pending candidates never enter this set.

    Attributes:
        iteration (int): Candidate iteration that completed all checks.
        resources (list[dict[str, object]]): Pristine manifests for replaying per-input assertions.
    """

    iteration: int
    resources: list[dict[str, object]]


@define
class Pruner:
    """
    Compile candidate equality witnesses and retain auditable representative links.

    Attributes:
        chart (Path): Original chart location.
        defaults (dict[str, object]): Values used by ordinary Helm coalescing.
        model (ValuesModel): Shared typed values hierarchy.
        files (dict[str, bytes]): Exact chart snapshot guarding certificate lifetime.
        programs (dict[str, tuple[Node, ...]]): Folded per-template symbolic output IR.
        disabled (str | None): Global reason the proof contract cannot cover this chart.
        representatives (dict[str, Representative]): Successfully rendered output classes.
        certificates (list[dict[str, object]]): Accepted equality proofs for skipped invocations.
        reasons (dict[str, int]): Counts of conservative fallback reasons.
        considered (int): Candidate proof lookups.
        rendered (int): Actual renderer invocations attempted.
        influence_matrix (list[dict[str, object]]): Schema fields mapped to surviving output spans.
        stamp (str): Human-readable chart fingerprint; never used alone as proof identity.
    """

    chart: Path
    defaults: dict[str, object]
    model: ValuesModel
    files: dict[str, bytes] = field(factory=dict)
    programs: dict[str, tuple[Node, ...]] = field(factory=dict)
    disabled: str | None = None
    representatives: dict[str, Representative] = field(factory=dict)
    certificates: list[dict[str, object]] = field(factory=list)
    reasons: dict[str, int] = field(factory=dict)
    considered: int = 0
    rendered: int = 0
    influence_matrix: list[dict[str, object]] = field(factory=list)
    stamp: str = ""

    def __attrs_post_init__(self) -> None:
        """
        Compile only charts inside the supported deterministic, dependency-free contract.

        Returns:
            None: Programs and influences are ready, or all candidates will fall back to Helm.
        """
        self.defaults = copy.deepcopy(self.defaults)
        try:
            self.files = snapshot(self.chart)
            self.stamp = hashlib.sha256(repr(sorted(self.files.items())).encode()).hexdigest()
            if any(name.casefold() == ".helmignore" or name.casefold().startswith("charts/") for name in self.files):
                raise ValueError("subcharts and .helmignore are outside the proof contract")
            metadata = mapping(yamlio.load(self.files["Chart.yaml"].decode()))
            if metadata.get("dependencies") or metadata.get("type", "application") != "application":
                raise ValueError("dependencies and library charts are outside the proof contract")
            actual = mapping(yamlio.load(self.files["values.yaml"].decode()) or {})
            if configuration_key(actual) != configuration_key(self.defaults) or not compatible_defaults(
                self.files["values.yaml"].decode(), self.defaults
            ):
                raise ValueError("in-memory defaults differ from Helm's values file")
            disk_schema = json.loads(self.files["values.schema.json"])
            if disk_schema != self.model.root.schema or not safe_schema(disk_schema):
                raise ValueError("schema validation is outside the shared proof contract")
            if not safe_values(self.defaults, self.defaults):
                raise ValueError("default coalescing or scalar types are outside the proof contract")
            for name, source in self.files.items():
                if name.casefold().startswith("templates/"):
                    if not name.startswith("templates/"):
                        raise ValueError("noncanonical template directory casing is outside the proof contract")
                    lowered = lower(source.decode())
                    if any(node.kind == "opaque" and node.text.split(maxsplit=1)[0] in ("define", "block") for node in walk(lowered)):
                        raise ValueError("parse-global template definitions are outside the proof contract")
                    nodes = fold(lowered)
                    self.programs[name] = nodes
                    for node in walk(nodes):
                        path = value_path(node.text) if node.kind in ("if", "emit") else None
                        if path is not None:
                            self.influence_matrix.append(
                                {
                                    "input": list(path),
                                    "declared": self.model.reference(path).target is not None,
                                    "output": {"file": name, "line": node.line},
                                    "transformation": "control" if node.kind == "if" else "scalar-copy",
                                }
                            )
        except (
            OSError,
            ValueError,
            KeyError,
            UnicodeError,
            TypeError,
            RecursionError,
            YAMLError,
        ) as exc:
            self.disabled = str(exc)
        LOGGER.info(
            "Exact-equivalence compiler: %s",
            self.disabled or f"{len(self.programs)} templates lowered",
        )

    def unchanged(self) -> bool:
        """
        Check exact source bytes rather than trusting a digest or timestamp alone.

        Returns:
            bool: Whether the current chart still matches this compilation.
        """
        try:
            return snapshot(self.chart) == self.files
        except (OSError, ValueError):
            return False

    def candidate(self, overrides: dict[str, object], effective: dict[str, object], context: str) -> Witness | None:
        """
        Compile an equality witness after ordinary schema preflight has succeeded.

        Args:
            overrides (dict[str, object]): Original candidate passed to Helm.
            effective (dict[str, object]): Coalesced values under the admitted merge rules.
            context (str): Exact fixed renderer, validator and environment configuration.

        Returns:
            Witness | None: Exact output identity, or unknown requiring actual rendering.
        """
        self.considered += 1
        reason = self.disabled
        if reason is None and not self.unchanged():
            reason = "chart changed since compilation"
        if reason is None and not safe_values(self.defaults, overrides):
            reason = "candidate coalescing or scalar types are outside the proof contract"
        if reason is None:
            expected = copy.deepcopy(self.defaults)

            def merge(base: dict[str, object], incoming: dict[str, object]) -> None:
                """
                Apply the admitted non-null map coalescing rules to the frozen defaults.

                Args:
                    base (dict[str, object]): Mutable expected values.
                    incoming (dict[str, object]): Admitted overrides at this location.

                Returns:
                    None: Expected values receive map merges or scalar replacements.
                """
                for key, value in incoming.items():
                    if isinstance(value, dict) and isinstance(base.get(key), dict):
                        merge(mapping(base[key]), mapping(value))
                    else:
                        base[key] = copy.deepcopy(value)

            merge(expected, overrides)
            if configuration_key(expected) != configuration_key(effective):
                reason = "coalesced values differ from the compiled defaults"
            elif not validators.validator_for(self.model.root.schema)(self.model.root.schema).is_valid(json_value(effective)):
                reason = "candidate violates the compiled schema"
        outputs: list[object] = []
        partitions: list[object] = []
        influences: set[tuple[str, ...]] = set()
        if reason is None:
            for name, nodes in self.programs.items():
                output = specialize(nodes, effective, self.model)
                if output.reason:
                    reason = f"{name}: {output.reason}"
                    break
                outputs.append((name, output.atoms))
                partitions.append((name, output.partition))
                influences.update(output.influences)
        if reason is not None:
            self.reasons[reason] = self.reasons.get(reason, 0) + 1
            return None
        return Witness(
            configuration_key({"outputs": outputs, "partitions": partitions, "context": context}),
            partitions,
            [list(path) for path in sorted(influences)],
        )

    def lookup(self, witness: Witness | None, iteration: int) -> list[dict[str, object]] | None:
        """
        Discard a Helm invocation only when its upper bound proves equality to a success.

        Args:
            witness (Witness | None): Candidate identity or unknown behavior.
            iteration (int): Current iteration for the audit certificate.

        Returns:
            list[dict[str, object]] | None: Fresh representative manifests, or a render request.
        """
        representative = self.representatives.get(witness.key) if witness else None
        bounds = DistanceBounds(0, 0) if representative else DistanceBounds()
        if bounds.decision() != "discard":
            self.rendered += 1
            return None
        assert witness is not None and representative is not None
        self.certificates.append(
            {
                "candidate_iteration": iteration,
                "representative_iteration": representative.iteration,
                "lower_bound": bounds.lower,
                "upper_bound": bounds.upper,
                "epsilon": EPSILON,
                "partition": witness.partition,
                "live_inputs": witness.influences,
                "eliminated_inputs": [
                    list(node.path)
                    for node in self.model.root.walk()
                    if node.path and not node.children and node.item is None and list(node.path) not in witness.influences
                ],
                "certainty": "EXACT",
                "rule": "same-partition-same-symbolic-output",
            }
        )
        return copy.deepcopy(representative.resources)

    def remember(self, witness: Witness | None, iteration: int, resources: list[dict[str, object]]) -> None:
        """
        Commit a representative only after rendering and every configured check passed.

        Args:
            witness (Witness | None): Exact candidate identity, if proved.
            iteration (int): Successful iteration number.
            resources (list[dict[str, object]]): Pristine resources before custom callbacks.

        Returns:
            None: Future equivalent inputs may reuse this completed successful representative.
        """
        if witness is not None and self.unchanged():
            self.representatives.setdefault(witness.key, Representative(iteration, copy.deepcopy(resources)))

    def report(self) -> dict[str, object]:
        """
        Export proof evidence separately from input coverage and actual render counts.

        Returns:
            dict[str, object]: Compiler scope, matrix, bounds and individual representative links.
        """
        return {
            "enabled": True,
            "compiler": VERSION,
            "metric": "discrete-manifest-equality",
            "epsilon": EPSILON,
            "chart_fingerprint": self.stamp,
            "disabled_reason": self.disabled,
            "considered_candidates": self.considered,
            "rendered_candidates": self.rendered,
            "pruned_candidates": len(self.certificates),
            "successful_representatives": len(self.representatives),
            "fallback_reasons": dict(self.reasons),
            "influence_matrix": self.influence_matrix,
            "certificates": self.certificates,
            "coverage_evidence": "rendered-or-proved-equivalent; assertions checked per candidate",
            "proof_scope": ("supported pure expressions, admitted schema/coalescing, fixed trusted Helm and chart environment"),
            "formally_verified": False,
        }
