"""
Verify measured output projections, retained subsets and their report placement.
"""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from hypothesis_helm.analysis.output_space import ENCODING, manifest_vector, project
from hypothesis_helm.analysis.reference import measure_reference
from hypothesis_helm.analysis.repository import mutations
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.reporting.reports.repository import write_reports
from hypothesis_helm.schemas.contracts import mapping, sequence


def resources(value: object) -> list[dict[str, object]]:
    """
    Produce a simple valid output whose scalar values can vary.

    Args:
        value (object): Distinguishable output observation.

    Returns:
        list[dict[str, object]]: One ConfigMap-like manifest.
    """
    return [{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "example"}, "data": {"observed": value}}]


def test_projection_preserves_types_and_uses_one_reference_frame() -> None:
    """
    Distinguish typed outputs, retain repeated observations and handle degenerate PCA safely.

    Returns:
        None: Coordinates share a centered basis; constant samples remain explicitly rank zero.
    """
    vectors = [manifest_vector(resources(value)) for value in (False, True, 0, "0", 10**400)]
    assert len({tuple(vector) for vector in vectors}) == len(vectors)
    coordinates, metadata = project(vectors)
    assert coordinates.shape == (5, 2)
    assert coordinates.mean(axis=0) == pytest.approx(np.zeros(2), abs=1e-10)
    assert 0 < sum(float(str(value)) for value in sequence(metadata["explained_variance_ratio"])) <= 1
    assert np.array_equal(project(vectors)[0], coordinates)
    same, constant = project([vectors[0], vectors[0]])
    assert constant["rank"] == 0 and np.array_equal(same, np.zeros((2, 2)))
    first, second = resources(1)[0], resources(2)[0]
    assert manifest_vector([first, second]) == manifest_vector([second, first])


@pytest.mark.parametrize("path_mode", [False, True])
def test_reference_uses_real_selectors_and_preserves_baseline(tmp_path: Path, path_mode: bool) -> None:
    """
    Measure one bounded population and apply finite filtering or recorded path ownership.

    Args:
        tmp_path (Path): Chart identity and saved path inventory.
        path_mode (bool): Exercise recorded path selection instead of finite random filtering.

    Returns:
        None: Retained outputs form an exact subset of the measured reference, including defaults.
    """
    defaults: dict[str, object] = {f"field{index}": False for index in range(6)}
    chart = Chart(tmp_path, {"type": "object", "properties": {name: {"type": "boolean"} for name in defaults}}, defaults)
    changes = mutations(defaults, chart.schema, 6, 0)
    record: dict[str, object] = {}
    settings: dict[str, object] = {"trim": 1, "trim_topology": 0, "permutations": 2}
    if path_mode:
        record.update(traversal={}, artifacts=str(tmp_path))
        (tmp_path / "path-inventory.json").write_text(json.dumps({"paths": [list(changes[0].path)]}))
    document = measure_reference(chart, changes, lambda values: resources(values), record, settings, limit=16)
    assert document["planned"] == document["measured"] == 16
    assert document["status"] == "complete" and document["remaining"] == 0
    observations = [mapping(row) for row in sequence(document["observations"])]
    assert observations[0]["retained"] is True
    assert 1 < sum(row["retained"] is True for row in observations) < 16
    assert max(len(sequence(row["paths"])) for row in observations) <= 2
    if path_mode:
        assert all(not row["retained"] or all(path == list(changes[0].path) for path in sequence(row["paths"])) for row in observations)


def test_unavailable_selection_and_failed_outputs_are_not_zero(tmp_path: Path) -> None:
    """
    Keep observed reference outputs when policy records are missing, without inventing retained data.

    Args:
        tmp_path (Path): Synthetic chart identity.

    Returns:
        None: Missing selection remains unknown; render failures never receive a PCA vector.
    """
    chart = Chart(tmp_path, {"type": "object"}, {"enabled": False})

    def render(values: dict[str, object]) -> object:
        """
        Fail only the changed configuration.

        Args:
            values (dict[str, object]): Reference configuration.

        Returns:
            object: The valid baseline output.
        """
        if values["enabled"]:
            raise ValueError("Invalid rendered YAML")
        return resources(False)

    result = measure_reference(chart, mutations(chart.defaults, chart.schema, 2, 0), render, {"traversal": {}}, {"filter": True})
    assert result["measured"] == result["render_failures"] == 1
    assert mapping(sequence(result["observations"])[0])["retained"] is None
    assert result["test_findings_unchanged"] is True


def test_reference_timeout_preserves_completed_outputs(tmp_path: Path) -> None:
    """
    Stop reference rendering on its own deadline without losing a measured baseline.

    Args:
        tmp_path (Path): Synthetic chart identity.

    Returns:
        None: No later render starts; the incomplete sample retains explicit remaining work.
    """
    chart = Chart(tmp_path, {"type": "object"}, {"first": False, "second": False})
    calls = 0

    def render(values: dict[str, object]) -> object:
        """
        Simulate a bounded renderer timing out on its second invocation.

        Args:
            values (dict[str, object]): Selected reference configuration.

        Returns:
            object: Only the first configuration has a completed output.

        Raises:
            TimeoutError: The second render exhausts its allotted time.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TimeoutError("Reference deadline")
        return resources(values)

    result = measure_reference(chart, mutations(chart.defaults, chart.schema, 2, 0), render, {}, {}, limit=4)
    assert result["status"] == "time-limit"
    assert result["planned"] == 4 and result["measured"] == 1 and result["remaining"] == 3
    assert calls == 2
    assert mapping(sequence(result["observations"])[0])["retained"] is True


@pytest.mark.parametrize("count", [2, 115])
def test_output_pca_follows_graph_appendix_after_results(tmp_path: Path, count: int) -> None:
    """
    Put PCA after the graph appendix while preserving the chart links on page three.

    Args:
        tmp_path (Path): Published Markdown, figures and PDF.
        count (int): Small or real-repository-sized chart inventory.

    Returns:
        None: Results start on page four; the aggregate graphs follow them on separate appendix pages.
    """
    study = tmp_path / "studies/chart-topologies"
    (study / "chart-0").mkdir(parents=True)
    (study / "README.md").write_text("| charts | [chart-0](chart-0/README.md) | rendered | 10 | 15 | 2 | 7 |\n")
    Image.new("RGB", (400, 240), "green").save(study / "chart-0/topology.png")
    charts = [
        {
            "chart": f"chart-{index}",
            "status": "passed",
            "testing_seconds": 2,
            "output_space": {
                "encoding": ENCODING,
                "observations": [
                    {"vector": manifest_vector(resources(index)), "retained": True},
                    {"vector": manifest_vector(resources(index + 1)), "retained": False},
                ],
            },
        }
        for index in range(count)
    ]
    report: dict[str, object] = {
        "directory": "charts",
        "started_epoch": 1,
        "elapsed_seconds": 2,
        "charts_discovered": count,
        "counts": {"passed": count},
        "settings": {},
        "charts": charts,
    }
    markdown, pdf = write_reports(report, tmp_path / "report")
    assert (tmp_path / "report-pca.png").is_file()
    with Image.open(tmp_path / "report-topology.png") as graph:
        assert graph.height / graph.width > 0.9  # A full page with the two plots stacked vertically.
    content = markdown.read_text()
    assert content.index("![Chart severity") < content.index("## Scan summary") < content.index("## Charts")
    assert content.index(f"### chart-{count - 1}\n") < content.index("## Appendix: graph structure") < content.index("![Output-space PCA")
    assert "| 01 | [chart-0](#chart-0) | 2 / 1 |" in content
    assert mapping(report["output_pca"])["retained_observations"] == count
    objects = dict(re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", pdf.read_bytes(), re.DOTALL))
    pages = [(number, body) for number, body in objects.items() if b"/Type /Page\n" in body]
    assert len(re.findall(rb"/FormXob\.[^\s]+ \d+ 0 R", pages[2][1])) == 2
    graph_outline = next(body for body in objects.values() if b"/Title (Appendix: graph structure)" in body)
    graph_page = next(index for index, (number, _) in enumerate(pages) if b"/Dest [ " + number + b" 0 R" in graph_outline)
    assert graph_page > 3
    assert len(re.findall(rb"/FormXob\.[^\s]+ \d+ 0 R", pages[graph_page][1])) == 2
    assert len(re.findall(rb"/FormXob\.[^\s]+ \d+ 0 R", pages[graph_page + 1][1])) == 2
    outline = next(body for body in objects.values() if b"/Title (Appendix: output space)" in body)
    assert b"/Dest [ " + pages[graph_page + 1][0] + b" 0 R" in outline
    summary = next(body for body in objects.values() if b"/Title (Scan summary)" in body)
    assert b"/Dest [ " + pages[3][0] + b" 0 R" in summary
    links = [body for body in objects.values() if b"/Contents (Chart 01: chart-0)" in body]
    assert len(links) == 2
    assert links[0].split(b"/Dest", 1)[1].split(b"]", 1)[0] == links[1].split(b"/Dest", 1)[1].split(b"]", 1)[0]
