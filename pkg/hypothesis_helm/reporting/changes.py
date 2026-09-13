"""
Compare JSON documents and replay verified DeepDiff deltas without pickle payloads.
"""

import copy
import hashlib
import json
from pathlib import Path

from deepdiff import DeepDiff, Delta
from deepdiff.delta import DeltaError

from hypothesis_helm.charts import yamlio
from hypothesis_helm.reporting.reproductions import value_path
from hypothesis_helm.schemas.contracts import mapping

TYPES = {kind.__name__: kind for kind in (type(None), bool, int, float, str, list, dict)}


def normalize(value: object) -> object:
    """
    Remove YAML presentation types while retaining JSON scalar types and list order.

    Args:
        value (object): JSON-compatible values or parsed manifests.

    Returns:
        object: Detached plain JSON data.
    """
    return json.loads(json.dumps(value, allow_nan=False))


def digest(value: object) -> str:
    """
    Identify the entire document, including unchanged fields, for replay verification.

    Args:
        value (object): JSON-compatible baseline or result.

    Returns:
        str: SHA-256 of canonical, type-preserving JSON.
    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def compare(before: object, after: object) -> dict[str, object]:
    """
    Record ordered, type-sensitive changes and a replayable JSON delta.

    Args:
        before (object): Baseline document.
        after (object): Observed document from the same test context.

    Returns:
        dict[str, object]: Change paths, old/new values, identities, and a verified delta.
    """
    before, after = normalize(before), normalize(after)
    diff = DeepDiff(before, after, view="tree", verbose_level=2, threshold_to_diff_deeper=0, zip_ordered_iterables=True)
    changes = []
    for kind, nodes in sorted(diff.items()):
        for node in nodes:
            path = node.path(output_format="list")
            old_present, new_present = not kind.endswith("_added"), not kind.endswith("_removed")
            change = {"kind": kind, "path": value_path(path), "segments": path, "old_present": old_present, "new_present": new_present}
            if old_present:
                change["before"] = node.t1
            if new_present:
                change["after"] = node.t2
            changes.append(change)
    delta = copy.deepcopy(Delta(diff, bidirectional=True, always_include_values=True, raise_errors=True, log_errors=False).diff)
    # Only delta metadata contains Python types. User dictionaries are never decoded as types.
    for change in delta.get("type_changes", {}).values():
        for name in ("old_type", "new_type"):
            change[name] = change[name].__name__
    record = {
        "format": "deepdiff-json-v1",
        "baseline_sha256": digest(before),
        "result_sha256": digest(after),
        "changes": sorted(changes, key=lambda change: (str(change["path"]), str(change["kind"]))),
        "delta": normalize(delta),
    }
    try:
        replay(before, record)
    except (ValueError, DeltaError):
        # Some quoted keys cannot round-trip through DeepDiff's string paths, and
        # its numeric comparison equates signed zeros. Preserve exact JSON replay.
        record["representation"] = "whole-document replacement: field delta did not reproduce exact JSON"
        record["delta"] = {"values_changed": {"root": {"old_value": before, "new_value": after}}}
        record["changes"] = [
            {
                "kind": "values_changed",
                "path": "$",
                "segments": [],
                "old_present": True,
                "new_present": True,
                "before": before,
                "after": after,
            }
        ]
        replay(before, record)
    return record


def replay(baseline: object, record: dict[str, object]) -> object:
    """
    Apply a JSON delta only to its exact baseline and verify the complete result.

    Args:
        baseline (object): Original document, left unchanged.
        record (dict[str, object]): Saved change record.

    Returns:
        object: Reconstructed document with the recorded identity.
    """
    baseline = normalize(baseline)
    if record.get("format") != "deepdiff-json-v1":
        raise ValueError("unsupported change record format")
    if digest(baseline) != record.get("baseline_sha256"):
        raise ValueError("change record baseline checksum does not match")
    delta = copy.deepcopy(mapping(record["delta"]))
    for item in mapping(delta.get("type_changes", {})).values():
        change = mapping(item)
        for name in ("old_type", "new_type"):
            kind = change.get(name)
            if not isinstance(kind, str) or kind not in TYPES:
                raise ValueError("unsupported delta scalar or container type")
            change[name] = TYPES[kind]
    result = baseline + Delta(diff=delta, bidirectional=True, always_include_values=True, raise_errors=True, log_errors=False)
    if digest(result) != record.get("result_sha256"):
        raise ValueError("replayed result checksum does not match")
    return result


def replay_file(record: Path, baseline: Path | None, section: str, output: Path | None) -> None:
    """
    Reconstruct saved overrides, effective values, or manifests from a JSON artifact.

    Args:
        record (Path): Saved changes.json artifact.
        baseline (Path | None): JSON baseline; omitted only for overrides starting from an empty map.
        section (str): Comparison section to replay.
        output (Path | None): Destination JSON file, or standard output.

    Returns:
        None: Verified JSON is written after successful replay.
    """
    if baseline is None and section != "overrides":
        raise ValueError("--baseline is required for values and manifests")
    original = json.loads(baseline.read_text()) if baseline is not None else {}
    result = replay(original, mapping(mapping(json.loads(record.read_text()))[section]))
    encoded = yamlio.json_for_helm(result, indent=2) + "\n"
    if output is None:
        print(encoded, end="")
    else:
        output.write_text(encoded)
