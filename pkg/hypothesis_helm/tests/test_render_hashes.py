"""
Verify output identity and successful-validation reuse independently of input coverage.
"""

import json
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, check_chart, render
from hypothesis_helm.execution.render_hashes import (
    ALGORITHM,
    RenderHashes,
    render_digest,
    summarize_process_statistics,
)
from hypothesis_helm.reporting.output import MANIFEST_FD


def test_bare_equals_preserves_string_identity() -> None:
    """
    Read equals signs as strings without changing unrelated tags or other YAML readers.

    Returns:
        None: Keys, nested values, streaming, and hashing receive JSON-compatible strings.
    """
    source = dedent("""
    =: =
    nested:
      - value: =
    """)
    expected = {"=": "=", "nested": [{"value": "="}]}
    assert yamlio.load(source) == expected
    assert yamlio.load_all(source) == [expected]
    assert render_digest(yamlio.load_all(source)) == render_digest([expected])
    assert json.loads(yamlio.json_for_helm(yamlio.load(source))) == expected
    assert isinstance(YAML(typ="rt").load("value: =")["value"], TaggedScalar)
    tagged = yamlio.load_all("value: !custom keep")[0]
    assert isinstance(tagged, dict) and isinstance(tagged["value"], TaggedScalar)


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("helm"), reason="Helm is required")
def test_equals_renders_hashes_and_streams(tmp_path: Path) -> None:
    """
    Accept bare and quoted equals signs with identical rendered identities under real Helm.

    Args:
        tmp_path (Path): Chart and manifest stream destination.

    Returns:
        None: Native Helm conversion agrees with the values accepted and hashed by the runner.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: equals
        version: 0.1.0
        """)
    )
    (tmp_path / "values.yaml").write_text("literal: '='\n")
    template = tmp_path / "templates/configmap.yaml"
    template.write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: equals
        data:
          literal: {{ .Values.literal }}
          =: {{ .Values.literal }}
          native: '{{ fromYaml "value: =" | toJson }}'
        """)
    )
    hashes = RenderHashes()
    chart = Chart(tmp_path, {"type": "object"}, {"literal": "="})
    stream_path = tmp_path / "manifests.jsonl"
    with stream_path.open("w") as stream:
        token = MANIFEST_FD.set(stream.fileno())
        try:
            first = render(chart, {"literal": "="}, hashes=hashes)
            template.write_text(template.read_text().replace("{{ .Values.literal }}", '"="'))
            second = render(chart, {"literal": "="}, hashes=hashes)
        finally:
            MANIFEST_FD.reset(token)
    assert first == second
    assert first[0]["data"] == {"literal": "=", "=": "=", "native": '{"value":"="}'}
    assert hashes.snapshot()["validation_cache_hits"] == 1
    assert len(stream_path.read_text().splitlines()) == 2
    assert json.loads(stream_path.read_text().splitlines()[0]) == first[0]


def test_digest_preserves_meaningful_order() -> None:
    """
    Ignore map ordering while preserving complete content and sequence ordering.

    Returns:
        None: Canonical identities distinguish semantically different bundles.
    """
    assert render_digest([{"a": 1, "b": 2}]) == render_digest([{"b": 2, "a": 1}])
    assert render_digest([{"a": [1, 2]}]) != render_digest([{"a": [2, 1]}])
    assert render_digest([{"a": 1}, {"b": 2}]) != render_digest([{"b": 2}, {"a": 1}])
    assert render_digest([{"a": 1}]) != render_digest([{"a": True}])


def test_cache_only_commits_success_in_same_context() -> None:
    """
    Retry failures and revalidate when validation settings change.

    Returns:
        None: Only successful matching validation is reused.
    """
    hashes = RenderHashes()
    validate = Mock(side_effect=[AssertionError("invalid"), None, None])
    with pytest.raises(AssertionError, match="invalid"):
        hashes.check([{"a": 1}], "schema-a", validate)
    hashes.check([{"a": 1}], "schema-a", validate)
    hashes.check([{"a": 1}], "schema-a", validate)
    hashes.check([{"a": 1}], "schema-b", validate)
    assert validate.call_count == 3
    assert hashes.snapshot()["validation_cache_hits"] == 1
    assert hashes.snapshot()["duplicate_bundles"] == 3


def test_render_reuse_preserves_properties_and_stream(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Exercise distinct inputs with identical renders without suppressing custom assertions.

    Args:
        monkeypatch (pytest.MonkeyPatch): Isolate Helm and validators.
        tmp_path (Path): Isolated chart location.

    Returns:
        None: Reuse saves standard validation while every input still runs its properties.
    """
    output = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: unchanged\n"
    helm = Mock(return_value=subprocess.CompletedProcess([], 0, output, ""))
    validator = Mock()
    stream = Mock()
    prop = Mock(side_effect=[None, AssertionError("custom failure")])
    monkeypatch.setattr("hypothesis_helm.charts.runner.subprocess.run", helm)
    monkeypatch.setattr("hypothesis_helm.charts.runner.validate", validator)
    monkeypatch.setattr("hypothesis_helm.charts.runner.emit_manifest", stream)
    chart = Chart(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["enabled"],
            "properties": {"enabled": {"type": "boolean"}},
        },
        {"enabled": False},
    )
    report = check_chart(chart, permutations=2, infer_exhaustive_groups=False, properties=(prop,))
    assert report["status"] == "failed"
    assert helm.call_count == stream.call_count == prop.call_count == 2
    assert validator.call_count == 1
    assert report["render_hashes"] == {
        "algorithm": ALGORITHM,
        "scope": "run-local",
        "observed_bundles": 2,
        "unique_bundles": 1,
        "duplicate_bundles": 1,
        "validation_cache_hits": 1,
        "validated_entries": 1,
    }
    assert check_chart(chart, permutations=2, infer_exhaustive_groups=False)["status"] == "passed"
    assert validator.call_count == 2


def test_worker_statistics_do_not_claim_global_uniqueness(tmp_path: Path) -> None:
    """
    Aggregate counters without interpreting separate worker sets as one shared set.

    Args:
        tmp_path (Path): Worker counter directory.

    Returns:
        None: Reports identify worker-local uniqueness and never contain hashes.
    """
    hashes = RenderHashes()
    hashes.check([{}], "context", Mock())
    for worker in (1, 2):
        (tmp_path / f"{worker}.json").write_text(json.dumps(hashes.snapshot()))
    stats = summarize_process_statistics(tmp_path)
    assert stats["worker_unique_bundles"] == 2
    assert stats["global_unique_bundles"] is None
    assert stats["workers_reporting"] == 2
    assert "seen" not in stats and "validated" not in stats
