"""
Complete measurement-scope regression coverage and the saved-profile publication contract.
"""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path

import pytest
from hypothesis_helm_benchmarking.execution.resources import METRICS, Resources, Snapshot
from hypothesis_helm_benchmarking.reporting.publication import final_files


def test_counter_reset_or_missing_interval_cannot_become_complete_later() -> None:
    """
    Reject a counter stream that loses observations even if subsequent reads recover.

    Returns:
        None: A broken phase counter remains unavailable instead of reporting a misleading subtotal.
    """
    readings = iter(
        [
            Snapshot(0, 0, 0, 10, 100, 200),
            Snapshot(1, 1, 0, 10, None, 150),
            Snapshot(2, 2, 0, 10, 120, 250),
        ]
    )
    usage = Resources(read=lambda: next(readings))
    usage.transition(usage.active, force=True)
    report = usage.finish()
    phase = report["phases"][0]
    assert phase["values"]["disk_read_bytes"] is None
    assert phase["values"]["disk_write_bytes"] is None
    assert set(phase["unavailable"]) == {"disk_read_bytes", "disk_write_bytes"}


def test_profile_publication_includes_rankings_and_recursive_checksums(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Publish two saved synthetic profile invocations through the actual refresh recipe.

    Args:
        tmp_path (Path): Disposable refresh workspace containing synthetic observations only.
        monkeypatch (pytest.MonkeyPatch): Supply the recipe's explicit CLI argument.

    Returns:
        None: Scaling and finite-worker captures retain raw evidence and every nested resource checksum.
    """
    for invocation, roles in (("scaling", ("coordinator", "worker")), ("finite", ("coordinator", "backend"))):
        directory = tmp_path / "profiles" / f"profile-{invocation}"
        directory.mkdir(parents=True)
        for role in roles:
            data = {
                "format": "hypothesis-helm-profile-v1",
                "role": role,
                "pid": 123,
                "process_id": f"synthetic-{invocation}-{role}",
                "capture_complete": True,
                "truncated_events": 0,
                "frames": [{"label": "synthetic", "parent": -1, "self_seconds": 1, "calls": 1}],
                "resources": {
                    "format": "hypothesis-helm-phase-resources-v1",
                    "phases": [{"name": "Synthetic", "values": dict.fromkeys(METRICS) | {"cpu_seconds": 0.5, "wall_seconds": 1}}],
                },
            }
            (directory / f"{role}-{invocation}.json").write_text(json.dumps(data))
    recipe = Path(__file__).resolve().parents[2] / "pkg/hypothesis_helm_benchmarking/refresh/recipes/publish-flamegraphs.py"
    monkeypatch.setattr(sys, "argv", [str(recipe), str(tmp_path)])
    runpy.run_path(str(recipe), run_name="__main__")
    target = tmp_path / "outputs/flamegraphs"
    assert (target / "resources/README.md").is_file()
    ranks = json.loads((target / "resources/rankings.json").read_text())
    assert set(ranks) == {"backend", "coordinator", "worker"}
    checksums = json.loads((target / "sha256.json").read_text())
    assert "resources/rankings.json" in checksums
    assert all(hashlib.sha256((target / path).read_bytes()).hexdigest() == expected for path, expected in checksums.items())
    assert not list((tmp_path / "profiles").glob("combined-*"))
    target.rename(tmp_path / "prior-publication")
    runpy.run_path(str(recipe), run_name="__main__")
    assert (target / "resources/rankings.json").is_file()
    assert not list((tmp_path / "profiles").glob("combined-*"))


def test_only_compact_phase_rankings_cross_the_study_publication_boundary(tmp_path: Path) -> None:
    """
    Retain compact resource numbers without widening publication to raw profile payloads.

    Args:
        tmp_path (Path): Disposable source and unrelated study output roots.

    Returns:
        None: Only the exact resource-ranking path is eligible for publication.
    """
    source = tmp_path / "flamegraphs"
    (source / "resources").mkdir(parents=True)
    for name in ("rankings.json", "raw.json"):
        (source / "resources" / name).write_text("{}")
    (source / "worker-123.json").write_text("{}")
    assert [str(path.relative_to(source)) for path in final_files(source)] == ["resources/rankings.json"]
    unrelated = tmp_path / "another-study"
    unrelated.mkdir()
    (unrelated / "rankings.json").write_text("{}")
    assert not list(final_files(unrelated))
