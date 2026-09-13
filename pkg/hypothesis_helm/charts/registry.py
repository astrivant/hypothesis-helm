"""
Acquire indexed Helm repositories and OCI charts using Helm's existing credentials.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from attrs import define
from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.repository import RepositorySource
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.schemas.contracts import mapping, sequence, text

LOGGER = logging.getLogger(__name__)
CHART_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


@define
class HelmTransport:
    """
    Bound Helm source commands and isolate their index and content caches.

    Attributes:
        environment (dict[str, str]): Inherited credentials and private cache locations.
        stop (float): Monotonic deadline for source preparation.
    """

    environment: dict[str, str]
    stop: float

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """
        Execute an explicit Helm command and reap its process group on cancellation.

        Args:
            command (list[str]): Complete Helm invocation without shell interpolation.

        Returns:
            subprocess.CompletedProcess[str]: Captured output and exit status.
        """
        remaining = self.stop - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, 0)
        return Processes().run(command, env=self.environment, capture_output=True, timeout=remaining)


def unpack_chart(archive: Path, destination: Path, name: str, version: str | None) -> tuple[str, str]:
    """
    Extract a regular-file chart package and verify its name and selected version.

    Args:
        archive (Path): Downloaded chart archive.
        destination (Path): Isolated extraction directory.
        name (str): Expected chart basename.
        version (str | None): Exact indexed version, or None for an OCI constraint.

    Returns:
        tuple[str, str]: Resolved chart version and package SHA-256.
    """
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            parts = Path(member.name).parts
            if not parts or parts[0] != name or ".." in parts or not (member.isfile() or member.isdir()):
                raise ValueError("Chart archive contains an unsafe path or non-regular entry")
        package.extractall(destination, filter="data")
    metadata = mapping(yamlio.load((destination / name / "Chart.yaml").read_text()))
    resolved = text(metadata.get("version"))
    if metadata.get("name") != name or (version is not None and resolved != version):
        raise ValueError("Downloaded Chart.yaml does not match the requested chart name/version")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return resolved, digest


def prepare_helm_source(
    location: str,
    scope: ExitStack,
    *,
    helm: str,
    timeout: float,
    deadline: float | None,
    force: bool = False,
    version: str | None = None,
) -> RepositorySource | None:
    """
    Download selected chart releases without changing the user's Helm repositories.

    Args:
        location (str): Configured repo[/chart], public index URL, or OCI chart reference.
        scope (ExitStack): Owns temporary downloads until reports have been written.
        helm (str): Helm executable.
        timeout (float): Total source preparation budget in seconds.
        deadline (float | None): Optional earlier scan deadline.
        force (bool): Treat an HTTP(S) base URL or ambiguous path as a Helm repository.
        version (str | None): Optional version or semantic version constraint.

    Returns:
        RepositorySource | None: Prepared Helm source, or None for a local/Git source.
    """
    parsed = urlsplit(location)
    indexed = parsed.scheme in {"http", "https"} and (force or parsed.path.endswith("/index.yaml"))
    oci = parsed.scheme == "oci"
    if not force and not indexed and not oci:
        if Path(location).expanduser().exists() or not re.fullmatch(r"[\w.-]+(?:/[\w.-]+)?", location):
            return None
    if parsed.scheme:
        if not indexed and not oci:
            raise ValueError("Helm repository URLs must use HTTP(S); OCI sources must identify one chart")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use Helm source URLs without embedded credentials, query strings, or fragments")
    elif not re.fullmatch(r"[\w.-]+(?:/[\w.-]+)?", location):
        raise ValueError("Use a configured Helm repo or repo/chart reference")
    if any(ord(char) < 32 for char in location):
        raise ValueError("Helm source cannot contain control characters")

    temporary = Path(scope.enter_context(tempfile.TemporaryDirectory(prefix="hypothesis-helm-packages-")))
    root = temporary / "charts"
    root.mkdir()
    environment = dict(
        os.environ,
        HELM_REPOSITORY_CACHE=str(temporary / "indexes"),
        HELM_CACHE_HOME=str(temporary / "cache"),
        HELM_CONTENT_CACHE=str(temporary / "content"),
    )
    transport = HelmTransport(environment, min(time.monotonic() + timeout, deadline if deadline is not None else float("inf")))
    basename = parsed.path.removesuffix("/index.yaml").rstrip("/").rsplit("/", 1)[-1] or parsed.hostname or location
    source = RepositorySource(location, root, re.sub(r"[^A-Za-z0-9._-]", "_", basename), True, kind="helm")
    requested = location.split("/", 1)[1] if not parsed.scheme and "/" in location else None
    try:
        if oci:
            name = parsed.path.rstrip("/").rsplit("/", 1)[-1]
            if not parsed.path or not CHART_NAME.fullmatch(name):
                raise ValueError("OCI source must identify a chart; select its version with --chart-version")
            source.packages = [{"chart": name, "reference": location, "requested_version": version or "", "status": "pending"}]
        else:
            if indexed:
                repository_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.removesuffix("/index.yaml").rstrip("/"), "", ""))
                alias = "hypothesis-source"
                environment["HELM_REPOSITORY_CONFIG"] = str(temporary / "repositories.yaml")
                added = transport.run([helm, "repo", "add", alias, repository_url])
                if added.returncode:
                    raise ValueError(added.stderr or added.stdout)
            else:
                alias = location.split("/", 1)[0]
                listed = transport.run([helm, "repo", "list", "--output", "json"])
                if listed.returncode:
                    if not force:
                        return None
                    raise ValueError(listed.stderr or listed.stdout)
                repositories = sequence(json.loads(listed.stdout))
                configured = next((mapping(item) for item in repositories if mapping(item).get("name") == alias), None)
                if configured is None:
                    if not force:
                        return None
                    raise ValueError(f"Helm repository is not configured: {alias}")
                repository_url = text(configured.get("url"))
                updated = transport.run([helm, "repo", "update", alias])
                if updated.returncode:
                    raise ValueError(updated.stderr or updated.stdout)
            searched = transport.run([helm, "search", "repo", alias + "/", "--output", "json", "--version", version or ">=0.0.0"])
            if searched.returncode:
                raise ValueError(searched.stderr or searched.stdout)
            for item in sequence(json.loads(searched.stdout)):
                entry = mapping(item)
                reference = text(entry.get("name"))
                if not reference.startswith(alias + "/"):
                    continue
                name = reference.removeprefix(alias + "/")
                if not CHART_NAME.fullmatch(name) or (requested is not None and name != requested):
                    continue
                resolved = text(entry.get("version"))
                source.packages.append(
                    {
                        "chart": name,
                        "reference": reference,
                        "repository": repository_url,
                        "requested_version": resolved,
                        "status": "pending",
                    }
                )
            source.packages.sort(key=lambda item: str(item["chart"]))
            if not source.packages:
                raise ValueError("No chart releases match this Helm source and version constraint")
        source.inventory_complete = True
        for index, package in enumerate(source.packages):
            name = str(package["chart"])
            staging = temporary / f"download-{index}"
            staging.mkdir()
            LOGGER.info("Downloading chart %d/%d: %s", index + 1, len(source.packages), name)
            try:
                pulled = transport.run(
                    [helm, "pull", str(package["reference"]), "--version", str(package["requested_version"]), "--destination", str(staging)]
                )
                if pulled.returncode:
                    raise ValueError(pulled.stderr or pulled.stdout)
                archives = list(staging.glob("*.tgz"))
                if len(archives) != 1:
                    raise ValueError("Helm pull did not produce exactly one chart archive")
                resolved, digest = unpack_chart(archives[0], staging / "unpacked", name, None if oci else str(package["requested_version"]))
                shutil.move(str(staging / "unpacked" / name), root / name)
                package.update(status="downloaded", version=resolved, sha256=digest)
                if time.monotonic() >= transport.stop:
                    raise subprocess.TimeoutExpired("Helm package preparation", timeout)
            except (OSError, ValueError, EOFError, tarfile.TarError, YAMLError) as exc:
                package.update(status="download-failed", result="N/A", error=str(exc))
    except subprocess.TimeoutExpired:
        source.status = "scan-timeout" if deadline is not None and time.monotonic() >= deadline else "source-timeout"
        source.diagnostic = "Helm source preparation deadline reached"
    except KeyboardInterrupt:
        source.status = "interrupted"
        source.diagnostic = "Helm source preparation interrupted"
    except (OSError, ValueError) as exc:
        source.status = "source-failed"
        source.diagnostic = str(exc)
    # Helm may echo an index-provided URL; never retain URL userinfo in reports.
    source.diagnostic = re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", source.diagnostic)
    for package in source.packages:
        for key in ("error", "repository"):
            if key in package:
                package[key] = re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", str(package[key]))
    return source
