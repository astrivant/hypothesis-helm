"""
Compare dependency activation and guided path generation with native Helm behavior.
"""

import copy
import io
import json
import shutil
import tarfile
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.generate import ValuePath, coalesce
from hypothesis_helm.charts.generated import check_path
from hypothesis_helm.charts.paths import path_strategy
from hypothesis_helm.charts.runner import Chart, RenderFailure, check_chart, render
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.passes.dependencies import Dependencies, unpack
from hypothesis_helm.compiler.passes.graph import export_graph
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.compiler.passes.pruning import Pruner
from hypothesis_helm.compiler.passes.rejections import RejectionPolicy
from hypothesis_helm.schemas.contracts import mapping, sequence
from hypothesis_helm.schemas.groups import infer_groups
from hypothesis_helm.schemas.model import ValuesModel


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Create a disabled aliased dependency whose input also affects a parent resource.

    Args:
        tmp_path (Path): Isolated parent and installed child chart tree.

    Returns:
        Chart: Root input contract with an independently schema-valid child failure.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: parent
        version: 1.0.0
        dependencies:
          - name: store
            alias: cache
            version: 1.0.0
            condition: enableCache,features.cache
            tags: [backend, forced]
        """)
    )
    defaults: dict[str, object] = {"enableCache": False, "cache": {"count": 1}, "tags": {"backend": False}}
    (tmp_path / "values.yaml").write_text(yamlio.dump(defaults))
    (tmp_path / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: parent
        data:
          count: {{ .Values.cache.count | quote }}
        """)
    )
    child = tmp_path / "charts/store"
    (child / "templates").mkdir(parents=True)
    (child / "Chart.yaml").write_text(yamlio.dump({"apiVersion": "v2", "name": "store", "version": "1.0.0"}))
    (child / "values.yaml").write_text(yamlio.dump({"count": 1}))
    (child / "values.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"count": {"type": "integer", "minimum": 0, "maximum": 2}}})
    )
    (child / "templates/config.yaml").write_text(
        dedent("""
        {{ if eq (int .Values.count) 0 }}{{ fail "child count must be nonzero" }}{{ end }}
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: {{ .Chart.Name }}
        data:
          count: {{ .Values.count | quote }}
        """)
    )
    return Chart(tmp_path, {"type": "object"}, defaults)


def test_inventory_discovers_metadata_controls_and_child_scopes(chart: Chart) -> None:
    """
    Discover absent condition paths without inventing baseline activation values.

    Args:
        chart (Chart): Aliased installed dependency.

    Returns:
        None: Controls are Boolean generation levers, references are namespaced, and originals stay intact.
    """
    original = copy.deepcopy(chart.defaults)
    inventory = InputInventory.build(chart)
    assert {("enableCache",), ("features", "cache"), ("tags", "forced"), ("cache", "count")} <= inventory.known
    report = inventory.report()
    activation = mapping(report["dependency_activation"])
    assert mapping(sequence(activation["dependencies"])[0])["baseline_enabled"] is False
    model = coalesce(chart)
    entries = {entry.path: entry.schema for entry in model.paths}
    assert entries[("features", "cache")]["type"] == "boolean"
    assert entries[("cache", "count")]["maximum"] == 2
    assert "features" not in model.values and "forced" not in mapping(model.values["tags"])
    assert chart.defaults == original
    assert any(ref.file == "charts/cache/templates/config.yaml" for ref in inventory.dependencies.references)
    assert Pruner(chart.path, chart.defaults, ValuesModel.from_schema(chart.schema)).disabled
    groups, _ = infer_groups(chart.path, model.schema)
    assert any(group.source == "dependency:cache" and {("enableCache",), ("cache", "count")} <= set(group.paths) for group in groups)


@pytest.mark.integration
@pytest.mark.parametrize(
    "selected,values", [(("features", "cache"), {"features": {"cache": True}}), (("tags", "backend"), {"tags": {"backend": True}})]
)
def test_selected_fallback_controls_are_not_shadowed(chart: Chart, selected: tuple[str, ...], values: dict[str, object]) -> None:
    """
    Expose a fallback condition or tag while retaining the original shadowed context.

    Args:
        chart (Chart): Dependency disabled by the first Boolean condition.
        selected (tuple[str, ...]): Later condition or tag being tested.
        values (dict[str, object]): Explicit selected control input.

    Returns:
        None: The earlier condition is removed only in the additional schema-valid context.
    """
    contexts = Dependencies.build(chart.path).contexts(chart.defaults, values, selected, lambda _: True)
    assert contexts[0]["enableCache"] is None
    assert contexts[-1] == values
    assert len(render(chart, contexts[0])) == 2
    assert len(render(chart, contexts[-1])) == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_dependency_inventory_stays_conservative_without_v2_declarations(chart: Chart, legacy: bool) -> None:
    """
    Recognize installed implicit children and legacy requirements as incomplete cross-chart proofs.

    Args:
        chart (Chart): Parent with an installed chart whose declaration is moved or removed.
        legacy (bool): Move metadata to v1 requirements instead of retaining an implicit child.

    Returns:
        None: Both discovery routes retain child inputs and conservative filtering boundaries.
    """
    metadata = mapping(yamlio.load((chart.path / "Chart.yaml").read_text()))
    declared = metadata.pop("dependencies")
    if legacy:
        metadata["apiVersion"] = "v1"
        (chart.path / "requirements.yaml").write_text(yamlio.dump({"dependencies": declared}))
    (chart.path / "Chart.yaml").write_text(yamlio.dump(metadata))
    inventory = InputInventory.build(chart)
    assert inventory.usage_unknown
    assert ("cache" if legacy else "store", "count") in inventory.known
    assert len(inventory.dependencies.nodes) == 1


def test_missing_sources_and_unsafe_archives_stay_explicit(chart: Chart, tmp_path: Path) -> None:
    """
    Retain unknown cases and reject traversal members without extracting outside the workspace.

    Args:
        chart (Chart): Parent metadata still available after removing its installed child.
        tmp_path (Path): Malformed archive workspace.

    Returns:
        None: Missing sources remain unknown and archive paths cannot escape extraction.
    """
    shutil.rmtree(chart.path / "charts/store")
    dependencies = Dependencies.build(chart.path)
    assert dependencies.states(chart.defaults, {})[("cache",)] is None
    original: dict[str, object] = {"cache": {"count": 0}}
    assert dependencies.contexts(chart.defaults, original, ("cache", "count"), lambda _: True) == [original]
    assert dependencies.unavailable == 1
    archive = tmp_path / "bad.tgz"
    with tarfile.open(archive, "w:gz") as bundle:
        entry = tarfile.TarInfo("../escaped")
        entry.size = 4
        bundle.addfile(entry, io.BytesIO(b"oops"))
    destination = tmp_path / "unpacked"
    destination.mkdir()
    with pytest.raises(ValueError, match="unsafe"):
        unpack(archive, destination)
    assert not (tmp_path / "escaped").exists()


@pytest.mark.integration
def test_alias_instances_are_independent_and_globals_keep_types(chart: Chart) -> None:
    """
    Bind repeated child charts separately and preserve forwarded global values in generation.

    Args:
        chart (Chart): Parent with a reusable installed child chart.

    Returns:
        None: Activating one alias leaves the other disabled and globals retain their supplied type.
    """
    metadata = mapping(yamlio.load((chart.path / "Chart.yaml").read_text()))
    sequence(metadata["dependencies"]).append({"name": "store", "alias": "other", "version": "1.0.0", "condition": "other.enabled"})
    (chart.path / "Chart.yaml").write_text(yamlio.dump(metadata))
    chart.defaults["other"] = {"enabled": False}
    chart.defaults["global"] = {"label": "shared"}
    (chart.path / "values.yaml").write_text(yamlio.dump(chart.defaults))
    template = chart.path / "charts/store/templates/config.yaml"
    template.write_text(template.read_text() + "  label: {{ .Values.global.label | quote }}\n")
    dependencies = Dependencies.build(chart.path)
    contexts = dependencies.contexts(chart.defaults, {"cache": {"count": 2}}, ("cache", "count"), lambda _: True)
    assert dependencies.states(chart.defaults, contexts[0]) == {("cache",): True, ("other",): False}
    assert {mapping(resource["metadata"])["name"] for resource in render(chart, contexts[0])} == {"cache", "parent"}
    model = coalesce(chart)
    assert mapping(mapping(model.values["other"])["global"])["label"] == "shared"
    assert {entry.path: entry.schema for entry in model.paths}[("other", "global", "label")]["type"] == "string"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("overrides", "enabled"),
    [
        ({}, False),
        ({"enableCache": True}, True),
        ({"enableCache": False, "tags": {"backend": True}}, False),
        ({"enableCache": None, "features": {"cache": True}}, True),
        ({"enableCache": "ignored", "features": {"cache": False}, "tags": {"backend": True}}, False),
        ({"enableCache": None, "tags": {"backend": False, "forced": True}}, True),
        ({"enableCache": None, "tags": {"backend": None}}, True),
    ],
)
def test_condition_and_tag_precedence_matches_helm(chart: Chart, overrides: dict[str, object], enabled: bool) -> None:
    """
    Match ordered Boolean conditions, tag OR behavior, nulls, and ignored non-Boolean controls.

    Args:
        chart (Chart): Aliased installed dependency.
        overrides (dict[str, object]): Activation controls passed to native Helm.
        enabled (bool): Expected child inclusion.

    Returns:
        None: Compiler predictions agree with rendered resource identities.
    """
    dependencies = Dependencies.build(chart.path)
    assert dependencies.states(chart.defaults, overrides)[("cache",)] is enabled
    resources = render(chart, overrides)
    names = {mapping(resource["metadata"])["name"] for resource in resources}
    assert ("cache" in names) is enabled
    assert "parent" in names


@pytest.mark.integration
def test_guidance_finds_disabled_child_failure_and_preserves_baseline(chart: Chart, tmp_path: Path) -> None:
    """
    Exercise a child field with activation enabled and retain its parent-only context.

    Args:
        chart (Chart): Child that fails at zero only when enabled.
        tmp_path (Path): Reproducer artifact destination.

    Returns:
        None: Enabled context exposes the child bug and exact selected input is preserved.
    """
    dependencies = Dependencies.build(chart.path)
    values: dict[str, object] = {"cache": {"count": 0}}
    contexts = dependencies.contexts(chart.defaults, values, ("cache", "count"), lambda _: True)
    assert contexts == [{"cache": {"count": 0}, "enableCache": True}, values]
    assert len(render(chart, contexts[1])) == 1
    with pytest.raises(RenderFailure, match="child count"):
        render(chart, contexts[0])
    original = copy.deepcopy(values)
    blocked = dependencies.contexts(chart.defaults, values, ("cache", "count"), lambda candidate: not candidate.get("enableCache"))
    assert blocked == [values] and values == original
    # A selected control is never overwritten to activate its own dependency.
    assert dependencies.contexts(chart.defaults, {"enableCache": False}, ("enableCache",), lambda _: True) == [{"enableCache": False}]
    model = coalesce(chart)
    entry = ValuePath(("cache", "count"), {"const": 0})
    report = check_chart(
        chart, input_strategy=path_strategy(chart, entry, model.schema, dependencies), max_examples=10, artifact_dir=tmp_path / "results"
    )
    assert report["status"] == "failed"
    assert mapping(report["values"])["enableCache"] is True
    assert mapping(mapping(report["values"])["cache"])["count"] == 0
    observed = sequence(mapping(report["dependency_activation"])["render_attempts_by_predicted_state"])
    assert int(str(mapping(observed[0])["enabled"])) > 0


@pytest.mark.integration
def test_native_schema_validation_uses_child_defaults(chart: Chart, tmp_path: Path) -> None:
    """
    Accept required parent-schema fields supplied by Helm's installed child defaults.

    Args:
        chart (Chart): Installed child provides count while the parent omits it.
        tmp_path (Path): Result artifact directory.

    Returns:
        None: Parent-only Python merging cannot reject a Helm-valid baseline.
    """
    chart.defaults = {"enableCache": True}
    chart.schema = {
        "type": "object",
        "required": ["cache"],
        "properties": {"cache": {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer"}}}},
    }
    (chart.path / "values.yaml").write_text(yamlio.dump(chart.defaults))
    (chart.path / "values.schema.json").write_text(json.dumps(chart.schema))
    assert len(render(chart, {})) == 2
    result = check_chart(chart, input_strategy=st.just({}), max_examples=1, artifact_dir=tmp_path / "schema-results")
    assert result["status"] == "passed"


@pytest.mark.integration
def test_dependency_rejections_always_require_native_confirmation(chart: Chart, tmp_path: Path) -> None:
    """
    Prevent witness caching from authorizing exclusions across dependency contexts.

    Args:
        chart (Chart): Parent with installed dependencies and an explicit input guard.
        tmp_path (Path): Result artifact directory.

    Returns:
        None: A dependency scan retains native verification after two rejection witnesses.
    """
    template = chart.path / "templates/config.yaml"
    template.write_text(
        dedent("""
        {{ if eq (int .Values.cache.count) 0 }}{{ fail "zero rejected" }}{{ end }}
        """)
        + template.read_text()
    )
    policy = RejectionPolicy(Contracts.build(chart.path), chart.defaults)
    result = check_chart(
        chart, input_strategy=st.just({}), max_examples=1, rejection_policy=policy, artifact_dir=tmp_path / "rejection-results"
    )
    assert result["status"] == "passed"
    assert policy.verify_every_candidate
    values: dict[str, object] = {"cache": {"count": 0}}
    rejection = policy.predict(values)
    assert rejection is not None
    policy.verified(rejection, values)
    policy.verified(rejection, {**values, "enableCache": True})
    assert policy.needs_probe(rejection, values)
    assert policy.needs_probe(rejection, {**values, "enableCache": False})
    checked = check_chart(
        chart,
        input_strategy=st.just(values),
        max_examples=1,
        rejection_policy=policy,
        protected_paths=((),),
        fail_fast=True,
        artifact_dir=tmp_path / "verified-rejection",
    )
    assert checked["status"] == "configuration-rejected"
    assert mapping(checked["configuration_rejections"])["verification_renders"] == 1


@pytest.mark.integration
def test_generated_path_runner_uses_dependency_context(chart: Chart) -> None:
    """
    Keep saved generated suites consistent with direct recursive scans.

    Args:
        chart (Chart): Child that rejects a schema-valid zero input when active.

    Returns:
        None: The generated-test helper reaches an enabled child failure.
    """
    chart.dependency_model = Dependencies.build(chart.path)

    @given(st.data())
    @settings(max_examples=10, deadline=None)
    def property_test(data: st.DataObject) -> None:
        """
        Exercise the generated runtime using the ordinary Hypothesis draw context.

        Args:
            data (st.DataObject): Context choice draw supplied by Hypothesis.

        Returns:
            None: A real enabled child render must fail.
        """
        check_path(chart, ("cache", "count"), 0, data)

    with pytest.raises(RenderFailure, match="child count"):
        property_test()


@pytest.mark.integration
def test_packed_aliases_nested_controls_and_graph(chart: Chart, tmp_path: Path) -> None:
    """
    Discover packed children, nested scopes, and activation edges using alias identities.

    Args:
        chart (Chart): Parent with one installed dependency directory.
        tmp_path (Path): Archive and graph artifact workspace.

    Returns:
        None: Both levels activate for a leaf input and the graph retains conditional edges.
    """
    child = chart.path / "charts/store"
    metadata = mapping(yamlio.load((child / "Chart.yaml").read_text()))
    metadata["dependencies"] = [{"name": "leaf", "version": "1.0.0", "condition": "leaf.enabled"}]
    (child / "Chart.yaml").write_text(yamlio.dump(metadata))
    (child / "values.yaml").write_text(yamlio.dump({"count": 1, "leaf": {"enabled": False}}))
    leaf = child / "charts/leaf"
    (leaf / "templates").mkdir(parents=True)
    (leaf / "Chart.yaml").write_text(yamlio.dump({"apiVersion": "v2", "name": "leaf", "version": "1.0.0"}))
    (leaf / "values.yaml").write_text(yamlio.dump({"count": 1}))
    (leaf / "templates/config.yaml").write_text((child / "templates/config.yaml").read_text())
    archive = chart.path / "charts/store-1.0.0.tgz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(child, arcname="store")
    shutil.rmtree(child)
    dependencies = Dependencies.build(chart.path)
    assert [node.path for node in dependencies.nodes] == [("cache",), ("cache", "leaf")]
    assert dependencies.states(chart.defaults, {}) == {("cache",): False, ("cache", "leaf"): False}
    contexts = dependencies.contexts(chart.defaults, {"cache": {"leaf": {"count": 2}}}, ("cache", "leaf", "count"), lambda _: True)
    assert dependencies.states(chart.defaults, contexts[0]) == {("cache",): True, ("cache", "leaf"): True}
    names = {mapping(resource["metadata"])["name"] for resource in render(chart, contexts[0])}
    assert names == {"parent", "cache", "leaf"}
    target = tmp_path / "graph.json"
    export_graph(chart, target)
    graph = json.loads(target.read_text())
    kinds = {edge["kind"] for edge in graph["edges"]}
    assert {"dependency-condition", "dependency-tag", "requires-enabled-parent", "conditionally-includes"} <= kinds
    identifiers = {node["id"] for node in graph["nodes"]}
    assert all(edge["from"] in identifiers and edge["to"] in identifiers for edge in graph["edges"])
    assert any(node.get("path") == "charts/cache/charts/leaf/templates/config.yaml" for node in graph["nodes"])
    assert "helm-dependency-analysis-" not in target.read_text()
