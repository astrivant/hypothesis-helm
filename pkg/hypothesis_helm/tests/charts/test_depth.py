"""
Limit dependency discovery and input traversal without changing Helm's chart source.
"""

import json
import shutil
import tarfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hypothesis_helm.charts.depth import active_depth, dependency_depth
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.repositories.scan import discover_charts
from hypothesis_helm.charts.suites.generate import coalesce, generate_tests
from hypothesis_helm.charts.suites.runtime import prepared_chart
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.cli import argument_parser, main
from hypothesis_helm.compiler.passes.inputs import InputInventory
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.generation.finite import enumerate_values


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """
    Create a root chart, an aliased child and a grandchild with independently variable flags.

    Args:
        tmp_path (Path): Isolated chart workspace.

    Returns:
        Path: Root chart containing ordinary nested values and two dependency levels.
    """
    root = tmp_path / "repo/team/apps/root"
    value: dict[str, object] = {}
    schema: dict[str, object] = {}
    for path, name, child, alias in (
        (root / "charts/child/charts/grand", "grand", "", ""),
        (root / "charts/child", "child", "grand", "grand"),
        (root, "root", "child", "alias"),
    ):
        (path / "templates").mkdir(parents=True)
        metadata: dict[str, object] = {"apiVersion": "v2", "name": name, "version": "1.0.0"}
        properties: dict[str, object] = {"flag": {"type": "boolean"}}
        defaults: dict[str, object] = {"flag": False}
        if child:
            metadata["dependencies"] = [{"name": child, "alias": alias, "version": "1.0.0"}]
            properties[alias] = schema
            defaults[alias] = value
        if name == "root":
            properties["nested"] = {
                "type": "object",
                "properties": {"ordinary": {"const": "kept"}},
                "required": ["ordinary"],
                "additionalProperties": False,
            }
            defaults["nested"] = {"ordinary": "kept"}
        schema = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
        value = defaults
        (path / "Chart.yaml").write_text(yamlio.dump(metadata))
        (path / "values.yaml").write_text(yamlio.dump(defaults))
        (path / "values.schema.json").write_text(json.dumps(schema))
        (path / "templates/config.yaml").write_text(
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ .Chart.Name }}\ndata:\n  flag: {{ .Values.flag | quote }}\n"
        )
    return root


@pytest.mark.parametrize("depth", [0, 1, 2])
@pytest.mark.parametrize("packed", [False, True])
def test_dependency_inputs_obey_depth(source: Path, depth: int, packed: bool) -> None:
    """
    Traverse only permitted dependency levels and freeze deeper values during whole-chart generation.

    Args:
        source (Path): Aliased chart with a nested dependency.
        depth (int): Requested dependency depth.
        packed (bool): Whether the direct dependency is supplied as a Helm archive.

    Returns:
        None: Path inventories and generated configurations obey the same boundary.
    """
    if packed:
        with tarfile.open(source / "charts/child-1.0.0.tgz", "w:gz") as bundle:
            bundle.add(source / "charts/child", arcname="child")
        shutil.rmtree(source / "charts/child")
    with dependency_depth(depth):
        chart = Chart.load(source)
        inventory = InputInventory.build(chart)
        paths = {entry.path for entry in coalesce(chart).paths}
        assert ("nested", "ordinary") in paths
        assert (("alias", "flag") in paths) is (depth >= 1)
        assert (("alias", "grand", "flag") in paths) is (depth >= 2)
        assert (("alias", "flag") in inventory.known) is (depth >= 1)
        assert (("alias", "grand", "flag") in inventory.known) is (depth >= 2)
        assert len(inventory.dependencies.nodes) == depth
        assert not inventory.dependencies.diagnostics
        schema = chart.generation_schema()

        @given(st.data())
        @settings(max_examples=12, deadline=None)
        def generated(data: st.DataObject) -> None:
            """
            Keep all out-of-scope dependency values unchanged in sampled configurations.

            Args:
                data (st.DataObject): Hypothesis draw context for the scoped chart strategy.

            Returns:
                None: Random generation respects the same depth as path discovery.
            """
            values = data.draw(chart.strategy())
            if depth == 0:
                assert values["alias"] == chart.defaults["alias"]
            elif depth == 1:
                assert mapping(values["alias"])["grand"] == {"flag": False}

        generated()
        cases = enumerate_values(schema, 100)
        assert len(cases) == 2 ** (depth + 1)


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_repository_directories_do_not_count_as_dependencies(source: Path, depth: int) -> None:
    """
    Find root charts at any directory depth and count only nested chart boundaries.

    Args:
        source (Path): Chart nested inside ordinary repository directories.
        depth (int): Selected number of dependency levels.

    Returns:
        None: Starting from a repository or a chart selects the same chart subtree.
    """
    direct = discover_charts(source, max_depth=depth)
    repository = discover_charts(source.parents[2], max_depth=depth)
    assert len(direct) == len(repository) == depth + 1
    assert [record["depth"] for record in direct] == list(range(depth + 1))
    assert [record["name"] for record in direct] == [record["name"] for record in repository]


def test_generated_suite_retains_depth(source: Path, tmp_path: Path) -> None:
    """
    Preserve traversal scope when a saved suite is reopened outside its originating command.

    Args:
        source (Path): Source chart with deeper dependency values.
        tmp_path (Path): Generated-suite workspace.

    Returns:
        None: Generated tests exclude dependency paths and replay freezes the same dependency inputs.
    """
    output = tmp_path / "suite"
    previous = active_depth()
    with dependency_depth(0):
        generate_tests(Chart.load(source), output)
    assert active_depth() == previous
    inventory = json.loads((output / "paths.json").read_text())
    assert all(entry["path"][0] != "alias" for entry in inventory["paths"])
    with prepared_chart(source, output) as chart:
        assert active_depth() == 0
        assert chart.dependency_model is not None
        assert chart.dependency_model.excluded == {("alias",)}
        assert len(enumerate_values(chart.generation_schema(), 100)) == 2
    assert active_depth() == previous


@pytest.mark.parametrize("command", ["test", "scan"])
def test_cli_defaults_to_root_chart_and_rejects_negative_depth(command: str) -> None:
    """
    Expose the same depth policy for local and remote traversal before any source access.

    Args:
        command (str): Local testing or remote scanning command.

    Returns:
        None: Unspecified depth is zero and invalid negative depths stop during argument validation.
    """
    assert argument_parser().parse_args([command, "missing"]).max_depth == 0
    assert argument_parser().parse_args([command, "missing", "--max-depth", "2"]).max_depth == 2
    with pytest.raises(SystemExit) as result:
        main([command, "missing", "--max-depth", "-1"])
    assert result.value.code == 2
