"""
Verify templates.
"""

from pathlib import Path

from hypothesis_helm.charts.templates import Diagnostic, Reference, discover, parse


def scan(tmp_path: Path, text: str) -> tuple[list[Reference], list[Diagnostic]]:
    """
    Check scan.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.
        text (str): YAML or template text to process.

    Returns:
        tuple[list[Reference], list[Diagnostic]]: Result of the documented operation.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "test.yaml").write_text(text)
    return discover(tmp_path)


def test_scopes_aliases_and_lookups(tmp_path: Path) -> None:
    """
    Verify scopes aliases and lookups.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    refs, warnings = scan(
        tmp_path,
        """
{{ $root := . }}{{ $v := .Values }}
{{ with .Values.image }}{{ .tag }}{{ $root.Values.enabled }}{{ end }}
{{ range $item := .Values.items }}{{ .name }}{{ $item.port }}{{ end }}
{{ $v.hidden | default "fallback" }}
{{ index .Values "hyphen-key" "child" }}
{{ (index .Values "other").nested }}
{{ dig "nested" "key" "default" .Values }}
""".removeprefix("\n").removesuffix("\n"),
    )
    paths = {r.path for r in refs}
    assert {
        ("image", "tag"),
        ("enabled",),
        ("items", "*", "name"),
        ("items", "*", "port"),
        ("hidden",),
        ("hyphen-key", "child"),
        ("other", "nested"),
        ("nested", "key"),
    } <= paths
    assert any(r.path == ("hidden",) and r.fallback for r in refs)
    assert not warnings


def test_comments_strings_and_delimiters(tmp_path: Path) -> None:
    """
    Verify comments strings and delimiters.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    refs, warnings = scan(tmp_path, '{{/* .Values.fake }} */}}{{ "}} .Values.fake" }}{{ .Values.real }}')
    assert {r.path for r in refs} == {("real",)}
    assert not warnings


def test_unresolved_is_visible(tmp_path: Path) -> None:
    """
    Verify unresolved is visible.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    _, warnings = scan(
        tmp_path,
        '{{ index .Values $key }}{{ tpl .Values.content . }}{{ define "x" }}{{ .thing }}{{ end }}',
    )
    assert any("dynamic key" in w.message for w in warnings)
    assert any("named template" in w.message for w in warnings)
    assert any("unresolved dot" in w.message for w in warnings)


def test_invalid_blocks() -> None:
    """
    Verify invalid blocks.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    import pytest

    for source in ("{{ if .Values.x }}", "{{ end }}", '{{ "unterminated }}'):
        with pytest.raises(ValueError):
            parse(source)


def test_dig_pipeline_and_range_key(tmp_path: Path) -> None:
    """
    Verify dig pipeline and range key.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    refs, _ = scan(
        tmp_path,
        '{{ dig "nested" "key" "fallback" .Values | quote }}{{ range '
        "$key, $value := .Values.map }}{{ $key.name }}{{ $value.port "
        "}}{{ end }}",
    )
    paths = {r.path for r in refs}
    assert ("nested", "key") in paths
    assert ("map", "*", "port") in paths
    assert ("map", "*", "name") not in paths


def test_tpl_sources_and_contexts(tmp_path: Path) -> None:
    """
    Discover nested template references from values, literals, and chart files.

    Args:
        tmp_path (Path): Temporary chart directory.

    Returns:
        None: Resolved tpl inputs expose nested paths without dynamic diagnostics.
    """
    from hypothesis_helm.charts import yamlio

    (tmp_path / "values.yaml").write_text(
        yamlio.dump(
            {
                "content": "{{ tpl .Values.inner . }}",
                "inner": '{{ .Values.hidden | default "fallback" }}',
                "config": {"entry": "{{ $.Values.serialized }}"},
            }
        )
    )
    (tmp_path / "app.conf").write_text("{{ .Values.fromFile }}")
    refs, warnings = scan(
        tmp_path,
        """
{{ $v := .Values }}{{ tpl $v.content $ | quote }}
{{ tpl `{{ if true }}{{ .child }} {{ $.other }}{{ end }}` .Values.nested }}
{{ tpl (.Files.Get "app.conf") . }}
{{ tpl (toYaml .Values.config) . }}
{{ tpl (toJson .Values.config) . }}
{{ tpl (index .Values "inner") . }}
""",
    )
    paths = {ref.path for ref in refs}
    assert {
        ("hidden",),
        ("nested", "child"),
        ("nested", "other"),
        ("fromFile",),
        ("serialized",),
    } <= paths
    assert any(ref.path == ("hidden",) and ref.fallback for ref in refs)
    assert any("(tpl)" in ref.file for ref in refs if ref.path == ("fromFile",))
    assert any("(tpl)" in ref.file for ref in refs if ref.path == ("nested", "child"))
    assert not warnings


def test_tpl_dynamic_recursive_and_invalid(tmp_path: Path) -> None:
    """
    Surface unresolved or recursive tpl calls without assuming their context.

    Args:
        tmp_path (Path): Temporary chart directory.

    Returns:
        None: Recursion terminates and unsupported inputs remain visible.
    """
    from hypothesis_helm.charts import yamlio

    (tmp_path / "values.yaml").write_text(
        yamlio.dump(
            {
                "loop": "{{ tpl .Values.loop . }}",
            }
        )
    )
    refs, warnings = scan(
        tmp_path,
        """
{{ tpl .Values.loop . }}
{{ tpl .Values.absent . }}
{{ tpl `{{ .Values.wrong }}` (dict "Values" .Values) }}
{{ tpl `{{ if .Values.bad }}` . }}
{{ tpl (.Files.Get "../outside") . }}
{{ tpl (.Files.Get "") . }}
{{ tpl (printf "%s" .Values.dynamic) . }}
""",
    )
    messages = [warning.message for warning in warnings]
    assert any("recursive tpl" in message for message in messages)
    assert any("absent" in message for message in messages)
    assert any("context is dynamic" in message for message in messages)
    assert any("unclosed block" in message for message in messages)
    assert any("outside chart" in message for message in messages)
    assert any("source is dynamic" in message for message in messages)
    assert ("wrong",) not in {ref.path for ref in refs}


def test_tpl_coalescing_and_helm_render(tmp_path: Path) -> None:
    """
    Coalesce an undocumented tpl lever and render its override through real Helm.

    Args:
        tmp_path (Path): Temporary complete chart directory.

    Returns:
        None: Hidden paths enter the model and Helm evaluates nested template strings.
    """
    import shutil

    import pytest

    from hypothesis_helm.charts import yamlio
    from hypothesis_helm.charts.generate import coalesce
    from hypothesis_helm.charts.runner import Chart, render
    from hypothesis_helm.schemas.contracts import mapping

    if shutil.which("helm") is None:
        pytest.skip("Helm is required for tpl rendering")
    (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: tpl-example\nversion: 0.1.0\n")
    (tmp_path / "values.schema.json").write_text('{"type":"object"}')
    (tmp_path / "values.yaml").write_text(
        yamlio.dump(
            {
                "content": "{{ tpl .Values.inner . }}",
                "inner": '{{ .Values.hidden | default "fallback" }}',
            }
        )
    )
    scan(
        tmp_path,
        """
apiVersion: v1
kind: ConfigMap
metadata:
  name: tpl-example
data:
  result: {{ tpl .Values.content . | quote }}
""".removeprefix("\n"),
    )
    chart = Chart.load(tmp_path)
    model = coalesce(chart)
    assert ("hidden",) in {entry.path for entry in model.paths}
    assert "hidden" in model.values
    assert mapping(render(chart, {})[0]["data"])["result"] == "fallback"
    assert mapping(render(chart, {"hidden": "generated"})[0]["data"])["result"] == "generated"
