"""
Verify exported values as replacement defaults and graph evidence with real Helm renders.
"""

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.cli import main
from hypothesis_helm.compiler.graph import export_graph
from hypothesis_helm.compiler.minimum import export_minimal
from hypothesis_helm.schemas.contracts import mapping

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not shutil.which("helm"), reason="Helm required"),
]


@pytest.fixture
def chart(tmp_path: Path) -> Chart:
    """
    Build a chart requiring concrete false and zero values and allowing an optional resource.

    Args:
        tmp_path (Path): Isolated chart directory.

    Returns:
        Chart: Schema-backed chart with reducible defaults.
    """
    (tmp_path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: minimum
        version: 1.0.0
    """)
    )
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: minimum
        data:
          flag: {{ .Values.flag | quote }}
          count: {{ .Values.count | quote }}
        {{ if .Values.enabled }}
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: optional
        {{ end }}
    """)
    )
    schema: dict[str, object] = {
        "type": "object",
        "required": ["flag", "count"],
        "properties": {
            "flag": {"const": False},
            "count": {"const": 0},
            "enabled": {"type": "boolean"},
            "unused": {"type": "string"},
        },
    }
    defaults: dict[str, object] = {"flag": False, "count": 0, "enabled": True, "unused": "unused"}
    (tmp_path / "values.schema.json").write_text(json.dumps(schema))
    (tmp_path / "values.yaml").write_text(yamlio.dump(defaults))
    return Chart(tmp_path, schema, defaults)


def test_verified_concrete_replacement(chart: Chart, tmp_path: Path) -> None:
    """
    Keep required false and zero, remove optional resources, and verify replacement defaults.

    Args:
        chart (Chart): Reducible chart fixture.
        tmp_path (Path): Export destination.

    Returns:
        None: Export is stable, valid without original defaults, and honestly deletion-minimal.
    """
    original = (chart.path / "values.yaml").read_bytes()
    target = tmp_path / "values-minimal.yaml"
    result = export_minimal(chart, target)
    documents = yamlio.load_all(target.read_text())
    assert documents[0] == {"flag": False, "count": 0}
    verification = mapping(result["verification"])
    assert verification["verified"] and verification["deletion_minimal"]
    assert verification["nonempty_resources"] == 1
    assert not verification["globally_minimal_proven"]
    assert (chart.path / "values.yaml").read_bytes() == original
    first = target.read_bytes()
    proof_path = target.with_suffix(".proof")
    proof_bytes = proof_path.read_bytes()
    proof = json.loads(proof_bytes)
    assert proof["verification"]["verified"]
    assert "elapsed_seconds" not in proof["verification"]
    assert proof["verification"]["candidates_checked"] == verification["candidates_checked"]
    assert "verification" not in mapping(documents[1])
    export_minimal(chart, target)
    assert target.read_bytes() == first
    assert proof_path.read_bytes() == proof_bytes
    (chart.path / "values.yaml").write_text(yamlio.dump(documents[0]))
    assert len(render(Chart.load(chart.path), {}, stream=False)) == 1


def test_unverified_example_is_exported(chart: Chart, tmp_path: Path) -> None:
    """
    Export the example with an explicit failure instead of searching for replacement values.

    Args:
        chart (Chart): Fixture changed to render no resources.
        tmp_path (Path): Export destination.

    Returns:
        None: The example is inspectable and never labeled verified or deletion-minimal.
    """
    (chart.path / "templates/config.yaml").write_text("{{/* no resources */}}")
    target = tmp_path / "values-minimal.yaml"
    result = export_minimal(chart, target, budget=2)
    assert target.exists()
    verification = mapping(result["verification"])
    assert not verification["verified"]
    assert not verification["deletion_minimal"]
    assert verification["validation_error"] == "Candidate renders no resources"
    assert yamlio.load_all(target.read_text())[0] == chart.defaults


def test_graph_evidence_and_no_secret_values(chart: Chart, tmp_path: Path) -> None:
    """
    Relate named input paths to source templates and observed resources with explicit limits.

    Args:
        chart (Chart): Fixture with a conditional resource.
        tmp_path (Path): Graph destination.

    Returns:
        None: Graph contains reference and render edges without claiming complete causality.
    """
    target = tmp_path / "graph.json"
    result = export_graph(chart, target)
    graph = json.loads(target.read_text())
    assert graph["baseline"] == {"status": "rendered", "resources": 2}
    assert not graph["complete_influence_map_proven"]
    kinds = {edge["kind"] for edge in graph["edges"]}
    assert {"potential-reference", "condition", "observed-render", "contains"} <= kinds
    assert Path(str(result["dot"])).read_text().startswith("digraph helm {")
    assert any(node["kind"] == "manifest-field" for node in graph["nodes"])
    assert all("value" not in node for node in graph["nodes"])
    (chart.path / "templates/config.yaml").write_text('{{ fail "DO-NOT-EXPORT-SECRET" }}')
    export_graph(chart, target)
    assert json.loads(target.read_text())["baseline"]["status"] == "unavailable"
    assert "DO-NOT-EXPORT-SECRET" not in target.read_text()


def test_repository_exports_basename_only(chart: Chart, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Export beside each discovered chart and reject path overrides before writing files.

    Args:
        chart (Chart): Source chart.
        tmp_path (Path): File list destination.
        capsys (pytest.CaptureFixture[str]): CLI output capture.

    Returns:
        None: Exported YAML files and their proofs appear together in the staging inventory.
    """
    nested = tmp_path / "nested"
    shutil.copytree(chart.path, nested, ignore=shutil.ignore_patterns("nested"))
    listing = tmp_path / "files.txt"
    assert main(["export-minimal-values", str(chart.path), "--files-list", str(listing)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["exported"] == 2
    assert set(listing.read_bytes().split(b"\0")[:-1]) == {
        str(path / ("values-minimal" + suffix)).encode() for path in (chart.path, nested) for suffix in (".yaml", ".proof")
    }
    assert main(["export-minimal-values", str(chart.path), "--filename", "../outside.yaml"]) == 2
    assert "basename" in capsys.readouterr().out


def test_budget_retains_only_verified_candidate(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the last verified baseline when the minimization deadline interrupts another render.

    Args:
        chart (Chart): Valid chart before minimization.
        tmp_path (Path): Export destination.
        monkeypatch (pytest.MonkeyPatch): Delay subsequent render attempts beyond the budget.

    Returns:
        None: A verified export remains available with incomplete minimality explicitly recorded.
    """
    import time

    from hypothesis_helm.compiler import minimum

    original_render = render
    calls = 0

    def delayed(source: Chart, values: dict[str, object], **options: object) -> list[dict[str, object]]:
        """
        Complete the initial baseline and let the deadline interrupt a subsequent render.

        Args:
            source (Chart): Isolated candidate chart.
            values (dict[str, object]): Candidate overrides.
            **options (object): Renderer options unused by this deterministic fixture.

        Returns:
            list[dict[str, object]]: Real verified baseline resources before the delay.
        """
        nonlocal calls
        calls += 1
        if calls > 1:
            time.sleep(2)
        return original_render(source, values, stream=False)

    monkeypatch.setattr(minimum, "render", delayed)
    target = tmp_path / "values-minimal.yaml"
    report = export_minimal(chart, target, budget=1)
    verified = mapping(report["verification"])
    assert verified["verified"] and not verified["deletion_minimal"]
    assert not verified["search_complete"]
    assert yamlio.load_all(target.read_text())[0] == chart.defaults


def test_explicit_null_is_a_value_without_changing_other_writers() -> None:
    """
    Preserve legitimate nulls explicitly while keeping ordinary YAML serialization isolated.

    Returns:
        None: Explicit exports contain null tokens, not bare keys, without global mutation.
    """
    before = yamlio.dump({"nullable": None})
    exported = yamlio.dump({"nullable": None, "flag": False, "count": 0}, explicit_null=True)
    assert "nullable: null" in exported
    assert yamlio.load(exported) == {"nullable": None, "flag": False, "count": 0}
    assert yamlio.dump({"nullable": None}) == before


def test_ci_commit_only_exported_files(chart: Chart, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Commit back the YAML and its proof through a local bare remote without staging other work.

    Args:
        chart (Chart): Chart whose defaults will be reduced.
        tmp_path (Path): Isolated Git working tree.
        monkeypatch (pytest.MonkeyPatch): Isolate Git author and commit settings.

    Returns:
        None: One writer pushes the exported pair and a repeat makes no new commit.
    """
    import os
    import subprocess
    import sys

    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")
    remote = tmp_path.parent / f"{tmp_path.name}-remote.git"

    def git(*arguments: str) -> str:
        """
        Run Git only inside this test's temporary working tree.

        Args:
            *arguments (str): Literal Git arguments.

        Returns:
            str: Successful command output.
        """
        return subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "--bare", str(remote))
    git("init", "-b", "main")
    git("config", "commit.gpgsign", "false")
    git("add", "Chart.yaml", "values.yaml", "values.schema.json", "templates")
    git("commit", "-m", "Fixture")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    (tmp_path / "unrelated.txt").write_text("Keep this out of the commit")
    executable = Path(sys.executable).parent / "hypothesis-helm"
    native_helm = shutil.which("helm")
    assert native_helm
    binaries = tmp_path / "bin"
    binaries.mkdir()
    wrapper = binaries / "helm"
    # JSON-looking or glob characters in filenames must stay literal Git pathspecs.
    import shlex

    wrapper.write_text(
        dedent(f"""
        #!/usr/bin/env bash
        if [[ "$1" == hypothesis ]]; then
          shift
          exec {shlex.quote(str(executable))} "$@"
        fi
        exec {shlex.quote(native_helm)} "$@"
    """).lstrip()
    )
    wrapper.chmod(0o755)
    script = Path(__file__).resolve().parents[1] / "integrations/minimal_values.sh"
    environment = dict(
        os.environ,
        PATH=f"{binaries}:{os.environ['PATH']}",
        HH_CHART=str(chart.path),
        HH_COMMIT_MINIMAL_VALUES="true",
        HH_COMMIT_BRANCH="main",
        HH_RESOLVED_SHARD="1/3",
        HH_MINIMAL_VALUES_FILENAME="values-[review].yaml",
        RUNNER_TEMP=str(tmp_path),
    )
    for _ in range(2):
        subprocess.run(
            ["bash", str(script)],
            cwd=tmp_path,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    assert git("rev-list", "--count", "HEAD") == "2"
    assert set(git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()) == {
        "values-[review].yaml",
        "values-[review].proof",
    }
    assert "unrelated.txt" not in git("ls-files")
    assert ".inventory.json" not in git("ls-files")
    assert git("rev-parse", "HEAD") == git("rev-parse", "origin/main")
    environment["HH_RESOLVED_SHARD"] = "2/3"
    environment["HH_CHART"] = "does-not-exist"
    subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_invalid_supplied_values_are_not_replaced(chart: Chart, tmp_path: Path) -> None:
    """
    Preserve supplied values and report validation failures without generated repair.

    Args:
        chart (Chart): Fixture requiring a false flag but supplied with true.
        tmp_path (Path): Export destination.

    Returns:
        None: The illustrative export retains the supplied value and records its schema failure.
    """
    defaults = {**chart.defaults, "flag": True}
    (chart.path / "values.yaml").write_text(yamlio.dump(defaults))
    target = tmp_path / "values-minimal.yaml"
    result = export_minimal(Chart(chart.path, chart.schema, defaults), target, budget=10)
    assert not mapping(result["verification"])["verified"]
    assert yamlio.load_all(target.read_text())[0] == defaults


def test_proof_cannot_overwrite_symlinks_or_values(chart: Chart, tmp_path: Path) -> None:
    """
    Reject colliding or redirected proof paths before changing either output file.

    Args:
        chart (Chart): Source chart fixture.
        tmp_path (Path): Output destination.

    Returns:
        None: Existing source and output bytes remain intact on validation errors.
    """
    from hypothesis_helm.compiler.inputs import InputInventory

    inventory = InputInventory.build(chart)
    target = tmp_path / "values-minimal.yaml"
    target.write_text("keep this output")
    proof = target.with_suffix(".proof")
    proof.symlink_to(chart.path / "values.yaml")
    source = (chart.path / "values.yaml").read_bytes()
    with pytest.raises(ValueError, match="symbolic"):
        inventory.dump(chart, target)
    assert target.read_text() == "keep this output"
    assert (chart.path / "values.yaml").read_bytes() == source
    with pytest.raises(ValueError, match="differ"):
        inventory.dump(chart, tmp_path / "same.proof")
    assert not (tmp_path / "same.proof").exists()
