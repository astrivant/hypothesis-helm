"""
Check equality certificates against Helm and adversarial proof-boundary cases.
"""

import copy
import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from hypothesis_helm import Chart, check_chart
from hypothesis_helm.charts.runner import render
from hypothesis_helm.cli import main
from hypothesis_helm.compiler.asts.templates import fold, lex, lower, specialize
from hypothesis_helm.compiler.passes.pruning import DistanceBounds, Pruner
from hypothesis_helm.schemas.contracts import mapping, number, sequence
from hypothesis_helm.schemas.model import ValuesModel


@pytest.fixture
def proof_chart(tmp_path: Path) -> Chart:
    """
    Create a finite chart with live scalars, an unused field and a Boolean branch.

    Args:
        tmp_path (Path): Isolated source location.

    Returns:
        Chart: Eight inputs with three distinct output classes.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: proof\nversion: 0.1.0\n")
    (tmp_path / "values.yaml").write_text("enabled: false\ncount: 1\nunused: false\n")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["enabled", "count", "unused"],
        "properties": {
            "enabled": {"type": "boolean"},
            "count": {"type": "integer", "minimum": 1, "maximum": 2},
            "unused": {"type": "boolean"},
        },
    }
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "templates" / "config.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ .Release.Name }}\n"
        "data:\n{{ if .Values.enabled }}  count: '{{ .Values.count }}'\n"
        "{{ else }}  state: disabled\n{{ end }}"
    )
    return Chart.load(tmp_path)


def test_bounds_use_strict_comparisons() -> None:
    """
    Keep equality at the threshold ambiguous and reject malformed bounds.

    Returns:
        None: Only a strict proved upper bound authorizes discarding.
    """
    assert DistanceBounds(0, 0).decision() == "discard"
    assert DistanceBounds(1, 1).decision() == "render-novel"
    assert DistanceBounds().decision() == "render-ambiguous"
    assert DistanceBounds(0, 0.5).decision() == "render-ambiguous"
    assert DistanceBounds(0.5, 1).decision() == "render-ambiguous"
    for bounds in (DistanceBounds(1, 0), DistanceBounds(float("nan"), 1)):
        with pytest.raises(ValueError):
            bounds.decision()


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_pruning_matches_full_helm_output_and_replays_assertions(proof_chart: Chart) -> None:
    """
    Differentially compare every pruned output with a complete real Helm enumeration.

    Args:
        proof_chart (Chart): Finite chart spanning multiple control-flow regions.

    Returns:
        None: All eight candidates retain identical outputs while only three invoke Helm.
    """
    full = Mock()
    reduced = Mock()
    baseline = check_chart(proof_chart, permutations=2, properties=(full,))
    report = check_chart(proof_chart, permutations=2, prune_equivalent=True, properties=(reduced,))
    assert baseline["status"] == report["status"] == "passed"
    assert full.call_count == reduced.call_count == 8
    assert full.call_args_list == reduced.call_args_list
    pruning = mapping(report["pruning"])
    assert pruning["rendered_candidates"] == 3
    assert pruning["pruned_candidates"] == 5
    assert report["remaining_iterations"] == 0
    assert report["completed_iterations"] == 8
    assert mapping(report["render_hashes"])["observed_bundles"] == 3
    for item in sequence(pruning["certificates"]):
        certificate = mapping(item)
        assert certificate["upper_bound"] == 0
        assert number(certificate["representative_iteration"]) < number(certificate["candidate_iteration"])


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_reachable_opaque_failure_is_never_pruned(proof_chart: Chart) -> None:
    """
    Render an opaque fail call when its branch becomes reachable.

    Args:
        proof_chart (Chart): Finite chart with both Boolean guard outcomes.

    Returns:
        None: Prior inactive successes cannot suppress the later Helm failure.
    """
    source = proof_chart.path / "templates" / "config.yaml"
    source.write_text(source.read_text() + '{{ if .Values.enabled }}{{ fail "must fail" }}{{ end }}')
    report = check_chart(proof_chart, permutations=2, prune_equivalent=True)
    assert report["status"] == "failed"
    assert "must fail" in str(report["error"])
    assert mapping(report["pruning"])["rendered_candidates"] == 2


def test_opaque_expressions_and_inactive_regions(proof_chart: Chart) -> None:
    """
    Retain unknowns while allowing literal and candidate-proved dead branch elimination.

    Args:
        proof_chart (Chart): Source of declared model field identities.

    Returns:
        None: Unsupported executed code never produces an equality witness.
    """
    model = ValuesModel.from_schema(proof_chart.schema)
    for expression in (
        "randAlphaNum 8",
        'lookup "v1" "Secret" "" ""',
        "tpl .Values.unused .",
        ".Values.count | quote",
        'include "helper" .',
        'set .Values "count" 2',
    ):
        nodes = fold(lower("{{ " + expression + " }}"))
        assert specialize(nodes, proof_chart.defaults, model).reason is not None
        nodes = fold(lower("{{ if false }}{{ " + expression + " }}{{ end }}stable"))
        assert specialize(nodes, proof_chart.defaults, model).reason is None
    nodes = fold(lower("{{ if .Values.enabled }}{{ randAlphaNum 8 }}{{ end }}stable"))
    assert specialize(nodes, proof_chart.defaults, model).reason is None
    assert specialize(nodes, dict(proof_chart.defaults, enabled=True), model).reason is not None


def test_no_success_no_certificate_and_mutations_invalidate(proof_chart: Chart) -> None:
    """
    Reject pending results, changed contexts and source changes before proof reuse.

    Args:
        proof_chart (Chart): Stable finite source chart.

    Returns:
        None: Equivalence lookup requires an earlier committed success in the same context.
    """
    model = ValuesModel.from_schema(proof_chart.schema)
    pruner = Pruner(proof_chart.path, proof_chart.defaults, model)
    witness = pruner.candidate({}, proof_chart.defaults, "context-a")
    assert witness is not None
    assert pruner.lookup(witness, 1) is None
    assert pruner.lookup(witness, 2) is None
    pruner.remember(witness, 2, [])
    assert pruner.lookup(witness, 3) == []
    other = pruner.candidate({}, proof_chart.defaults, "context-b")
    assert pruner.lookup(other, 4) is None
    source = proof_chart.path / "templates" / "new.yaml"
    source.write_text("new output")
    assert pruner.candidate({}, proof_chart.defaults, "context-a") is None


def test_schema_and_coalescing_boundaries(proof_chart: Chart) -> None:
    """
    Treat validator dialect differences, null deletion and type changes as unknown.

    Args:
        proof_chart (Chart): Source with a schema accepted by the restricted validator contract.

    Returns:
        None: No risky merge or format constraint can authorize skipping Helm.
    """
    pruner = Pruner(proof_chart.path, proof_chart.defaults, ValuesModel.from_schema(proof_chart.schema))
    assert pruner.candidate({"unused": None}, proof_chart.defaults, "context") is None
    assert pruner.candidate({"unused": {}}, proof_chart.defaults, "context") is None
    schema = copy.deepcopy(proof_chart.schema)
    mapping(mapping(schema["properties"])["unused"])["format"] = "email"
    (proof_chart.path / "values.schema.json").write_text(json.dumps(schema))
    pruner = Pruner(proof_chart.path, proof_chart.defaults, ValuesModel.from_schema(schema))
    assert pruner.disabled is not None
    assert pruner.candidate({}, proof_chart.defaults, "context") is None


def test_lexer_preserves_go_trim_and_quoted_delimiters() -> None:
    """
    Keep source text, trim only valid markers and avoid tokenizing quoted delimiters.

    Returns:
        None: Trims, negative literals and comments remain lexically distinct.
    """
    tokens = lex("left \n{{- true -}}\n right")
    assert [token.text for token in tokens] == ["left", "true", "right"]
    assert [token.text for token in lex("x {{-3}} y")] == ["x ", "-3", " y"]
    assert [token.text for token in lex('{{ printf "}}" }}')] == ["", 'printf "}}"', ""]
    assert [token.text for token in lex("a{{/* }} {{ */}}b")] == ["a", "b"]
    for source in ("{{ if true }}", "{{ end }}", '{{ "unfinished }}'):
        with pytest.raises(ValueError):
            lower(source)


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_custom_failure_on_equivalent_candidate_still_fails(proof_chart: Chart) -> None:
    """
    Preserve stateful custom assertions and their failures after skipping equivalent rendering.

    Args:
        proof_chart (Chart): Chart whose second candidate is equivalent to its baseline.

    Returns:
        None: Callback failure is recorded despite a valid manifest-equivalence certificate.
    """
    prop = Mock(side_effect=[None, AssertionError("custom failure")])
    report = check_chart(proof_chart, permutations=2, prune_equivalent=True, properties=(prop,))
    assert report["status"] == "failed"
    assert "custom failure" in str(report["error"])
    assert prop.call_count == 2
    assert mapping(report["pruning"])["pruned_candidates"] == 1


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_differential_scalar_output_and_trim_proofs(proof_chart: Chart) -> None:
    """
    Compare accepted symbolic equality against Helm across guarded scalar substitutions.

    Args:
        proof_chart (Chart): Chart with pure expressions.

    Returns:
        None: Every generated equality witness implies identical actual manifest resources.
    """
    model = ValuesModel.from_schema(proof_chart.schema)
    pruner = Pruner(proof_chart.path, proof_chart.defaults, model)
    outputs: dict[str, list[dict[str, object]]] = {}
    for enabled in (False, True):
        for count in (1, 2):
            for unused in (False, True):
                values: dict[str, object] = {"enabled": enabled, "count": count, "unused": unused}
                witness = pruner.candidate(values, values, "fixed")
                assert witness is not None
                actual = render(proof_chart, values)
                if witness.key in outputs:
                    assert actual == outputs[witness.key]
                outputs[witness.key] = actual


def test_yaml_and_numeric_schema_ambiguity_falls_back(proof_chart: Chart) -> None:
    """
    Reject YAML octal defaults and floating-point schema constraints before any pruning.

    Args:
        proof_chart (Chart): Chart to modify with cross-parser edge cases.

    Returns:
        None: Different YAML resolution and numeric validation cannot produce certificates.
    """
    values = proof_chart.path / "values.yaml"
    original = values.read_text()
    values.write_text(original.replace("count: 1", "count: 0123"))
    chart = Chart.load(proof_chart.path)
    pruner = Pruner(chart.path, chart.defaults, ValuesModel.from_schema(chart.schema))
    assert pruner.disabled is not None
    values.write_text("%YAML 1.2\n---\n" + original)
    pruner = Pruner(proof_chart.path, proof_chart.defaults, ValuesModel.from_schema(proof_chart.schema))
    assert pruner.disabled is not None
    values.write_text(original)
    schema = copy.deepcopy(proof_chart.schema)
    mapping(mapping(schema["properties"])["count"])["maximum"] = 1.9999999999999999
    (proof_chart.path / "values.schema.json").write_text(json.dumps(schema))
    pruner = Pruner(proof_chart.path, proof_chart.defaults, ValuesModel.from_schema(schema))
    assert pruner.disabled is not None


def test_parse_global_definitions_and_invalid_candidates_do_not_prune(proof_chart: Chart) -> None:
    """
    Refuse hidden template definitions and independently validate the compiled schema.

    Args:
        proof_chart (Chart): Chart with schema constraints and frozen defaults.

    Returns:
        None: Dead-code elimination cannot discard global definitions or validation failures.
    """
    model = ValuesModel.from_schema(proof_chart.schema)
    pruner = Pruner(proof_chart.path, proof_chart.defaults, model)
    invalid: dict[str, object] = dict(proof_chart.defaults, count=3)
    assert pruner.candidate(invalid, invalid, "context") is None
    mismatched: dict[str, object] = dict(proof_chart.defaults, count=2)
    assert pruner.candidate({}, mismatched, "context") is None
    source = proof_chart.path / "templates" / "config.yaml"
    source.write_text('{{ if false }}{{ define "hidden" }}bad{{ end }}{{ end }}')
    pruner = Pruner(proof_chart.path, proof_chart.defaults, model)
    assert pruner.disabled is not None
    assert "parse-global" in pruner.disabled


def test_pruning_dry_run_does_not_render_or_create_artifacts(
    proof_chart: Chart,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """
    Expose the compiler contract during CLI planning without claiming runtime certificates.

    Args:
        proof_chart (Chart): Finite source chart.
        monkeypatch (pytest.MonkeyPatch): Prevent renderer execution.
        capsys (pytest.CaptureFixture[str]): Capture the structured CLI report.
        tmp_path (Path): Prospective artifact location.

    Returns:
        None: Dry runs contain zero runtime certificates and write no artifacts.
    """
    renderer = Mock(side_effect=AssertionError("unexpected render"))
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", renderer)
    target = tmp_path / "reports"
    assert (
        main(
            [
                "test",
                str(proof_chart.path),
                "--prune-equivalent",
                "--dry-run",
                "--artifact-dir",
                str(target),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "dry-run"
    assert report["pruning"]["pruned_candidates"] == 0
    assert report["pruning"]["certificates"] == []
    assert not target.exists()
    renderer.assert_not_called()


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
@pytest.mark.parametrize(
    "body",
    [
        'data:\n  state: "{{ if .Values.enabled }}on{{ else }}off{{ end }}"\n',
        'data:\n  state: "A \n{{- if .Values.enabled -}} on {{- else -}} off {{- end -}} B"\n',
        ('data:\n  state: "{{ if .Values.enabled }}{{ if .Values.unused }}a{{ else }}b{{ end }}{{ else }}c{{ end }}"\n'),
        'data:\n  state: "{{/* }} {{ */}}constant"\n',
    ],
)
def test_supported_control_ir_matches_helm(proof_chart: Chart, body: str) -> None:
    """
    Differentially exercise trimming, nested partitions and quoted-delimiter comments.

    Args:
        proof_chart (Chart): Finite chart source.
        body (str): Pure Go-template body under test.

    Returns:
        None: Every candidate emits the same manifests with and without pruning.
    """
    (proof_chart.path / "templates" / "config.yaml").write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: proof\n" + body)
    baseline = Mock()
    reduced = Mock()
    assert check_chart(proof_chart, permutations=2, properties=(baseline,))["status"] == "passed"
    report = check_chart(proof_chart, permutations=2, prune_equivalent=True, properties=(reduced,))
    assert report["status"] == "passed"
    assert baseline.call_args_list == reduced.call_args_list
    assert number(mapping(report["pruning"])["pruned_candidates"]) > 0


@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_callback_mutation_cannot_contaminate_representatives(proof_chart: Chart) -> None:
    """
    Replay pristine resource copies even when each callback mutates its input.

    Args:
        proof_chart (Chart): Finite source with equivalent candidates.

    Returns:
        None: Later callbacks never see mutations made by an earlier candidate.
    """

    def mutate(resources: list[dict[str, object]]) -> None:
        """
        Assert pristine input and deliberately modify it.

        Args:
            resources (list[dict[str, object]]): Candidate manifests.

        Returns:
            None: The callback's private manifests are modified.
        """
        assert "callback" not in resources[0]
        resources[0]["callback"] = True

    report = check_chart(proof_chart, permutations=2, prune_equivalent=True, properties=(mutate,))
    assert report["status"] == "passed"
    assert mapping(report["pruning"])["pruned_candidates"] == 5


def test_case_insensitive_ignore_files_cannot_hide_values(proof_chart: Chart) -> None:
    """
    Reject ignore-file casing that could change Helm defaults on case-insensitive hosts.

    Args:
        proof_chart (Chart): Finite source chart.

    Returns:
        None: A differently cased ignore file disables all proof reuse.
    """
    (proof_chart.path / ".HELMIGNORE").write_text("values.yaml\nvalues.schema.json\n")
    pruner = Pruner(proof_chart.path, proof_chart.defaults, ValuesModel.from_schema(proof_chart.schema))
    assert pruner.disabled is not None
    assert ".helmignore" in pruner.disabled


@pytest.mark.parametrize("enabled", [False, True])
def test_progressive_forecast_is_read_only(proof_chart: Chart, monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    """
    Forecast known output classes without executing assertions or issuing certificates.

    Args:
        proof_chart (Chart): Eight-input chart with three supported output classes.
        monkeypatch (pytest.MonkeyPatch): Prevents accidental renderer execution.
        enabled (bool): Whether the configured run enables pruning.

    Returns:
        None: Forecasts distinguish potential savings from configured work.
    """
    renderer = Mock(side_effect=AssertionError("dry-run rendered"))
    prop = Mock(side_effect=AssertionError("dry-run asserted"))
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", renderer)
    before = {path: path.read_bytes() for path in proof_chart.path.rglob("*") if path.is_file()}
    report = check_chart(
        proof_chart,
        permutations=2,
        dry_run=True,
        prune_equivalent=enabled,
        artifact_dir=proof_chart.path / "artifacts",
        properties=(prop,),
    )
    forecast = mapping(report["progressive_estimate"])
    configured = mapping(forecast["configured_run"])
    assert configured["candidate_inputs"] == 8
    assert configured["filter_forecast_renders"] == 3
    assert configured["filter_forecast_removed"] == 5
    assert configured["configured_renders"] == (3 if enabled else 8)
    assert configured["estimated_seconds"] is None
    assert forecast["actual_renders"] == 0
    assert forecast["pruning_certificates"] == []
    if enabled:
        assert mapping(report["pruning"])["certificates"] == []
    renderer.assert_not_called()
    prop.assert_not_called()
    assert before == {path: path.read_bytes() for path in proof_chart.path.rglob("*") if path.is_file()}
