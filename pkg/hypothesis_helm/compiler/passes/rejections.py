"""
Guide generation with explicit rejection contracts and retain real Helm witness checks.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable

from attrs import define, field

from hypothesis_helm.compiler.asts.contracts import Contracts, Rejection
from hypothesis_helm.schemas.contracts import configuration_key


def matches_rejection(error: str, rejection: Rejection) -> bool:
    """
    Confirm an actual Helm execution rejection with the exact chart-authored message.

    Args:
        error (str): Native Helm failure diagnostic.
        rejection (Rejection): Evaluated explicit contract.

    Returns:
        bool: Whether Helm rejected the input with this precise message.
    """
    diagnostic = re.sub(r"(?m)^Use --debug flag to render out invalid YAML\s*$", "", error).strip()
    match = re.search(r"execution error at \([^)]+\):\s*(.*)", diagnostic, re.DOTALL)
    return match is not None and " ".join(match[1].split()) == " ".join(rejection.message.split())


@define
class RejectionPolicy:
    """
    Track bounded witness checks, exclusions, and dependent-input adjustments per chart.

    Attributes:
        contracts (Contracts): Supported template AST and helper-call relationships.
        defaults (dict[str, object]): Chart defaults available for deterministic repair candidates.
        declared_schema (bool): Preserve failures admitted by an authored values schema.
        verify_every_candidate (bool): Require native confirmation when dependency coalescing is not modeled completely.
        records (dict[str, dict[str, object]]): Rejection evidence and bounded representative cases.
        witnesses (dict[str, set[str]]): Distinct inputs whose rejection Helm verified.
        disabled (set[str]): Contracts contradicted by native execution.
        candidates (int): Generated candidates classified as explicit rejections.
        filtered (int): Rejected candidates excluded without an accepted replacement.
        adjusted (int): Candidates replaced by a nearby schema-valid configuration.
        probes (int): Actual Helm calls made to verify rejection witnesses.
        contradictions (int): Native outcomes disagreeing with the predicted rejection.
        schema_conflicts (int): Observed rejections of inputs admitted by the declared schema.
    """

    contracts: Contracts
    defaults: dict[str, object]
    declared_schema: bool = False
    verify_every_candidate: bool = False
    records: dict[str, dict[str, object]] = field(factory=dict)
    witnesses: dict[str, set[str]] = field(factory=dict)
    disabled: set[str] = field(factory=set)
    candidates: int = 0
    filtered: int = 0
    adjusted: int = 0
    probes: int = 0
    contradictions: int = 0
    schema_conflicts: int = 0

    def predict(self, values: dict[str, object]) -> Rejection | None:
        """
        Return an enabled contract prediction without classifying unknown branches.

        Args:
            values (dict[str, object]): Coalesced candidate configuration.

        Returns:
            Rejection | None: Supported enabled rejection or no filtering decision.
        """
        rejection = self.contracts.predict(values)
        if rejection is None or rejection.key in self.disabled or (rejection.key not in self.records and len(self.records) >= 64):
            return None
        return rejection

    def needs_probe(self, rejection: Rejection, values: dict[str, object]) -> bool:
        """
        Request native verification for initial witnesses or every candidate when required.

        Args:
            rejection (Rejection): Predicted explicit rejection.
            values (dict[str, object]): Effective input being classified.

        Returns:
            bool: Whether native verification is still needed for this witness.
        """
        seen = self.witnesses.get(rejection.key, set())
        return self.verify_every_candidate or (len(seen) < 2 and configuration_key(values) not in seen)

    def verified(self, rejection: Rejection, values: dict[str, object]) -> None:
        """
        Retain a verified witness without ever storing it as a successful chart test.

        Args:
            rejection (Rejection): Contract that Helm also rejected.
            values (dict[str, object]): Effective rejected input.

        Returns:
            None: Witness identities and bounded explanatory examples are recorded.
        """
        seen = self.witnesses.setdefault(rejection.key, set())
        identity = configuration_key(values)
        fresh = identity not in seen
        if len(seen) < 2:
            seen.add(identity)
        record = self.records.setdefault(rejection.key, {**rejection.report(), "occurrences": 0, "examples": []})
        examples = record["examples"]
        assert isinstance(examples, list)
        if len(examples) < 2 and fresh:
            examples.append(rejection.report())

    def repair(
        self,
        values: dict[str, object],
        rejection: Rejection,
        protected: tuple[tuple[str | int, ...], ...],
        accept: Callable[[dict[str, object]], bool],
    ) -> dict[str, object] | None:
        """
        Try bounded single-field changes while preserving the selected path and chart schema.

        Args:
            values (dict[str, object]): Original overrides.
            rejection (Rejection): Evaluated contract and dependent paths.
            protected (tuple[tuple[str | int, ...], ...]): Selected fields that must remain unchanged.
            accept (Callable[[dict[str, object]], bool]): Schema and rejection checks on a replacement.

        Returns:
            dict[str, object] | None: Nearby candidate requiring real testing, or no supported repair.
        """
        attempts = 0
        for name, value in rejection.inputs.items():
            path = tuple(name.removeprefix("$.").split("."))
            if any(all(left == right or right == "*" for left, right in zip(path, item, strict=False)) for item in protected):
                continue
            default: object = self.defaults
            for key in path:
                default = default.get(key) if isinstance(default, dict) else None
            alternatives = [default] if default is not None else []
            if type(value) is bool:
                alternatives.append(not value)
            if type(value) is int:
                alternatives.extend([0, 1, value - 1, value + 1])
            for alternative in alternatives:
                if type(alternative) is type(value) and alternative == value:
                    continue
                attempts += 1
                if attempts > 32:
                    return None
                candidate = copy.deepcopy(values)
                current = candidate
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    child = current[key]
                    if not isinstance(child, dict):
                        break
                    current = child
                else:
                    current[path[-1]] = copy.deepcopy(alternative)
                    if accept(candidate):
                        return candidate
        return None

    def snapshot(self) -> dict[str, object]:
        """
        Report configuration exclusions independently from passes, failures, and render attempts.

        Returns:
            dict[str, object]: Counters, source requirements, bounded witnesses, and unsupported-source diagnostics.
        """
        return {
            "enabled": True,
            "rejected_candidates": self.candidates,
            "filtered_candidates": self.filtered,
            "adjusted_candidates": self.adjusted,
            "verification_renders": self.probes,
            "verify_every_candidate": self.verify_every_candidate,
            "classifier_disagreements": self.contradictions,
            "declared_schema": self.declared_schema,
            "schema_conflicts": self.schema_conflicts,
            "requirements": copy.deepcopy(list(self.records.values())),
            "unsupported_sources": self.contracts.diagnostics,
            "scope": "Explicit chart rejection contracts; unknown branches are tested normally. Not a proof of valid chart semantics.",
        }
