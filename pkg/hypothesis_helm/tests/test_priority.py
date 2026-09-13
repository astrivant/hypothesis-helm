"""
Known-input ordering retains original contracts and dynamic map coverage.
"""

import copy
import json
import shutil
import unicodedata
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import find, given, settings
from jsonschema import validators

from hypothesis_helm.charts.prioritized import check_prioritized
from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.schemas.contracts import json_value, mapping, schema_strategy
from hypothesis_helm.schemas.priority import PriorityInputs


@pytest.mark.parametrize("deferred", [False, True])
def test_sampled_control_characters_are_excluded(tmp_path: Path, deferred: bool) -> None:
    """
    Exclude the nginx reproducer and nested control-character keys in both phases.

    Args:
        tmp_path (Path): Empty chart template directory.
        deferred (bool): Exercise original-schema robustness instead of known inputs.

    Returns:
        None: Every sample obeys the character policy and the unchanged chart schema.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "existingContextEventsConfigmaps": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2},
        },
        "required": ["existingContextEventsConfigmaps"],
    }
    chart = Chart(tmp_path, copy.deepcopy(schema), {"existingContextEventsConfigmaps": []})
    priority = PriorityInputs.build(chart)
    strategy = priority.deferred_strategy(chart) if deferred else priority.strategy(chart)

    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(strategy)
    def check(values: dict[str, object]) -> None:
        """
        Inspect the complete generated JSON tree, including arbitrary nested keys.

        Args:
            values (dict[str, object]): Sampled chart overrides.

        Returns:
            None: Each string contains text or permitted configuration whitespace.
        """
        assert validators.validator_for(schema)(schema).is_valid(json_value(values))
        pending: list[object] = [values]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                assert all(unicodedata.category(char) != "Cc" or char in "\n\r" for char in item)
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)

    check()
    assert chart.schema == schema


@pytest.mark.parametrize("value", ["café", "日本語", "🔑", "line 1\n  line 2\r\n"])
def test_text_sampling_retains_application_content(value: str) -> None:
    """
    Keep Unicode application text and multiline configuration eligible for sampling.

    Args:
        value (str): Meaningful text that must remain in the sampled domain.

    Returns:
        None: Allowed text survives sampling alongside an excluded control character.
    """
    strategy = schema_strategy({"type": "string", "enum": ["\x1f", "\t", value]})
    found = find(strategy, lambda candidate: True, settings=settings(max_examples=20, deadline=None, derandomize=True))
    assert found == value


def test_constrained_sampling_excludes_tabs() -> None:
    """
    Drop tab-only alternatives while retaining schema-valid application values.

    Returns:
        None: Random constrained sampling cannot reproduce indentation-tab noise.
    """
    schema = {
        "type": "object",
        "properties": {"config": {"type": "string", "enum": ["\t", "ready"]}},
        "required": ["config"],
        "additionalProperties": False,
    }

    @settings(max_examples=20, deadline=None, derandomize=True)
    @given(schema_strategy(schema))
    def check(value: object) -> None:
        """
        Check the generated configuration against its permitted useful alternative.

        Args:
            value (object): Fresh schema-constrained candidate.

        Returns:
            None: Tabs never reach the chart renderer through this strategy.
        """
        assert value == {"config": "ready"}

    check()


def test_known_inputs_preserve_dynamic_maps(tmp_path: Path) -> None:
    """
    Keep schema/default/reference fields and open dynamic maps without editing the contract.

    Args:
        tmp_path (Path): Template directory.

    Returns:
        None: Generation preferences retain known and uncertain paths distinctly.
    """
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "resource.yaml").write_text(
        dedent("""
        {{ index .Values.labels .Values.selector }}
        {{ range .Values.settings }}{{ . }}{{ end }}
        {{ .Values.undocumented }}
        {{ tpl .Values.extra . }}
    """)
    )
    schema: dict[str, object] = {"type": "object", "properties": {"enabled": {"type": "boolean"}}}
    defaults: dict[str, object] = {
        "enabled": False,
        "labels": {"app": "sample"},
        "settings": {"first": "x"},
        "selector": "app",
        "extra": "",
    }
    (tmp_path / "values.yaml").write_text(json.dumps(defaults))
    chart = Chart(tmp_path, copy.deepcopy(schema), copy.deepcopy(defaults))
    priority = PriorityInputs.build(chart)
    assert chart.schema == schema and chart.defaults == defaults
    assert priority.schema["additionalProperties"] is False
    properties = mapping(priority.schema["properties"])
    assert {
        "enabled",
        "selector",
        "labels",
        "settings",
        "undocumented",
        "extra",
    } <= properties.keys()
    assert mapping(properties["labels"]).get("additionalProperties") is not False
    assert mapping(properties["settings"]).get("additionalProperties") is not False
    assert ["labels"] in priority.dynamic_objects
    assert ["settings"] in priority.dynamic_objects
    assert priority.diagnostics
    assert validators.validator_for(schema)(schema).is_valid({"previously_unknown": 1})
    example = find(
        priority.strategy(chart),
        lambda values: True,
        settings=settings(max_examples=20, deadline=None),
    )
    assert set(example) <= properties.keys()
    deferred = find(
        priority.deferred_strategy(chart),
        lambda values: "enabled" not in values,
        settings=settings(max_examples=50, deadline=None),
    )
    assert validators.validator_for(schema)(schema).is_valid(json_value(deferred))
    from hypothesis_helm.charts.runner import merge_values

    assert not validators.validator_for(priority.schema)(priority.schema).is_valid(json_value(merge_values(chart.defaults, deferred)))


def test_pattern_maps_and_compositions_remain_open(tmp_path: Path) -> None:
    """
    Avoid closing schema-defined maps or changing composed object semantics.

    Args:
        tmp_path (Path): Empty template source.

    Returns:
        None: Complex and dynamic object declarations retain their generation domain.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "labels": {"type": "object", "patternProperties": {"^x": {"type": "string"}}},
            "ports": {"type": "object", "additionalProperties": {"type": "integer"}},
            "choice": {"type": "object", "anyOf": [{"required": ["a"]}, {"required": ["b"]}]},
        },
    }
    priority = PriorityInputs.build(Chart(tmp_path, schema, {}))
    properties = mapping(priority.schema["properties"])
    for name in ("labels", "ports", "choice"):
        assert mapping(properties[name]).get("additionalProperties") is not False


@pytest.mark.parametrize("fail_fast", [False, True])
def test_phase_order_and_failure_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_fast: bool) -> None:
    """
    Run robustness after failures unless fail-fast explicitly stops the phase.

    Args:
        tmp_path (Path): Chart and artifacts location.
        monkeypatch (pytest.MonkeyPatch): Capture runner arguments without spawning Helm.
        fail_fast (bool): Stop after the first failing phase.

    Returns:
        None: Both phases use the original chart and retain distinct reports.
    """
    chart = Chart(tmp_path, {"type": "object", "properties": {"flag": {"type": "boolean"}}}, {"flag": False})
    calls: list[dict[str, object]] = []

    def check(source: Chart, **kwargs: object) -> dict[str, object]:
        """
        Simulate independent phase outcomes.

        Args:
            source (Chart): Authoritative chart passed to each phase.
            **kwargs (object): Generation and budget configuration.

        Returns:
            dict[str, object]: Recorded failure or successful robustness sample.
        """
        assert source is chart
        calls.append(kwargs)
        return {
            "status": "failed" if len(calls) == 1 else "passed",
            "attempts": 3,
            "error": "known-input failure" if len(calls) == 1 else "",
        }

    monkeypatch.setattr("hypothesis_helm.charts.prioritized.check_chart", check)
    result = check_prioritized(
        chart,
        budget=2,
        max_examples=10,
        seed=0,
        helm="helm",
        timeout=1,
        artifacts=tmp_path / "reports",
        fail_fast=fail_fast,
    )
    if fail_fast:
        assert len(calls) == 1
        assert calls[0]["fail_fast"] is True
        assert result["status"] == "failed" and result["attempts"] == 3
        deferred = json.loads((tmp_path / "reports/robustness/report.json").read_text())
        assert deferred["status"] == "not-started"
        assert deferred["attempts"] == 0
        return
    assert len(calls) == 2
    assert calls[0]["input_strategy"] is not None
    assert calls[1]["input_strategy"] is not None
    assert calls[1]["input_strategy"] is not calls[0]["input_strategy"]
    assert float(str(calls[0]["time_limit"])) <= 1.8
    assert float(str(calls[1]["time_limit"])) <= 2
    assert result["status"] == "failed" and result["attempts"] == 6
    assert result["coverage_complete"] is False
    assert (tmp_path / "reports/known-inputs/report.json").exists()
    assert (tmp_path / "reports/robustness/report.json").exists()


@pytest.mark.integration
@pytest.mark.parametrize("key", ["\U00010000", "é" * 180])
@pytest.mark.parametrize("value", ["\U00010000", "\t", "\x7f", "\x85", "\x9f", "\u2028", "\u2029", "é", "\u0000"])
def test_unicode_values_reach_helm(tmp_path: Path, key: str, value: str) -> None:
    """
    Send supplementary Unicode as UTF-8 instead of YAML-incompatible surrogate escapes.

    Args:
        tmp_path (Path): Minimal chart with permissive values.
        key (str): Unicode key whose escaped representation can exceed YAML's key limit.
        value (str): Unicode scalar or control character requiring lossless transport.

    Returns:
        None: Helm accepts the legal Unicode key and renders the chart.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm required")
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: unicode
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
          name: unicode
        data:
          value: {{ .Values.input | quote }}
    """)
    )
    result = render(Chart(tmp_path, {"type": "object"}, {}), {key: None, "input": value}, helm=helm)
    assert result[0]["kind"] == "ConfigMap"
    assert mapping(result[0]["data"])["value"] == value
