"""
Persist value-free YAML structure markers separately from property outcomes.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from attrs import frozen

from hypothesis_helm.charts import yamlio
from hypothesis_helm.execution.cache import seed_key
from hypothesis_helm.reporting.progress import format_path


def structure(value: object, ancestors: frozenset[int] = frozenset()) -> object:
    """
    Retain mapping keys and array positions while replacing scalar contents with null.

    Args:
        value (object): Source YAML value.
        ancestors (frozenset[int]): Container identities along the current traversal.

    Returns:
        object: Canonical JSON-compatible tree without scalar contents or types.
    """
    if not isinstance(value, dict | list):
        return None
    if id(value) in ancestors:
        raise ValueError("recursive YAML aliases cannot form a finite values structure")
    ancestors = ancestors | {id(value)}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("values structure requires string mapping keys")
        return {"object": {key: structure(value[key], ancestors) for key in sorted(value)}}
    return {"array": [structure(entry, ancestors) for entry in value]}


def paths(tree: object, prefix: tuple[str | int, ...] = ()) -> set[tuple[str | int, ...]]:
    """
    Extract concrete paths and reject malformed cached tree representations.

    Args:
        tree (object): Decoded structure marker.
        prefix (tuple[str | int, ...]): Current concrete path.

    Returns:
        set[tuple[str | int, ...]]: Named fields and indexed collection entries.
    """
    result = {prefix} if prefix else set()
    if tree is None:
        return result
    if not isinstance(tree, dict):
        raise ValueError("invalid cached values structure")
    if set(tree) == {"object"} and isinstance(tree["object"], dict):
        for key, child in tree["object"].items():
            if not isinstance(key, str):
                raise ValueError("invalid cached values structure key")
            result.update(paths(child, (*prefix, key)))
    elif set(tree) == {"array"} and isinstance(tree["array"], list):
        for index, child in enumerate(tree["array"]):
            result.update(paths(child, (*prefix, index)))
    else:
        raise ValueError("invalid cached values structure")
    return result


@frozen
class StructureMarker:
    """
    Hold a source structure and its comparison to the preceding run.

    Attributes:
        destination (Path): Seed-scoped marker file.
        source (Path): Original values file, or saved-suite snapshot when source is unknown.
        encoded (str): Base64-encoded canonical JSON structure.
        status (str): New, changed, unchanged, or invalid-cache.
        added (tuple[str, ...]): Paths absent from the preceding marker.
        removed (tuple[str, ...]): Paths no longer present.
    """

    destination: Path
    source: Path
    encoded: str
    status: str
    added: tuple[str, ...]
    removed: tuple[str, ...]

    def save(self) -> None:
        """
        Atomically persist only the encoded tree after a testing run.

        Returns:
            None: The new marker replaces the previous baseline.
        """
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.destination.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(self.encoded + "\n")
        temporary.replace(self.destination)

    def report(self) -> dict[str, object]:
        """
        Describe the structure comparison without embedding its cached payload.

        Returns:
            dict[str, object]: Marker location, source, status, and changed paths.
        """
        return {
            "marker": str(self.destination),
            "source": str(self.source),
            "status": self.status,
            "added_paths": list(self.added),
            "removed_paths": list(self.removed),
        }


def inspect_structure(directory: Path, cache_root: Path, seed: int, *, suite_location: Path | None = None) -> StructureMarker | None:
    """
    Compare original values with the previous seed-scoped tree without writing files.

    Args:
        directory (Path): Actual generated suite location.
        cache_root (Path): Root of the persistent result cache.
        seed (int): Hypothesis seed selecting the marker namespace.
        suite_location (Path | None): Logical suite location during a staged dry run.

    Returns:
        StructureMarker | None: Comparison, or none when a custom suite has no values file.
    """
    metadata = directory / "chart-source.json"
    if metadata.is_file():
        source = ((suite_location or directory) / json.loads(metadata.read_text())["chart"] / "values.yaml").resolve()
    else:
        source = ((suite_location or directory) / "values.coalesced.yaml").resolve()
    if not source.is_file():
        return None
    current = structure(yamlio.load(source.read_text()))
    payload = json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    relative_source = os.path.relpath(source, (suite_location or directory).resolve())
    identity = hashlib.sha256(relative_source.encode("utf-8")).hexdigest()
    destination = cache_root / seed_key(seed) / "structures" / f"{identity}.b64"
    previous_paths: set[tuple[str | int, ...]] = set()
    status = "new"
    if destination.exists():
        try:
            previous = json.loads(base64.b64decode(destination.read_text().strip(), validate=True))
            previous_paths = paths(previous)
            status = "unchanged" if previous == current else "changed"
        except (OSError, ValueError, RecursionError):
            status = "invalid-cache"
    current_paths = paths(current)
    return StructureMarker(
        destination,
        source,
        encoded,
        status,
        tuple(sorted(format_path(path) for path in current_paths - previous_paths)),
        tuple(sorted(format_path(path) for path in previous_paths - current_paths)),
    )
