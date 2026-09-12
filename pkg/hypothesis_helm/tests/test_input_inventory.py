"""
Conservative input inventories, inspectable projections, and honest field coverage.
"""

import json
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import strategies as st

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.compiler.inputs import FieldCoverage, InputInventory


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Construct a chart with both surplus defaults and missing template inputs.

    Args:
        tmp_path (Path): Source chart directory.

    Returns:
        Chart: Declared and undeclared fields with an unreachable reference.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: inventory
        version: 1.0.0
    """)
    )
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: inventory
        data:
          used: {{ .Values.used | quote }}
          hidden: {{ .Values.hidden | default "fallback" | quote }}
          {{ if false }}dead: {{ .Values.dead }}{{ end }}
    """)
    )
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "used": {"type": "boolean"},
            "orphan": {"type": "integer"},
            "documented": {"type": "string"},
        },
    }
    defaults: dict[str, object] = {"used": False, "orphan": 9}
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "values.yaml").write_text(yamlio.dump(defaults))
    return Chart(tmp_path, schema, defaults)


def test_input_discrepancies_and_projection(chart: Chart, tmp_path: Path) -> None:
    """
    Identify hidden fields and surplus defaults without inventing values or dead inputs.

    Args:
        chart (Chart): Source fixture with known discrepancies.
        tmp_path (Path): Output location.

    Returns:
        None: The dump and lower-bound evidence agree with the original document.
    """
    inventory = InputInventory.build(chart)
    report = json.loads(json.dumps(inventory.report()))
    assert report["known_fields"] == [["hidden"], ["used"]]
    assert report["lower_bound_fields"] == 2
    assert report["unreferenced_values"] == [["orphan"]]
    assert [row["path"] for row in report["template_only_fields"]] == [["hidden"]]
    assert ["documented"] in report["schema_fields_without_values"]
    assert (
        next(f for f in inventory.fields if f.reference.path == ("used",)).reference.target
        is not None
    )
    original = (chart.path / "values.yaml").read_bytes()
    target = tmp_path / "minimal.yaml"
    result = inventory.dump(chart, target)
    assert yamlio.load(target.read_text()) == {"used": False}
    assert result["schema_valid"] is True
    assert result["render_equivalence_proven"] is False
    assert result["globally_minimal_proven"] is False
    assert (chart.path / "values.yaml").read_bytes() == original
    assert (
        json.loads(target.with_suffix(".inventory.json").read_text())["input_inventory"][
            "lower_bound_fields"
        ]
        == 2
    )
    with pytest.raises(ValueError, match="overwrite"):
        inventory.dump(chart, chart.path / "values.yaml")


def test_schema_and_opaque_context_prevent_unsafe_reduction(chart: Chart, tmp_path: Path) -> None:
    """
    Retain values when schema obligations or opaque helpers prevent a smaller projection.

    Args:
        chart (Chart): Chart to add required constraints and dynamic access to.
        tmp_path (Path): Dump destination.

    Returns:
        None: Conservative fallback preserves the source values and explains why.
    """
    chart.schema["required"] = ["orphan"]
    inventory = InputInventory.build(chart)
    result = inventory.dump(chart, tmp_path / "required.yaml")
    assert "schema constraints" in str(result["reason"])
    assert yamlio.load((tmp_path / "required.yaml").read_text()) == chart.defaults
    (chart.path / "templates/config.yaml").write_text('{{ include "opaque" . }}\n')
    inventory = InputInventory.build(chart)
    assert inventory.report()["unreferenced_usage"] == "unknown"
    result = inventory.dump(chart, tmp_path / "opaque.yaml")
    assert "Unresolved" in str(result["reason"])
    assert yamlio.load((tmp_path / "opaque.yaml").read_text()) == chart.defaults


def test_dynamic_map_and_array_inventory(chart: Chart) -> None:
    """
    Keep wildcard key spaces outside the finite named-field denominator.

    Args:
        chart (Chart): Chart whose template is replaced with dynamic selectors.

    Returns:
        None: Named roots and unresolved collection regions remain distinct.
    """
    (chart.path / "templates/config.yaml").write_text(
        dedent("""
        {{ index .Values.options .Values.selector }}
        {{ range .Values.items }}{{ .port }}{{ end }}
    """)
    )
    inventory = InputInventory.build(chart)
    assert ("options",) in inventory.dynamic
    assert ("items",) in inventory.dynamic
    assert all("*" not in path for path in inventory.known)
    assert inventory.report()["inventory_complete"] is False


def test_render_input_variation_is_not_presence(
    chart: Chart, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Credit only changed named fields and preserve missing-field gaps after successful renders.

    Args:
        chart (Chart): Two referenced fields, only one supplied by the baseline.
        monkeypatch (pytest.MonkeyPatch): Replace Helm execution with a deterministic manifest.

    Returns:
        None: Successful rendering does not imply every named field was varied.
    """
    monkeypatch.setattr(
        "hypothesis_helm.charts.runner.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}]
    )
    report = check_chart(chart, max_examples=1, input_strategy=st.just({"used": True}))
    assert report["status"] == "passed"
    measured = report["field_coverage"]
    assert isinstance(measured, dict)
    assert measured["present_fields"] == [["used"]]
    assert measured["varied_fields"] == [["used"]]
    assert measured["unvaried_fields"] == [["hidden"]]
    assert measured["varied_fraction"] == 0.5
    baseline = FieldCoverage(InputInventory.build(chart), chart.defaults)
    baseline.observe(chart.defaults)
    assert baseline.statistics["varied_count"] == 0
    baseline.observe({"used": 0})
    assert baseline.statistics["varied_fields"] == [["used"]]


def test_audit_dump_without_schema(
    chart: Chart, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """
    Expose the compiler baseline through audit even without a values schema.

    Args:
        chart (Chart): Source chart with the schema removed.
        capsys (pytest.CaptureFixture[str]): Capture CLI JSON.
        tmp_path (Path): Dump destination.

    Returns:
        None: Audit reports missing documentation and emits reviewable YAML.
    """
    (chart.path / "values.schema.json").unlink()
    target = tmp_path / "dump.yaml"
    assert main(["audit", str(chart.path), "--dump-minimal-values", str(target)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["input_inventory"]["lower_bound_fields"] == 2
    assert report["minimal_values"]["yaml"] == str(target)
    assert yamlio.load(target.read_text()) == {"used": False}


def test_scan_dumps_each_chart(
    chart: Chart,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Put per-chart projections under the requested scan dump directory.

    Args:
        chart (Chart): Root chart and one nested chart.
        tmp_path (Path): Scan and report output locations.
        monkeypatch (pytest.MonkeyPatch): Replace chart execution only.
        capsys (pytest.CaptureFixture[str]): Capture the scan report.

    Returns:
        None: Both chart dumps remain independently inspectable.
    """
    nested = chart.path / "child"
    nested.mkdir()
    (nested / "Chart.yaml").write_text("apiVersion: v2\nname: child\nversion: 1.0.0\n")
    (nested / "values.yaml").write_text("{}\n")
    monkeypatch.setattr(
        "hypothesis_helm.charts.scan.exercise_chart", lambda *args: {"status": "passed"}
    )
    output = tmp_path / "dumps"
    assert (
        main(
            [
                "scan",
                str(chart.path),
                "--helm",
                "/usr/bin/true",
                "--no-build-dependencies",
                "--dump-minimal-values",
                str(output),
                "--artifact-dir",
                str(tmp_path / "out"),
                "--report",
                str(tmp_path / "scan"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert len(report["charts"]) == 2
    assert (output / "minimal-values.yaml").exists()
    assert (output / "child/minimal-values.yaml").exists()
    assert "Identified input fields" in (tmp_path / "scan.md").read_text()


def test_phase_coverage_unions_field_identities(
    chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Count a field once across phases even when both phases vary it.

    Args:
        chart (Chart): Shared original input inventory.
        tmp_path (Path): Phase artifact destination.
        monkeypatch (pytest.MonkeyPatch): Supply overlapping phase measurements.

    Returns:
        None: Aggregate variation uses a union, not a sum or a new denominator.
    """
    from hypothesis_helm.charts.prioritized import check_prioritized

    calls = []

    def phase(source: Chart, **kwargs: object) -> dict[str, object]:
        """
        Return overlapping phase evidence while verifying the shared inventory.

        Args:
            source (Chart): Unmodified original chart.
            **kwargs (object): Phase settings and compiler inventory.

        Returns:
            dict[str, object]: Simulated render-input observations.
        """
        assert source is chart
        calls.append(kwargs["input_inventory"])
        varied = [["used"]] if len(calls) == 1 else [["used"], ["hidden"]]
        return {
            "status": "passed",
            "attempts": 2,
            "field_coverage": {"present_fields": varied, "varied_fields": varied},
        }

    monkeypatch.setattr("hypothesis_helm.charts.prioritized.check_chart", phase)
    result = check_prioritized(
        chart,
        budget=3,
        max_examples=1,
        seed=0,
        helm="helm",
        timeout=1,
        artifacts=tmp_path / "phases",
    )
    assert calls[0] is calls[1]
    measured = result["field_coverage"]
    assert isinstance(measured, dict)
    assert measured["varied_count"] == 2
    assert measured["varied_fraction"] == 1
    assert result["proof_of_totality"] is False


def test_failure_retains_field_coverage(
    chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Persist partial variation evidence alongside a failing render's counterexample.

    Args:
        chart (Chart): Referenced Boolean input with a known default.
        tmp_path (Path): Failure artifact destination.
        monkeypatch (pytest.MonkeyPatch): Fail rendering only for the changed value.

    Returns:
        None: Failure JSON retains the same field denominator and observed variation.
    """

    def render(
        source: Chart, values: dict[str, object], **kwargs: object
    ) -> list[dict[str, object]]:
        """
        Simulate a render failure for the varied input.

        Args:
            source (Chart): Original chart.
            values (dict[str, object]): Render overrides.
            **kwargs (object): Renderer settings.

        Returns:
            list[dict[str, object]]: Baseline manifest, or a failure for changed values.
        """
        if values.get("used"):
            raise AssertionError("changed input failed")
        return [{"kind": "ConfigMap"}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    output = tmp_path / "failure"
    result = check_chart(
        chart, max_examples=1, input_strategy=st.just({"used": True}), artifact_dir=output
    )
    assert result["status"] == "failed"
    saved = json.loads((output / "report.json").read_text())
    assert saved["field_coverage"]["varied_fields"] == [["used"]]
    assert saved["field_coverage"]["lower_bound_fields"] == 2
