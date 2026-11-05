"""
Own one disposable benchmark chart and retain small, reproducible case descriptions.
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path
from types import TracebackType

from attrs import define, field
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.schemas.contracts import mapping

__all__ = ("FixtureWorkspace", "case_path", "chart_path", "read_spec", "record_change")


def chart_path(logical: Path, *, workspace: FixtureWorkspace | None = None) -> Path:
    """
    Resolve a generated case to the invocation's single chart workspace.

    Args:
        logical (Path): Original logical case location or an external user chart.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        Path: Owned chart location for registered cases; external charts are unchanged.

    Raises:
        ValueError: A previous case was replaced; regenerate its retained recipe first.
    """
    if workspace is not None and logical.resolve() in workspace.cases:
        if logical.resolve() != workspace.current:
            raise ValueError(f"case is no longer active; replay {case_path(logical)} first")
        return workspace.chart
    return logical


def case_path(logical: Path) -> Path:
    """
    Locate a retained parameter record without creating another Helm chart.

    Args:
        logical (Path): Logical case location used by a study.

    Returns:
        Path: Small YAML record next to the study's results.
    """
    if logical.parent.name == "charts":
        return logical.parent.parent / "cases" / (logical.name + ".yaml")
    return logical.parent / (logical.name + "-parameters.yaml")


def read_spec(logical: Path) -> dict[str, object]:
    """
    Read retained case metadata, including older published chart snapshots.

    Args:
        logical (Path): Logical case location.

    Returns:
        dict[str, object]: Independent oracle metadata for that case.
    """
    record = case_path(logical)
    if record.is_file():
        return mapping(mapping(yamlio.load(record.read_text()))["oracle"])
    return mapping(json.loads((logical / "benchmark.json").read_text()))


def record_change(logical: Path, name: str, parameters: dict[str, object], *, workspace: FixtureWorkspace | None = None) -> None:
    """
    Retain fault-injection parameters applied after initial chart generation.

    Args:
        logical (Path): Logical fixture location.
        name (str): Deterministic post-generation operation.
        parameters (dict[str, object]): Inputs needed to repeat that operation.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        None: The case record contains the complete generation recipe.
    """
    compiled = chart_path(logical, workspace=workspace)
    description = compiled / "benchmark-parameters.yaml"
    if description.is_file():
        document = mapping(yamlio.load(description.read_text()))
        mapping(document.setdefault("operations", {}))[name] = parameters
        description.write_text(yamlio.dump(document))
    if workspace is not None and logical.resolve() in workspace.cases:
        record = case_path(logical)
        document = mapping(yamlio.load(record.read_text()))
        mapping(document.setdefault("operations", {}))[name] = parameters
        document["oracle"] = mapping(json.loads((workspace.chart / "benchmark.json").read_text()))
        record.write_text(yamlio.dump(document))


@define
class FixtureWorkspace:
    """
    Isolate concurrent commands while reusing one chart across each command's cases.

    Attributes:
        cases (set[Path]): Logical case locations registered by the generator.
        chart (Path): Only physical chart compiled during this invocation.
        current (Path | None): Logical identity of the currently compiled case.
    """

    cases: set[Path] = field(factory=set)
    chart: Path = field(init=False)
    current: Path | None = None
    _temporary: tempfile.TemporaryDirectory[str] | None = field(default=None, init=False)

    def __enter__(self) -> FixtureWorkspace:
        """
        Allocate an isolated chart and make it available to benchmark generation.

        Returns:
            FixtureWorkspace: Active owner of the invocation's chart.
        """
        self._temporary = tempfile.TemporaryDirectory(prefix="hypothesis-helm-benchmark-")
        self.chart = Path(self._temporary.name).resolve() / "chart"
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None) -> None:
        """
        Remove the disposable chart after all benchmark workers have joined.

        Args:
            kind (type[BaseException] | None): Exception type leaving the command.
            error (BaseException | None): Active exception.
            traceback (TracebackType | None): Active traceback.

        Returns:
            None: Case records remain; chart files are released.
        """
        if self._temporary is not None:
            self._temporary.cleanup()

    def prepare(self, logical: Path) -> Path:
        """
        Reset only this invocation's owned chart before compiling another case.

        Args:
            logical (Path): Logical identity used to retain case parameters.

        Returns:
            Path: Reusable chart directory with no previous case content.
        """
        self.cases.add(logical.resolve())
        self.current = logical.resolve()
        if self.chart.exists():
            shutil.rmtree(self.chart)
        return self.chart

    def record(self, logical: Path, parameters: dict[str, object], spec: dict[str, object]) -> None:
        """
        Save a reproducible recipe and oracle without copying generated chart sources.

        Args:
            logical (Path): Logical case identity.
            parameters (dict[str, object]): Generator arguments.
            spec (dict[str, object]): Independent output and topology metadata.

        Returns:
            None: Human-readable YAML captures the configuration used for the case.
        """
        target = case_path(logical)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = mapping(yamlio.load(target.read_text()))
            if existing["parameters"] != parameters or existing["oracle"] != spec:
                raise ValueError(f"case parameters differ from the retained record: {target}")
            return
        target.write_text(yamlio.dump({"format": 1, "parameters": copy.deepcopy(parameters), "oracle": copy.deepcopy(spec)}))
