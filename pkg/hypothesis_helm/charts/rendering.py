"""
Render Helm charts and validate complete manifest bundles.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from ruamel.yaml.error import YAMLError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.render_hashes import RenderHashes, process_hashes
from hypothesis_helm.reporting.output import emit_manifest
from hypothesis_helm.schemas.conformity import ENVIRONMENT, validate
from hypothesis_helm.schemas.contracts import (
    mapping,
    sequence,
)

LOGGER = logging.getLogger(__name__)


class RenderFailure(AssertionError):
    """
    A reproducible values input failed the rendering contract.

    Attributes:
        resources (list[object] | None): Parsed output available before a manifest validation failure.
    """

    resources: list[object] | None = None


def validate_resources(resources: Sequence[object]) -> None:
    """
    Check resource envelopes; callers can add Kubernetes or domain validation.

    Args:
        resources (Sequence[object]): Rendered Kubernetes resource documents.

    Returns:
        None: None. The operation completes through its documented side effects.
    """
    identities = set()
    for resource in resources:
        if not isinstance(resource, dict):
            raise RenderFailure("rendered document is not an object")
        for key in ("apiVersion", "kind"):
            if not isinstance(resource.get(key), str) or not resource[key]:
                raise RenderFailure(f"resource has no nonempty {key}")
        if resource["kind"] == "List":
            if not isinstance(resource.get("items"), list):
                raise RenderFailure("List resource has no items array")
            validate_resources(sequence(resource["items"]))
            continue
        metadata = resource.get("metadata")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str) or not metadata["name"]:
            raise RenderFailure("resource has no metadata.name")
        identity = (
            resource["apiVersion"],
            resource["kind"],
            metadata.get("namespace"),
            metadata["name"],
        )
        if identity in identities:
            raise RenderFailure(f"duplicate resource: {identity}")
        identities.add(identity)


def render(
    chart: Chart,
    values: dict[str, object],
    *,
    helm: str = "helm",
    timeout: float = 30.0,
    release: str = "hypothesis",
    namespace: str = "default",
    kube_version: str | None = None,
    hashes: RenderHashes | None = None,
    stream: bool = True,
) -> list[dict[str, object]]:
    """
    Render locally with Helm schema checks enabled and a subprocess deadline.

    Args:
        chart (Chart): Loaded chart and its schema and defaults.
        values (dict[str, object]): Values document used as the rendering baseline.
        helm (str): Helm executable used to render the chart.
        timeout (float): Maximum seconds allowed for each Helm invocation.
        release (str): Release name supplied to Helm.
        namespace (str): Release namespace supplied to Helm.
        kube_version (str | None): Optional Kubernetes capability version supplied to Helm.

        hashes (RenderHashes | None): Run index, or the current process index by default.
        stream (bool): Emit manifests to the configured output stream.

    Returns:
        list[dict[str, object]]: Result of the documented operation.
    """
    with tempfile.TemporaryDirectory(prefix="hypothesis-helm-") as directory:
        value_file = Path(directory) / "values.json"
        value_file.write_text(yamlio.json_for_helm(values), encoding="utf-8")
        command = [
            helm,
            "template",
            release,
            str(chart.path),
            "--namespace",
            namespace,
            "--values",
            str(value_file),
        ]
        if kube_version:
            command += ["--kube-version", kube_version]
        try:
            process = Processes().run(command, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RenderFailure(f"helm exceeded {timeout}s") from exc
        if process.returncode:
            raise RenderFailure(process.stderr.strip() or f"helm exited {process.returncode}")
        try:
            resources = [item for item in yamlio.load_all(process.stdout) if item is not None]
        except YAMLError as exc:
            raise RenderFailure(f"invalid rendered YAML: {exc}") from exc
    if stream:
        for resource in resources:
            emit_manifest(resource)

    def validate_bundle() -> None:
        """
        Validate the complete output before committing a successful cache entry.

        Returns:
            None: Manifest checks pass or their failure propagates.
        """
        validate_resources(resources)
        try:
            validate(process.stdout, timeout)
        except AssertionError as exc:
            raise RenderFailure(str(exc)) from exc

    context = json.dumps(
        {"resource_contract": 1, "conformity": os.environ.get(ENVIRONMENT), "timeout": timeout},
        sort_keys=True,
    )
    try:
        (hashes if hashes is not None else process_hashes()).check(resources, context, validate_bundle)
    except RenderFailure as exc:
        exc.resources = resources
        raise
    except (TypeError, ValueError) as exc:
        failure = RenderFailure(f"invalid rendered manifest: {exc}")
        failure.resources = resources
        raise failure from exc
    return [mapping(resource) for resource in resources]
