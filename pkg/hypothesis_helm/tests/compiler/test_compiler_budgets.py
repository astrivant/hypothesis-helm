"""
Exercise configurable compiler budgets at their conservative analysis boundaries.
"""

import io
import json
import tarfile
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.inspection.templates import discover
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.compiler.asts.contracts import Contracts
from hypothesis_helm.compiler.asts.renderer import RendererContext, archive_files, chart_files
from hypothesis_helm.compiler.asts.transformations import calculate
from hypothesis_helm.compiler.complexity import output_profile
from hypothesis_helm.compiler.limits import DEFAULT_LIMITS, active_limits, compiler_limits
from hypothesis_helm.compiler.passes.complexity import measure
from hypothesis_helm.compiler.passes.dependencies import Dependencies, unpack
from hypothesis_helm.compiler.passes.domains import project
from hypothesis_helm.compiler.passes.pruning import snapshot
from hypothesis_helm.environment import refresh_env
from hypothesis_helm.exceptions.compiler import Unavailable, UnsupportedTransformation
from hypothesis_helm.execution.state.cache import fingerprint
from hypothesis_helm.findings.configuration import COMPLETE_EXAMPLE
from hypothesis_helm.schemas.configuration.policy import ENVIRONMENT, load_policy


def configure(monkeypatch: pytest.MonkeyPatch, **limits: int) -> None:
    """
    Set compiler budgets through the same serialized policy inherited by workers.

    Args:
        monkeypatch (pytest.MonkeyPatch): Isolate the process environment.
        **limits (int): Selected positive resource budgets.

    Returns:
        None: Subsequent analyses inherit the settings.
    """
    monkeypatch.setenv(ENVIRONMENT, json.dumps({"compiler": limits}))
    refresh_env()


def archive(contents: dict[str, bytes]) -> bytes:
    """
    Build a compressed chart archive with predictable member counts and inflated sizes.

    Args:
        contents (dict[str, bytes]): Archive-relative regular files.

    Returns:
        bytes: Gzip-compressed tar data.
    """
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as bundle:
        for name, data in contents.items():
            info = tarfile.TarInfo("chart/" + name)
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def fixture_chart(root: Path, body: str) -> Chart:
    """
    Create a closed-domain chart whose template can exercise compiler budgets.

    Args:
        root (Path): Temporary chart directory.
        body (str): Template source to inspect.

    Returns:
        Chart: Loaded chart with two Boolean fields and no external dependencies.
    """
    (root / "templates").mkdir(parents=True)
    (root / "Chart.yaml").write_text(yamlio.dump({"apiVersion": "v2", "name": root.name, "version": "1.0.0"}))
    (root / "values.yaml").write_text(yamlio.dump({"first": True, "second": False}))
    (root / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"first": {"type": "boolean"}, "second": {"type": "boolean"}},
                "required": ["first", "second"],
            }
        )
    )
    (root / "templates/config.yaml").write_text(body)
    return Chart.load(root)


@pytest.mark.parametrize("name", DEFAULT_LIMITS)
@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "10000", None])
def test_budget_validation(name: str, invalid: object) -> None:
    """
    Reject invalid values for every configurable budget instead of coercing them.

    Args:
        name (str): Supported compiler setting.
        invalid (object): Nonpositive or incorrectly typed input.

    Returns:
        None: An actionable error identifies the exact configuration key.
    """
    with pytest.raises(ValueError, match=f"compiler.{name} must be a positive integer"):
        compiler_limits({name: invalid})


def test_config_documentation_and_cache_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep defaults, generated documentation, policy inheritance and cache invalidation aligned.

    Args:
        tmp_path (Path): Policy directory.
        monkeypatch (pytest.MonkeyPatch): Apply resolved coordinator settings.

    Returns:
        None: The example is complete and changed budgets cannot reuse a previous policy cache.
    """
    document = yamlio.load(COMPLETE_EXAMPLE)
    assert isinstance(document, dict)
    assert document["compiler"] == DEFAULT_LIMITS
    config = tmp_path / "config.yaml"
    config.write_text(yamlio.dump({"compiler": {"max_files": 1}}))
    monkeypatch.setenv(ENVIRONMENT, json.dumps(load_policy(config)))
    refresh_env()
    original = RendererContext(tmp_path)
    previous = fingerprint(tmp_path, 0, None, "none")
    configure(monkeypatch, max_files=2)
    assert original.limits["max_files"] == 1
    assert RendererContext(tmp_path).limits["max_files"] == 2
    assert fingerprint(tmp_path, 0, None, "none") != previous
    detached = active_limits()
    detached["max_files"] = 999
    assert active_limits()["max_files"] == 2


@pytest.mark.parametrize("reader", ["context", "dependencies"])
@pytest.mark.parametrize("budget", ["max_files", "max_context_bytes"])
def test_archive_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str, budget: str) -> None:
    """
    Enforce the same inclusive count and inflated-byte boundaries in both archive readers.

    Args:
        tmp_path (Path): Archive and unpack destination.
        monkeypatch (pytest.MonkeyPatch): Apply lower and raised budgets.
        reader (str): Compiler reader under test.
        budget (str): Member-count or byte budget.

    Returns:
        None: Raising only the selected limit admits the previously unresolved archive.
    """
    files = {"one.txt": b"x" * 4096, "two.txt": b"y" * 4096}
    data = archive(files)
    packed = tmp_path / "chart.tgz"
    packed.write_bytes(data)
    boundary = len(files) if budget == "max_files" else sum(map(len, files.values()))
    for limit in (boundary - 1, boundary):
        configure(monkeypatch, **{budget: limit})
        if limit < boundary:
            with pytest.raises(ValueError, match=f"compiler.{budget}="):
                if reader == "context":
                    archive_files(io.BytesIO(data))
                else:
                    unpack(packed, tmp_path / "unpacked")
        elif reader == "context":
            assert archive_files(io.BytesIO(data)) == files
        else:
            unpack(packed, tmp_path / "unpacked")
            assert (tmp_path / "unpacked/chart/two.txt").read_bytes() == files["two.txt"]


def test_nested_archives_use_captured_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the calling context's limits when nested dependency files are opened later.

    Args:
        monkeypatch (pytest.MonkeyPatch): Change current policy after taking a context snapshot.

    Returns:
        None: An environment change cannot bypass a captured budget for a nested archive.
    """
    data = archive({"Chart.yaml": b"name: child\napiVersion: v2\n", "a.txt": b"a", "b.txt": b"b"})
    files = {"charts/child.tgz": data}
    configure(monkeypatch, max_files=2)
    captured = active_limits()
    configure(monkeypatch, max_files=3)
    with pytest.raises(Unavailable, match="compiler.max_files=2"):
        chart_files(files, ("child",), {("child",): "child"}, limits=captured)
    assert chart_files(files, ("child",), {("child",): "child"}).get("b.txt") == "b"


@pytest.mark.parametrize(
    ("budget", "limit", "body", "values"),
    [
        ("max_steps", 1, '{{ if .Values.first }}{{ fail "reject" }}{{ end }}', {"first": True}),
        (
            "max_range_items",
            1,
            '{{ range .Values.items }}{{ if eq . "bad" }}{{ fail "reject" }}{{ end }}{{ end }}',
            {"items": ["good", "bad"]},
        ),
        ("max_template_bytes", 1, '{{ if eq (tpl .Values.script .) "bad" }}{{ fail "reject" }}{{ end }}', {"script": "bad"}),
    ],
)
def test_rejection_budgets_defer_without_excluding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget: str, limit: int, body: str, values: dict[str, object]
) -> None:
    """
    Distinguish an unresolved budget-limited prediction from a supported rejection.

    Args:
        tmp_path (Path): Chart directory.
        monkeypatch (pytest.MonkeyPatch): Change inherited analysis budget.
        budget (str): Relevant compiler setting.
        limit (int): Insufficient analysis budget.
        body (str): Rejection template requiring more work.
        values (dict[str, object]): Candidate that executes the rejection.

    Returns:
        None: Low budgets emit fallback evidence; raised budgets establish the rejection.
    """
    chart = fixture_chart(tmp_path, body)
    configure(monkeypatch, **{budget: limit})
    limited = Contracts.build(chart.path)
    assert limited.predict(values) is None
    assert budget in str(limited.fallbacks)
    configure(monkeypatch, **{budget: 100})
    assert Contracts.build(chart.path).predict(values) is not None
    assert limited.predict(values) is None


def test_discovery_and_projection_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Apply configured traversal and projection bounds without claiming complete analysis.

    Args:
        tmp_path (Path): Chart directory.
        monkeypatch (pytest.MonkeyPatch): Change discovery and variant budgets.

    Returns:
        None: Discovery resumes with a larger budget and projection records variant exhaustion.
    """
    chart = fixture_chart(
        tmp_path,
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: example
        data:
          first: {{ .Values.first | quote }}
          {{ if .Values.second }}
          second: "on"
          {{ else }}
          second: "off"
          {{ end }}
        """),
    )
    configure(monkeypatch, max_discovery_nodes=1)
    refs, diagnostics = discover(chart.path)
    assert ("second",) not in [ref.path for ref in refs]
    assert "max_discovery_nodes=1" in str(diagnostics)
    configure(monkeypatch, max_discovery_nodes=100, max_symbolic_variants=1)
    refs, diagnostics = discover(chart.path)
    assert {ref.path for ref in refs} == {("first",), ("second",)}
    assert diagnostics == []
    assert "max_symbolic_variants=1" in str(project(chart.path, chart.schema)[1])
    configure(monkeypatch, max_symbolic_variants=2)
    assert "max_symbolic_variants" not in str(project(chart.path, chart.schema)[1])


@pytest.mark.parametrize(
    ("budget", "function", "args", "boundary"),
    [
        ("max_string_chars", "replace", ("a", "bb", "aa"), 4),
        ("max_regex_pattern_chars", "regexMatch", ("^[ab]$", "a"), 6),
        ("max_regex_subject_chars", "regexMatch", ("^[ab]+$", "aaa"), 3),
    ],
)
def test_expression_budgets_and_cached_patterns(
    monkeypatch: pytest.MonkeyPatch, budget: str, function: str, args: tuple[object, ...], boundary: int
) -> None:
    """
    Respect raised and lowered expression budgets even after a regex is cached.

    Args:
        monkeypatch (pytest.MonkeyPatch): Replace the inherited configuration.
        budget (str): String or regex budget.
        function (str): Supported transformation.
        args (tuple[object, ...]): Concrete arguments.
        boundary (int): Smallest sufficient budget.

    Returns:
        None: Cached results cannot bypass a subsequently lowered budget.
    """
    configure(monkeypatch, **{budget: boundary})
    assert calculate(function, args)
    configure(monkeypatch, **{budget: boundary - 1})
    with pytest.raises(UnsupportedTransformation, match=budget):
        calculate(function, args)


@pytest.mark.parametrize("budget", ["max_dependency_depth", "max_dependencies"])
def test_dependency_tree_budgets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget: str) -> None:
    """
    Bound dependency nesting and instance count separately, retaining incomplete-source evidence.

    Args:
        tmp_path (Path): Three-chart dependency tree.
        monkeypatch (pytest.MonkeyPatch): Set low and sufficient tree budgets.
        budget (str): Dependency depth or instance-count budget.

    Returns:
        None: Raising the selected budget admits the previously unresolved descendant.
    """
    current = tmp_path
    for index in range(3):
        current.mkdir(parents=True, exist_ok=True)
        metadata: dict[str, object] = {"apiVersion": "v2", "name": f"chart{index}", "version": "1.0.0"}
        if index < 2:
            metadata["dependencies"] = [{"name": f"chart{index + 1}", "version": "1.0.0"}]
        (current / "Chart.yaml").write_text(yamlio.dump(metadata))
        current = current / "charts" / f"chart{index + 1}"
    configure(monkeypatch, **{budget: 1})
    limited = Dependencies.build(tmp_path)
    assert len(limited.nodes) == 1
    assert budget in str(limited.diagnostics)
    configure(monkeypatch, **{budget: 2})
    complete = Dependencies.build(tmp_path)
    assert len(complete.nodes) == 2
    assert complete.diagnostics == []


def test_proof_and_complexity_budgets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Expose proof storage and complexity work limits without misreporting an exact maximum.

    Args:
        tmp_path (Path): Small closed-domain chart.
        monkeypatch (pytest.MonkeyPatch): Change each analysis budget independently.

    Returns:
        None: Low limits decline proofs; restored limits produce the supported maximum.
    """
    chart = fixture_chart(
        tmp_path,
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: example
        data:
          fixed: "always"
          {{ if .Values.first }}
          first: "on"
          {{ end }}
          {{ if .Values.second }}
          second: "on"
          {{ end }}
        """),
    )
    configure(monkeypatch, max_proof_bytes=1)
    with pytest.raises(ValueError, match="max_proof_bytes=1"):
        snapshot(tmp_path)
    configure(monkeypatch, max_output_nodes=2)
    assert output_profile([{"a": 1}])["nodes"] == 2
    with pytest.raises(ValueError, match="max_output_nodes=2"):
        output_profile([{"a": {"b": 1}}])
    configure(monkeypatch, max_complexity_cases=1, max_complexity_seconds=7)
    limited = measure(chart)
    assert limited["limits"] == {"max_cases": 1, "seconds": 7.0}
    assert limited["status"] == "unknown"
    configure(monkeypatch)
    complete = measure(chart)
    assert complete["status"] == "compiled-maximum", complete


@pytest.mark.parametrize("reader", ["context", "dependencies"])
def test_compressed_size_and_links_stay_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str) -> None:
    """
    Check packed size before reading members and retain link checks after raising limits.

    Args:
        tmp_path (Path): Source archive and extraction directory.
        monkeypatch (pytest.MonkeyPatch): Replace byte limits.
        reader (str): Compiler archive reader.

    Returns:
        None: Packed bytes and unsafe links cannot bypass either reader's protections.
    """
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as bundle:
        member = tarfile.TarInfo("chart/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../outside"
        bundle.addfile(member)
    packed = tmp_path / "chart.tgz"
    packed.write_bytes(data.getvalue())
    for limit, reason in ((1, "max_context_bytes"), (len(data.getvalue()), "links")):
        configure(monkeypatch, max_context_bytes=limit)
        with pytest.raises(ValueError, match=reason):
            if reader == "context":
                archive_files(io.BytesIO(data.getvalue()))
            else:
                unpack(packed, tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


def test_version_budget_precedes_native_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reject oversized version input before invoking Helm and admit the exact configured boundary.

    Args:
        tmp_path (Path): Fake executable used only for identity checks.
        monkeypatch (pytest.MonkeyPatch): Capture native probe calls and policy settings.

    Returns:
        None: Only the comparison fitting its budget reaches the renderer probe.
    """
    binary = tmp_path / "helm"
    binary.touch()
    monkeypatch.setattr("hypothesis_helm.compiler.asts.renderer.shutil.which", lambda _: str(binary))
    calls: list[tuple[object, ...]] = []

    def probe(*args: object) -> bool:
        """
        Record a native comparison without invoking an external executable.

        Args:
            *args (object): Arguments forwarded by the renderer context.

        Returns:
            bool: Successful comparison for the supported input.
        """
        calls.append(args)
        return True

    monkeypatch.setattr("hypothesis_helm.compiler.asts.renderer.probe", probe)
    configure(monkeypatch, max_version_chars=7)
    with pytest.raises(Unavailable, match="max_version_chars=7"):
        RendererContext(tmp_path).semver_compare(">=1", "1.2.3")
    assert calls == []
    configure(monkeypatch, max_version_chars=8)
    assert RendererContext(tmp_path).semver_compare(">=1", "1.2.3")
    assert len(calls) == 1


def test_tpl_discovery_depth_and_source_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Apply separate nesting and UTF-8 source budgets before parsing dynamic templates.

    Args:
        tmp_path (Path): Chart with two nested tpl calls.
        monkeypatch (pytest.MonkeyPatch): Change both discovery budgets.

    Returns:
        None: Raising limits discovers the leaf; low limits preserve diagnostics.
    """
    chart = fixture_chart(tmp_path, "{{ tpl .Values.outer . }}")
    (chart.path / "values.yaml").write_text(yamlio.dump({"outer": "{{ tpl .Values.inner . }}", "inner": "{{ .Values.leaf }}"}))
    for settings, blocked in (({"max_tpl_depth": 1}, True), ({"max_template_bytes": 1}, True), ({"max_tpl_depth": 2}, False)):
        configure(monkeypatch, **settings)
        refs, diagnostics = discover(chart.path)
        assert (("leaf",) not in [ref.path for ref in refs]) is blocked
        if blocked:
            assert next(iter(settings)) in str(diagnostics)
        else:
            assert not any("exceeds compiler" in diagnostic.message for diagnostic in diagnostics)
