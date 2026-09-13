"""
Verify value-free structure markers survive runs without replacing result fingerprints.
"""

import base64
import json
from pathlib import Path

import pytest

from hypothesis_helm.execution.estimate import estimate_suite
from hypothesis_helm.execution.structure import inspect_structure, structure
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.schemas.contracts import mapping


def test_marker_canonical_structure(tmp_path: Path) -> None:
    """
    Ignore scalar contents and key order while reporting added and removed paths.

    Args:
        tmp_path (Path): Saved suite and cache root.

    Returns:
        None: Encoded structure contains keys and containers but no scalar values.
    """
    values = tmp_path / "values.coalesced.yaml"
    values.write_text("password: private-scalar\nitems:\n  - name: first\nold: 42\n")
    marker = inspect_structure(tmp_path, tmp_path / "cache", 0)
    assert marker is not None and marker.status == "new"
    decoded = base64.b64decode(marker.encoded).decode()
    assert "private-scalar" not in decoded and "first" not in decoded and "42" not in decoded
    assert json.loads(decoded) == {"object": {"password": None, "items": {"array": [{"object": {"name": None}}]}, "old": None}}
    marker.save()
    original = marker.destination.read_bytes()
    values.write_text("old: null\nitems:\n  - name: second\npassword: changed\n")
    unchanged = inspect_structure(tmp_path, tmp_path / "cache", 0)
    assert unchanged is not None and unchanged.status == "unchanged"
    assert unchanged.added == unchanged.removed == ()
    values.write_text("items:\n  - name: second\n  - name: third\npassword: changed\nnew: false\n")
    changed = inspect_structure(tmp_path, tmp_path / "cache", 0)
    assert changed is not None and changed.status == "changed"
    assert set(changed.added) == {"$.items[1]", "$.items[1].name", "$.new"}
    assert changed.removed == ("$.old",)
    assert marker.destination.read_bytes() == original
    other_seed = inspect_structure(tmp_path, tmp_path / "cache", 1)
    assert other_seed is not None and other_seed.status == "new"
    marker.destination.write_text("not base64")
    corrupt = inspect_structure(tmp_path, tmp_path / "cache", 0)
    assert corrupt is not None and corrupt.status == "invalid-cache"


def test_source_values_take_precedence(tmp_path: Path) -> None:
    """
    Record the original chart tree rather than inferred fields in the generated snapshot.

    Args:
        tmp_path (Path): Chart, logical suite, and staged dry-run directories.

    Returns:
        None: Coalescing and temporary generation locations do not change marker identity.
    """
    chart = tmp_path / "chart"
    chart.mkdir()
    (chart / "values.yaml").write_text("explicit: value\n")
    logical = tmp_path / "suite"
    logical.mkdir()
    (logical / "chart-source.json").write_text('{"chart":"../chart"}')
    (logical / "values.coalesced.yaml").write_text("explicit: value\ninferred: fallback\n")
    marker = inspect_structure(logical, tmp_path / "cache", 0)
    assert marker is not None and marker.added == ("$.explicit",)
    staged = tmp_path / "other" / "staged"
    staged.mkdir(parents=True)
    (staged / "chart-source.json").write_text('{"chart":"../chart"}')
    assert inspect_structure(staged, tmp_path / "cache", 0, suite_location=logical) == marker
    marker.save()
    relocated = tmp_path / "runner" / "suite"
    relocated.mkdir(parents=True)
    relocated_chart = relocated.parent / "chart"
    relocated_chart.mkdir()
    (relocated_chart / "values.yaml").write_text("explicit: another-value\n")
    (relocated / "chart-source.json").write_text('{"chart":"../chart"}')
    restored = inspect_structure(relocated, tmp_path / "cache", 0)
    assert restored is not None and restored.status == "unchanged"
    assert restored.destination == marker.destination


def test_execution_and_estimate_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Update markers after execution and inspect them without changes during dry runs.

    Args:
        tmp_path (Path): Saved suite and report directory.
        monkeypatch (pytest.MonkeyPatch): Force local retry defaults.

    Returns:
        None: Structure comparisons remain independent of scalar-sensitive outcome caching.
    """
    monkeypatch.setenv("CI", "false")
    (tmp_path / "test_chart_values.py").write_text("def test_pass(): pass\n")
    values = tmp_path / "values.coalesced.yaml"
    values.write_text("field: first\n")
    assert run_suite(tmp_path, jobs=1) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["values_structure"]["status"] == "new"
    destination = Path(report["values_structure"]["marker"])
    original = destination.read_bytes()
    assert estimate_suite(tmp_path)["scheduled_properties"] == 0
    values.write_text("field: changed\n")
    plan = estimate_suite(tmp_path)
    assert mapping(plan["values_structure"])["status"] == "unchanged"
    assert plan["scheduled_properties"] == 1
    values.write_text("field: changed\nextra: true\n")
    plan = estimate_suite(tmp_path)
    assert mapping(plan["values_structure"])["status"] == "changed"
    assert mapping(plan["values_structure"])["added_paths"] == ["$.extra"]
    assert destination.read_bytes() == original
    assert run_suite(tmp_path, jobs=1, disable_schema_caching=True) == 0
    assert destination.read_bytes() == original
    assert run_suite(tmp_path, collect_only=True) == 0
    assert run_suite(tmp_path, jobs=1, cache=False) == 0
    assert destination.read_bytes() == original
    assert run_suite(tmp_path, jobs=1) == 0
    assert destination.read_bytes() != original


def test_recursive_alias_rejected() -> None:
    """
    Reject cyclic aliases while permitting shared nonrecursive subtrees.

    Returns:
        None: Structure encoding terminates without storing scalar data.
    """
    value: dict[str, object] = {}
    value["cycle"] = value
    with pytest.raises(ValueError, match="recursive YAML"):
        structure(value)
    child = {"key": "secret"}
    assert structure({"a": child, "b": child}) == {"object": {"a": {"object": {"key": None}}, "b": {"object": {"key": None}}}}
