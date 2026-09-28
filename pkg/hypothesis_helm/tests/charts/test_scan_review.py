"""
Exercise failure retention and coordinator accounting exposed by real chart scans.
"""

import json
import logging
import shutil
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from hypothesis import strategies as st

from hypothesis_helm.charts.inspection.audit import audit_findings
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.suites.runtime import _replace
from hypothesis_helm.charts.testing.paths import check_paths
from hypothesis_helm.charts.testing.rendering import render
from hypothesis_helm.charts.testing.runner import check_chart
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.exceptions.execution import TimeLimitReached
from hypothesis_helm.exceptions.rendering import RenderFailure
from hypothesis_helm.execution.workers.path_queue import execute
from hypothesis_helm.reporting.console.logs import WorkerLogFormatter, WorkerLogs, diagnostic_line
from hypothesis_helm.reporting.evidence.checkpoints import save
from hypothesis_helm.schemas.contracts import mapping, sequence


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Supply a small chart with three independently testable Boolean paths.

    Args:
        tmp_path (Path): Isolated chart directory.

    Returns:
        Chart: In-memory schema and matching chart metadata.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: review
        version: 1.0.0
        """)
    )
    return Chart(
        tmp_path,
        {"type": "object", "properties": {name: {"type": "boolean"} for name in ("a", "b", "c")}},
        {"a": False, "b": False, "c": False},
    )


def test_shrink_timeout_retains_observed_failure(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve a native failure when a later shrink render reaches the chart deadline.

    Args:
        chart (Chart): Small property source.
        tmp_path (Path): Checkpoint and final report destination.
        monkeypatch (pytest.MonkeyPatch): Replace Helm with a failure followed by cancellation.

    Returns:
        None: Failure identity, input and incomplete minimization survive the stop.
    """
    artifacts = tmp_path / "results"
    calls = 0

    def render(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Fail once, then verify durable evidence exists before simulating a deadline.

        Args:
            *args (object): Chart and generated values.
            **kwargs (object): Renderer options.

        Returns:
            list[dict[str, object]]: No successful output is produced.
        """
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RenderFailure("reproduced invalid YAML", "HH1101")
        checkpoint = json.loads((artifacts / "observed-failure.json").read_text())
        assert checkpoint["values"] == {"a": True}
        assert checkpoint["code"] == "HH1101"
        raise TimeLimitReached()

    monkeypatch.setattr("hypothesis_helm.charts.testing.runner.render", render)
    result = check_chart(chart, check_defaults=False, input_strategy=st.just({"a": True}), artifact_dir=artifacts)
    assert result["status"] == "failed"
    assert result["stop_reason"] == "time-limit"
    assert result["minimization_complete"] is False
    assert result["coverage_complete"] is False
    assert result["code"] == "HH1101"
    assert result["values"] == {"a": True}
    assert "reproduced invalid YAML" in str(result["error"])
    assert json.loads((artifacts / "values.json").read_text()) == result["values"]
    assert json.loads((artifacts / "report.json").read_text()) == result


@pytest.mark.parametrize("blocking", [True, False])
def test_worker_recovery_retains_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocking: bool) -> None:
    """
    Recover a claimed property's saved failure when its worker cannot write a final result.

    Args:
        tmp_path (Path): Queue and worker evidence.
        monkeypatch (pytest.MonkeyPatch): Simulate an exited worker with no final queue record.
        blocking (bool): Whether saved evidence meets the active severity threshold.

    Returns:
        None: The coordinator retains the observed failure and marks execution incomplete.
    """
    queue = tmp_path / "queue"
    artifacts = tmp_path / "failure"

    def run(*args: object, **kwargs: object) -> SimpleNamespace:
        """
        Publish a claim and counterexample, then exit without finalizing the task.

        Args:
            *args (object): Worker command.
            **kwargs (object): Process execution options.

        Returns:
            SimpleNamespace: Completed process status without a queue result.
        """
        save(queue / "started-00000000.json", {"path": ["a"], "artifacts": str(artifacts), "worker_pid": 42})
        save(
            artifacts / "observed-failure.json",
            {"status": "failed" if blocking else "findings", "values": {"a": True}, "code": "HH1101", "blocking": blocking},
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "hypothesis_helm.execution.workers.path_queue.Processes", lambda **kwargs: SimpleNamespace(run=run, stop=lambda: None)
    )
    results = execute({"paths": [{"path": ["a"]}], "deadline": float("inf")}, queue, 1)
    assert len(results) == 1
    assert results[0]["status"] == ("failed" if blocking else "error")
    assert results[0]["stop_reason"] == "error"
    assert results[0]["values"] == {"a": True}
    assert results[0]["path"] == ["a"]


def test_parallel_counters_sum_property_deltas(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Include every property's counter delta and keep failed-but-unfinished paths incomplete.

    Args:
        chart (Chart): Chart with enough paths to reuse a worker.
        tmp_path (Path): Result destination.
        monkeypatch (pytest.MonkeyPatch): Supply deterministic worker snapshots.

    Returns:
        None: Repeated worker IDs do not discard earlier counts or mask policy settings.
    """
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", Mock(return_value=[{}]))

    def workers(context: dict[str, object], directory: Path, count: int) -> list[dict[str, object]]:
        """
        Return two properties from one worker and an interrupted failure from another.

        Args:
            context (dict[str, object]): Chart queue settings and discovered paths.
            directory (Path): Queue artifact destination.
            count (int): Requested worker count.

        Returns:
            list[dict[str, object]]: Per-property deltas with cumulative diagnostic snapshots.
        """
        return [
            {
                "kind": "value-path",
                "phase": str(index),
                "path": mapping(item)["path"],
                "worker_pid": 1 if index < 2 else 2,
                "status": "passed" if index < 2 else "failed",
                **({"stop_reason": "time-limit", "error": "observed failure"} if index == 2 else {}),
                "configuration_rejections": {
                    "incomplete_evaluations": index + 1,
                    "rejected_candidates": index + 1,
                    "schema_conflicts": 1,
                    "verify_every_candidate": True,
                    "analysis_fallbacks": [{"reason": "unsupported"}],
                },
            }
            for index, item in enumerate(sequence(context["paths"])[:3])
        ]

    monkeypatch.setattr("hypothesis_helm.execution.workers.path_queue.execute", workers)
    result = check_paths(
        chart, budget=30, max_examples=10, seed=0, helm="helm", timeout=5, artifacts=tmp_path / "results", jobs=2, filtering=True
    )
    evidence = mapping(result["configuration_rejections"])
    assert evidence["incomplete_evaluations"] == evidence["rejected_candidates"] == 6
    assert evidence["schema_conflicts"] == 3
    assert evidence["verify_every_candidate"] is True
    assert evidence["analysis_fallbacks"] == [{"reason": "unsupported"}]
    assert mapping(result["traversal"])["completed_paths"] == 2
    assert mapping(result["traversal"])["incomplete_paths"] == 1
    assert result["status"] == "failed"


def test_compiler_diagnostics_deduplicate_across_workers(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """
    Relay a compiler warning once per chart while leaving separate findings visible.

    Args:
        tmp_path (Path): Worker log directory.
        caplog (pytest.LogCaptureFixture): Coordinator logging capture.

    Returns:
        None: Duplicate analysis warnings disappear only from the shared terminal stream.
    """
    formatter = WorkerLogFormatter()
    record = logging.LogRecord("hypothesis_helm.compiler", logging.WARNING, "", 0, "analysis incomplete", (), None)
    record.diagnostic_key = "chart:template:1:unknown"
    for slot in range(2):
        (tmp_path / f"worker-{slot}.log").write_text(formatter.format(record) + "\n")
    with caplog.at_level(logging.WARNING):
        logs = WorkerLogs(tmp_path, 2)
        logs.drain()
        logs.drain()
    assert [entry.message for entry in caplog.records] == ["analysis incomplete"]


def test_multiline_rejection_log_includes_reason() -> None:
    """
    Include chart-authored validation text after Helm's otherwise empty error header.

    Returns:
        None: The live diagnostic identifies the missing required configuration.
    """
    message = "Error: execution error at (apache/templates/NOTES.txt:45:4):\n\nVALUES VALIDATION:\nmissing git repository"
    assert "missing git repository" in diagnostic_line(message)


def test_dynamic_references_are_not_missing_concrete_fields(chart: Chart) -> None:
    """
    Retain wildcard references without inventing undocumented concrete input paths.

    Args:
        chart (Chart): Source with nested dynamic map traversal.

    Returns:
        None: Audit evidence separates dynamic access from named-field findings.
    """
    (chart.path / "templates").mkdir()
    (chart.path / "templates/NOTES.txt").write_text("{{ range .Values }}{{ range . }}{{ .flag }}{{ end }}{{ end }}")
    audit = audit_findings(chart)
    assert audit["dynamic_references"]
    assert not any("*" in sequence(mapping(finding)["path"]) for finding in sequence(audit["findings"]))


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
@pytest.mark.parametrize(
    ("path", "replacement", "overrides"),
    [
        (("base", "enabled"), True, {"base": {"enabled": True}}),
        (("merged", "enabled"), True, {"merged": {"enabled": True}}),
        (("items", 0, "enabled"), True, {"items": [{"enabled": True, "count": 2}]}),
    ],
)
def test_yaml_anchor_overrides_match_helm(
    chart: Chart, path: tuple[str | int, ...], replacement: object, overrides: dict[str, object]
) -> None:
    """
    Mutate only the selected alias occurrence, matching Helm's loaded-value semantics.

    Args:
        chart (Chart): Source chart receiving anchored defaults and a values-observing manifest.
        path (tuple[str | int, ...]): Concrete map or array path to change.
        replacement (object): Generated value for that path.
        overrides (dict[str, object]): Equivalent native Helm override.

    Returns:
        None: Aliases, merge precedence and unaffected siblings agree with native rendering.
    """
    source = dedent("""
        base: &base
          enabled: false
          count: 2
        alias: *base
        merged:
          <<: *base
          count: 3
        items: &items
          - *base
        otherItems: *items
        """)
    (chart.path / "values.yaml").write_text(source)
    (chart.path / "templates").mkdir()
    (chart.path / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: anchored
        data:
          values: {{ .Values | toJson | quote }}
        """)
    )
    defaults = mapping(yamlio.load(source))
    before = yamlio.dump(defaults)
    generated = _replace(defaults, path, replacement)
    native_output = render(chart, overrides)
    expected = json.loads(str(mapping(native_output[0]["data"])["values"]))
    assert generated == expected
    assert yamlio.dump(defaults) == before
    assert mapping(generated["alias"])["enabled"] is False
    assert mapping(generated["merged"])["count"] == 3
