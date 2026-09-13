"""
Verify structured failure comparisons and exact JSON replay against real Helm output.
"""

import copy
import json
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, check_chart, merge_values, render
from hypothesis_helm.cli import main
from hypothesis_helm.reporting.changes import compare, digest, replay
from hypothesis_helm.reporting.repository import write_reports
from hypothesis_helm.reporting.reproductions import changed_values
from hypothesis_helm.schemas.contracts import mapping, sequence

JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text(),
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(), children, max_size=5),
    max_leaves=15,
)


@given(JSON_VALUES, JSON_VALUES)
@settings(max_examples=100, deadline=None)
def test_json_delta_round_trip(before: object, after: object) -> None:
    """
    Reconstruct arbitrary nested JSON without conflating scalar types or mutating inputs.

    Args:
        before (object): Original baseline.
        after (object): Target document.

    Returns:
        None: Serialized replay preserves the complete target and both source documents.
    """
    original = copy.deepcopy([before, after])
    record = json.loads(json.dumps(compare(before, after)))
    assert digest(replay(before, record)) == digest(after)
    assert digest([before, after]) == digest(original)


def test_helm_overrides_and_typed_differences() -> None:
    """
    Preserve inheritance, deletion, list replacement, and nested Boolean/numeric changes.

    Returns:
        None: Effective values and exact override replay serve distinct, correct purposes.
    """
    defaults = {"keep": 7, "remove": 3, "map": {"left": 1, "right": 2}, "list": [0, 1], "number": 1}
    overrides: dict[str, object] = {"remove": None, "map": {"left": 0}, "list": [False], "number": 1.0}
    effective = merge_values(defaults, overrides)
    assert effective == {"keep": 7, "map": {"left": 0, "right": 2}, "list": [False], "number": 1.0}
    assert changed_values({"list": [False]}, {"list": [0]}) == {"$.list": [False]}
    assert changed_values({"list": [{"x": 1.0}]}, {"list": [{"x": 1}]}) == {"$.list": [{"x": 1.0}]}
    assert replay({}, compare({}, overrides)) == overrides
    assert digest(replay(defaults, compare(defaults, effective))) == digest(effective)
    assert compare({"b": 1, "a": 2}, {"a": 2, "b": 1})["changes"] == []
    assert compare([0, 1], [1, 0])["changes"]
    yaml_values = yamlio.load('quoted: "hello"\nnumber: 1.0\n')
    assert compare(yaml_values, {"quoted": "hello", "number": 1.0})["changes"] == []


@pytest.mark.parametrize("before,after", [(0.0, -0.0), ({"a'\"[0]": 1}, {"a'\"[0]": 2})])
def test_exact_replay_when_field_delta_is_insufficient(before: object, after: object) -> None:
    """
    Retain a verified full replacement when signed zero or quoted keys defeat field replay.

    Args:
        before (object): Baseline exposing an upstream delta limitation.
        after (object): Exact target document.

    Returns:
        None: An explicitly labeled replacement retains exact data without silent loss.
    """
    record = compare(before, after)
    assert "whole-document replacement" in str(record["representation"])
    assert digest(replay(before, json.loads(json.dumps(record)))) == digest(after)


def test_replay_rejects_stale_and_corrupt_records() -> None:
    """
    Verify unchanged baseline fields, target hashes, and allowed delta type metadata.

    Returns:
        None: Incorrect records fail before a result can be published.
    """
    baseline = {"changed": 1, "untouched": "original"}
    record = compare(baseline, {**baseline, "changed": False})
    with pytest.raises(ValueError, match="baseline checksum"):
        replay({**baseline, "untouched": "stale"}, record)
    with pytest.raises(ValueError, match="result checksum"):
        replay(baseline, {**record, "result_sha256": "invalid"})
    bad = copy.deepcopy(record)
    change = mapping(mapping(mapping(bad["delta"])["type_changes"])["root['changed']"])
    change["new_type"] = "arbitrary.module.Type"
    with pytest.raises(ValueError, match="unsupported delta"):
        replay(baseline, bad)
    assert digest(baseline) == record["baseline_sha256"]


def test_replay_cli_preserves_helm_text_and_output_on_error(tmp_path: Path) -> None:
    """
    Write Helm-compatible Unicode and leave an existing output untouched on verification failure.

    Args:
        tmp_path (Path): JSON record and replay output directory.

    Returns:
        None: Supplemental Unicode stays literal, and bad hashes never overwrite output.
    """
    values = {"text": "\U0001f4dc", "delete": None}
    record = tmp_path / "changes.json"
    record.write_text(json.dumps({"overrides": compare({}, values)}))
    output = tmp_path / "values.json"
    assert main(["replay-changes", str(record), "--output", str(output)]) == 0
    assert "\U0001f4dc" in output.read_text()
    assert yamlio.load(output.read_text()) == values
    previous = output.read_bytes()
    bad = compare({}, values)
    bad["result_sha256"] = "bad"
    record.write_text(json.dumps({"overrides": bad}))
    assert main(["replay-changes", str(record), "--output", str(output)]) == 2
    assert output.read_bytes() == previous
    assert main(["replay-changes", str(record), "--section", "manifests", "--output", str(output)]) == 2
    assert output.read_bytes() == previous


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["property", "validation", "template", "shared-baseline"])
def test_failure_artifacts_and_replay(tmp_path: Path, mode: str) -> None:
    """
    Save genuine observed outputs and replay exact overrides without additional Helm runs.

    Args:
        tmp_path (Path): Native chart and report artifact directory.
        mode (str): Failure before parsing, during validation, in a property, or after reusing a path baseline.

    Returns:
        None: Reports stay concise, usable outputs replay, and missing renders are explicit.
    """
    chart_path = tmp_path / "chart"
    (chart_path / "templates").mkdir(parents=True)
    (chart_path / "Chart.yaml").write_text("apiVersion: v2\nname: changes\nversion: 1.0.0\n")
    defaults: dict[str, object] = {"name": "example", "value": "good"}
    (chart_path / "values.yaml").write_text(yamlio.dump(defaults))
    (chart_path / "templates/config.yaml").write_text(
        dedent("""
        {{ if eq .Values.value "reject" }}{{ fail "unsupported value" }}{{ end }}
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: {{ .Values.name | quote }}
        data:
          example: {{ .Values.value | quote }}
        """)
    )
    chart = Chart(chart_path, {"type": "object"}, defaults)
    overrides: dict[str, object] = {"name": ""} if mode == "validation" else {"value": "reject" if mode == "template" else "bad"}

    def property_check(resources: list[dict[str, object]]) -> None:
        """
        Reject a rendered data value after mutating the caller-owned manifest copy.

        Args:
            resources (list[dict[str, object]]): Observed manifest bundle.

        Returns:
            None: Original failing output must survive property mutation in the report.
        """
        data = mapping(resources[0]["data"])
        if data["example"] == "bad":
            data["example"] = "mutated by test"
            raise AssertionError("example must be good")

    artifacts = tmp_path / "artifacts"
    report = check_chart(
        chart,
        input_strategy=st.just(overrides),
        max_examples=1,
        artifact_dir=artifacts,
        properties=(property_check,),
        fail_fast=True,
        check_defaults=mode != "shared-baseline",
        baseline_resources=render(chart, {}) if mode == "shared-baseline" else None,
    )
    assert report["status"] == "failed"
    assert report["attempts"] == (1 if mode == "shared-baseline" else 2)
    records = mapping(report["comparisons"])
    assert json.loads((artifacts / "changes.json").read_text()) == records
    assert replay({}, mapping(records["overrides"])) == overrides
    reconstructed = tmp_path / "replayed.json"
    assert main(["replay-changes", str(artifacts / "changes.json"), "--output", str(reconstructed)]) == 0
    assert json.loads(reconstructed.read_text()) == overrides
    if mode == "template":
        assert "unavailable" in mapping(records["manifests"])
        assert not (artifacts / "manifests-baseline.json").exists()
    else:
        original = json.loads((artifacts / "manifests-baseline.json").read_text())
        output = sequence(replay(original, mapping(records["manifests"])))
        resource = mapping(output[0])
        assert mapping(resource["data"])["example"] == ("good" if mode == "validation" else "bad")
        assert (
            main(
                [
                    "replay-changes",
                    str(artifacts / "changes.json"),
                    "--section",
                    "manifests",
                    "--baseline",
                    str(artifacts / "manifests-baseline.json"),
                    "--output",
                    str(reconstructed),
                ]
            )
            == 0
        )
        assert json.loads(reconstructed.read_text()) == output
    aggregate = {
        "directory": str(chart_path),
        "started_epoch": 1,
        "elapsed_seconds": 1,
        "charts_discovered": 1,
        "counts": {"failed": 1},
        "settings": {},
        "charts": [{**report, "artifacts": str(artifacts)}],
    }
    markdown, pdf = write_reports(aggregate, tmp_path / "report")
    content = markdown.read_text()
    assert "(was " in content
    assert ("Manifest changes from rendered defaults" in content) == (mode != "template")
    assert "mutated by test" not in content
    assert len(content) < 6000
    assert pdf.read_bytes().startswith(b"%PDF")
