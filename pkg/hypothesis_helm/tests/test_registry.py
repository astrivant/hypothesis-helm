"""
Helm package sources, authenticated indexes, extraction, and partial scan reporting.
"""

import io
import json
import shutil
import subprocess
import tarfile
import threading
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.registry import HelmTransport, prepare_helm_source, unpack_chart
from hypothesis_helm.cli import main


def chart_archive(name: str, version: str) -> bytes:
    """
    Build a valid tiny package without depending on external executables.

    Args:
        name (str): Chart basename.
        version (str): Semantic version.

    Returns:
        bytes: Compressed chart with a finite Boolean values schema.
    """
    files = {
        "Chart.yaml": dedent(f"""
            apiVersion: v2
            name: {name}
            version: {version}
        """),
        "values.yaml": "enabled: true\n",
        "values.schema.json": json.dumps({"type": "object", "properties": {"enabled": {"type": "boolean"}}, "additionalProperties": False}),
        "templates/config.yaml": dedent("""
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: demo
            data:
              enabled: {{ .Values.enabled | quote }}
        """),
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, content in files.items():
            member = tarfile.TarInfo(f"{name}/{path}")
            data = content.encode()
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


@pytest.mark.parametrize("failure", ["none", "download", "timeout", "interrupt", "index", "no-match", "wrong-version"])
def test_helm_source_partial_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    """
    Preserve successful downloads and account for unavailable charts and deadlines.

    Args:
        tmp_path (Path): Retained report directory.
        monkeypatch (pytest.MonkeyPatch): Replace Helm transport and property execution.
        capsys (pytest.CaptureFixture[str]): Capture the aggregate report.
        failure (str): Failure boundary to exercise.

    Returns:
        None: Incomplete acquisition never becomes an empty successful scan.
    """
    roots: list[Path] = []

    def run(transport: HelmTransport, command: list[str]) -> subprocess.CompletedProcess[str]:
        """
        Serve two indexed packages and an unrelated search match.

        Args:
            transport (HelmTransport): Isolated cache owner.
            command (list[str]): Complete Helm command.

        Returns:
            subprocess.CompletedProcess[str]: Native-shaped Helm response.
        """
        roots.append(Path(transport.environment["HELM_REPOSITORY_CACHE"]).parent)
        if command[1:3] == ["repo", "list"]:
            return subprocess.CompletedProcess(command, 0, '[{"name": "private", "url": "https://example.test"}]', "")
        if command[1:3] == ["repo", "update"]:
            return subprocess.CompletedProcess(command, int(failure == "index"), "", "index rejected" if failure == "index" else "")
        if command[1:3] == ["search", "repo"]:
            entries = [
                {"name": f"{repo}/{name}", "version": "1.0.0"} for repo, name in [("private", "a"), ("private", "b"), ("other", "c")]
            ]
            return subprocess.CompletedProcess(command, 0, json.dumps([] if failure == "no-match" else entries), "")
        assert command[1] == "pull"
        name = command[2].split("/")[-1]
        if name == "b":
            if failure == "download":
                return subprocess.CompletedProcess(command, 1, "", "rejected https://user:secret@example.test/b.tgz")
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 1)
            if failure == "interrupt":
                raise KeyboardInterrupt()
        destination = Path(command[-1])
        (destination / f"{name}.tgz").write_bytes(chart_archive(name, "2.0.0" if failure == "wrong-version" else "1.0.0"))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(HelmTransport, "run", run)
    monkeypatch.setattr("hypothesis_helm.charts.scan.exercise_chart", lambda *args: {"status": "passed", "attempts": 2})
    code = main(
        [
            "scan",
            "private",
            "--helm",
            "/usr/bin/true",
            "--no-build-dependencies",
            "--artifact-dir",
            str(tmp_path),
            "--report",
            str(tmp_path / "report"),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == {"none": 0, "download": 2, "timeout": 124, "interrupt": 130, "index": 1, "no-match": 1, "wrong-version": 2}[failure]
    assert report["charts_discovered"] == (0 if failure in {"index", "no-match"} else 2)
    assert report["source"]["inventory_complete"] is (failure not in {"index", "no-match"})
    if failure in {"none", "download"}:
        assert report["charts"][0]["status"] == "passed"
        assert len(report["charts"][0]["package"]["sha256"]) == 64
        assert "Package: private/a | Version: 1.0.0" in (tmp_path / "report.md").read_text()
    if failure == "download":
        assert report["charts"][1]["status"] == "download-failed"
        assert report["charts"][1]["result"] == "N/A"
        assert "secret" not in json.dumps(report)
    if failure in {"timeout", "interrupt"}:
        assert report["unstarted_charts"] == 2
        assert not report["discovery_complete"]
    if failure == "wrong-version":
        assert report["counts"] == {"download-failed": 2}
    assert roots and all(not root.exists() for root in roots)
    assert (tmp_path / "report.pdf").is_file()


@pytest.mark.parametrize(
    "location",
    ["https://user:secret@example.test/index.yaml", "https://example.test/index.yaml?token=secret", "oci://user:secret@example.test/demo"],
)
def test_helm_source_credentials_in_url(location: str) -> None:
    """
    Keep credentials in Helm configuration rather than retained source identities.

    Args:
        location (str): Credential-bearing source URL.

    Returns:
        None: URL validation stops before invoking Helm or creating a checkout.
    """
    with ExitStack() as scope, pytest.raises(ValueError, match="credentials"):
        prepare_helm_source(location, scope, helm="not-invoked", timeout=30, deadline=None)


def test_local_source_precedence(tmp_path: Path) -> None:
    """
    Keep existing local paths usable without contacting Helm repositories.

    Args:
        tmp_path (Path): Existing local chart tree.

    Returns:
        None: Local and Git sources fall through to the original scanner.
    """
    with ExitStack() as scope:
        assert prepare_helm_source(str(tmp_path), scope, helm="not-invoked", timeout=30, deadline=None) is None
        assert prepare_helm_source("https://example.test/charts.git", scope, helm="not-invoked", timeout=30, deadline=None) is None


@pytest.mark.parametrize("entry", ["../escaped", "/escaped", "demo/../../escaped", "other/Chart.yaml", "symlink"])
def test_unsafe_chart_archive(tmp_path: Path, entry: str) -> None:
    """
    Reject traversal, unexpected roots, and links before extraction.

    Args:
        tmp_path (Path): Isolated extraction root.
        entry (str): Unsafe archive member.

    Returns:
        None: No package file is extracted on rejection.
    """
    archive = tmp_path / "unsafe.tgz"
    with tarfile.open(archive, "w:gz") as package:
        member = tarfile.TarInfo("demo/link" if entry == "symlink" else entry)
        if entry == "symlink":
            member.type = tarfile.SYMTYPE
            member.linkname = "../../escaped"
        package.addfile(member)
    with pytest.raises(ValueError, match="unsafe"):
        unpack_chart(archive, tmp_path / "unpacked", "demo", "1.0.0")
    assert not (tmp_path / "unpacked").exists()


def test_oci_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Let Helm resolve an OCI version using the inherited registry login configuration.

    Args:
        tmp_path (Path): Credential configuration location.
        monkeypatch (pytest.MonkeyPatch): Replace only Helm pull.

    Returns:
        None: Version, package checksum, and registry configuration are retained correctly.
    """
    monkeypatch.setenv("HELM_REGISTRY_CONFIG", str(tmp_path / "registry.json"))

    def pull(transport: HelmTransport, command: list[str]) -> subprocess.CompletedProcess[str]:
        """
        Return an OCI chart selected by a semantic version constraint.

        Args:
            transport (HelmTransport): Source command environment.
            command (list[str]): Helm pull invocation.

        Returns:
            subprocess.CompletedProcess[str]: Successful download result.
        """
        assert command[1:5] == ["pull", "oci://example.test/charts/demo", "--version", "^1.0.0"]
        assert transport.environment["HELM_REGISTRY_CONFIG"] == str(tmp_path / "registry.json")
        (Path(command[-1]) / "demo.tgz").write_bytes(chart_archive("demo", "1.2.0"))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(HelmTransport, "run", pull)
    with ExitStack() as scope:
        source = prepare_helm_source("oci://example.test/charts/demo", scope, helm="helm", timeout=30, deadline=None, version="^1.0.0")
        assert source is not None and source.status == "ready"
        assert source.packages[0]["version"] == "1.2.0"
        assert (source.root / "demo" / "Chart.yaml").is_file()
    assert not source.root.exists()


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["authenticated", "single", "index", "base"])
def test_real_helm_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str) -> None:
    """
    Exercise native Helm authentication, version selection, downloading, and chart tests.

    Args:
        tmp_path (Path): Private Helm configuration and test artifacts.
        monkeypatch (pytest.MonkeyPatch): Isolate Helm's persistent state.
        capsys (pytest.CaptureFixture[str]): Capture scan results.
        mode (str): Registered repository or public index spelling.

    Returns:
        None: The scanner uses existing authentication without modifying shared indexes.
    """
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm required")
    for key, directory in {
        "HELM_REPOSITORY_CONFIG": "repositories.yaml",
        "HELM_REGISTRY_CONFIG": "registry.json",
        "HELM_REPOSITORY_CACHE": "shared-indexes",
        "HELM_CONTENT_CACHE": "shared-content",
        "HELM_CACHE_HOME": "cache",
        "HELM_PLUGINS": "plugins",
    }.items():
        monkeypatch.setenv(key, str(tmp_path / directory))
    archive_a = chart_archive("a", "1.0.0")
    archive_new = chart_archive("a", "2.0.0")
    archive_b = chart_archive("b", "1.0.0")
    index = {
        "apiVersion": "v1",
        "entries": {
            "a": [
                {"apiVersion": "v2", "name": "a", "version": "2.0.0", "urls": ["a-2.0.0.tgz"]},
                {"apiVersion": "v2", "name": "a", "version": "1.0.0", "urls": ["a-1.0.0.tgz"]},
            ],
            "b": [{"apiVersion": "v2", "name": "b", "version": "1.0.0", "urls": ["b-1.0.0.tgz"]}],
        },
    }
    requests: list[str] = []
    assets = {"/index.yaml": json.dumps(index).encode(), "/a-1.0.0.tgz": archive_a, "/a-2.0.0.tgz": archive_new, "/b-1.0.0.tgz": archive_b}

    class RepositoryHandler(BaseHTTPRequestHandler):
        """
        Serve a public or HTTP Basic authenticated chart repository on loopback.
        """

        def do_GET(self) -> None:
            """
            Require configured credentials for both index and package requests.

            Returns:
                None: Respond with the requested package or an authentication failure.
            """
            if mode in {"authenticated", "single"} and self.headers.get("Authorization") != "Basic dXNlcjpwYXNz":
                self.send_response(401)
                self.end_headers()
                return
            requests.append(self.path)
            self.send_response(200 if self.path in assets else 404)
            self.end_headers()
            self.wfile.write(assets.get(self.path, b"missing"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), RepositoryHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        if mode in {"authenticated", "single"}:
            subprocess.run(
                [helm, "repo", "add", "private", url, "--username", "user", "--password", "pass"], check=True, capture_output=True
            )
        config = tmp_path / "repositories.yaml"
        before_config = config.read_bytes() if config.exists() else None
        before_cache = {path.name: path.read_bytes() for path in (tmp_path / "shared-indexes").glob("*")}
        source = {"authenticated": "private", "single": "private/a", "index": url + "/index.yaml", "base": url}[mode]
        options = {"authenticated": [], "single": ["--chart-version", "1.0.0"], "index": [], "base": ["--helm-repository"]}[mode]
        assert (
            main(
                [
                    "scan",
                    source,
                    "--helm",
                    helm,
                    "--filter",
                    "--max-examples",
                    "2",
                    "--no-build-dependencies",
                    "--artifact-dir",
                    str(tmp_path / "reports"),
                    *options,
                ]
            )
            == 0
        )
        report = json.loads(capsys.readouterr().out)
        assert report["counts"] == {"passed": 1 if mode == "single" else 2}
        assert report["source"]["packages"][0]["version"] == ("1.0.0" if mode == "single" else "2.0.0")
        assert (config.read_bytes() if config.exists() else None) == before_config
        assert {path.name: path.read_bytes() for path in (tmp_path / "shared-indexes").glob("*")} == before_cache
        assert "/a-1.0.0.tgz" in requests if mode == "single" else "/a-2.0.0.tgz" in requests
        assert "password" not in json.dumps(report)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
