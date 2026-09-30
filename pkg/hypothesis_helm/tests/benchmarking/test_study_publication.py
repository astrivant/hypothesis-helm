"""
Keep working data out of published studies and preserve usable document links.
"""

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from hypothesis_helm_benchmarking.reporting.publication import STUDIES, publish_study

from hypothesis_helm.reporting.reports.links import link_matches


@pytest.mark.parametrize("suite", ["progressive", "scaling", "all"])
def test_performance_publication_regenerates_its_readme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suite: str) -> None:
    """
    Keep the performance study browsable after replacing earlier published results.

    Args:
        tmp_path (Path): Isolated measurement and publication directories.
        monkeypatch (pytest.MonkeyPatch): Resolve publication paths within the fixture.
        suite (str): Available measurement families, including partial plot suites.

    Returns:
        None: The refreshed README links only available figures and retains raw measurements in the cache.
    """
    from hypothesis_helm_benchmarking.reporting.plots import plot
    from hypothesis_helm_benchmarking.studies.performance import save

    monkeypatch.chdir(tmp_path)
    source = Path(".cache/refresh/run/outputs/performance")
    destination = STUDIES / "performance"
    destination.mkdir(parents=True)
    (destination / "README.md").write_text("Earlier measured results\n")
    guide = Path("docs/benchmarking/README.md")
    guide.parent.mkdir(parents=True)
    guide.write_text("# Benchmarking\n")
    families = ["progressive"] if suite == "progressive" else ["strong", "weak"]
    if suite == "all":
        families.append("progressive")
    document: dict[str, object] = {
        "metadata": {"shard": None, "time_limit_seconds": 9},
        "points": [
            {
                "shard": None,
                "families": families,
                "requested_permutations": count,
                "replicas": 1,
                "repeat": 0,
                "pruning": pruning,
                "status": "passed",
                "completed": count,
                "pruned": count // 2 if pruning else 0,
                "rendered": count // 2 if pruning else count,
                "elapsed_seconds": float(count),
                "completed_per_second": 1.0,
                "workers": [],
            }
            for count in (2, 4)
            for pruning in (False, True)
        ],
    }
    save(source, document)
    plot(source, document)
    published = publish_study(source, destination)
    readme = destination / "README.md"
    assert str(readme) in published
    content = readme.read_text()
    assert "# Performance and scaling" in content
    assert "Earlier measured results" not in content
    assert "local run data" in content
    links = [unquote(urlsplit(match[2] or match[3]).path) for line in content.splitlines() for match in link_matches(line)]
    assert all((readme.parent / target).exists() for target in links)
    assert {target for target in links if target.endswith(".png")} == {path.name for path in source.glob("*.png")}
    assert (source / "results.json").is_file() and not (destination / "results.json").exists()


def test_publication_excludes_workspaces_and_replaces_stale_figures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Publish final documents and figures while preserving raw evidence in the run cache.

    Args:
        tmp_path (Path): Isolated project directory.
        monkeypatch (pytest.MonkeyPatch): Resolve publication paths from that project.

    Returns:
        None: Raw files remain cached; current plots replace stale plots and have valid links.
    """
    monkeypatch.chdir(tmp_path)
    source = Path(".cache/refresh/run/outputs/example")
    destination = STUDIES / "example"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (destination / "old.png").write_bytes(b"old")
    (source / "README.md").write_text(
        "# Example\n\n![Plot](plot.png)\n\n[Raw](results.json)\n\n[Guide](../../docs/benchmarking/README.md#runs)\n"
    )
    (source / "plot.png").write_bytes(b"new")
    (source / "results.json").write_text('{"measured": true}')
    for directory in ("runs", "cases", "reports", "chart"):
        root = source / directory
        root.mkdir()
        (root / "README.md").write_text("Run or fixture, not a published result")
        if directory == "chart":
            (root / "Chart.yaml").write_text("apiVersion: v2\nname: example\nversion: 0.1.0\n")
    # A dependency named charts inside the graph catalog is a legitimate final result.
    nested = source / "catalog/charts/dependency"
    nested.mkdir(parents=True)
    (nested / "graph.png").write_bytes(b"graph")
    published = publish_study(source, destination)
    assert set(published) == {str(destination / name) for name in ("README.md", "plot.png", "catalog/charts/dependency/graph.png")}
    assert not (destination / "old.png").exists()
    assert not (destination / "results.json").exists()
    assert (source / "results.json").read_text() == '{"measured": true}'
    document = (destination / "README.md").read_text()
    assert "![Plot](<plot.png>)" in document
    assert "Raw (local run data)" in document
    assert "[Guide](../../docs/benchmarking/README.md#runs)" in document


def test_empty_or_overlapping_publication_preserves_existing_results(tmp_path: Path) -> None:
    """
    Reject publication without finished files or with source data inside the destination.

    Args:
        tmp_path (Path): Isolated measurement and publication directories.

    Returns:
        None: Validation errors occur before changing the previous report.
    """
    destination = tmp_path / "final"
    destination.mkdir()
    report = destination / "README.md"
    report.write_text("Previous results")
    source = tmp_path / "cache"
    source.mkdir()
    (source / "results.json").write_text("{}")
    with pytest.raises(ValueError, match="No final documents"):
        publish_study(source, destination)
    with pytest.raises(ValueError, match="outside"):
        publish_study(destination, destination)
    assert report.read_text() == "Previous results"
