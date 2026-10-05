"""
Transport repository evidence with shared, lossless compressed analysis payloads.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import zlib

from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("compact_report", "expand_inventory", "merge_payloads")


def _store(value: dict[str, object], payloads: dict[str, object]) -> str:
    """
    Store one canonical JSON object under its content checksum.

    Args:
        value (dict[str, object]): Analysis or work inventory retained without alteration.
        payloads (dict[str, object]): Shared payload table owned by the compact report.

    Returns:
        str: SHA-256 reference to a deterministic gzip and base64 payload.
    """
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    identity = hashlib.sha256(raw).hexdigest()
    if identity not in payloads:
        payloads[identity] = base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")
    return identity


def _compact(record: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    """
    Copy report records while leaving user values, findings and diagnostics intact.

    Args:
        record (dict[str, object]): Repository, chart, baseline or phase record.
        payloads (dict[str, object]): Destination for repeated analysis and shared inventories.

    Returns:
        dict[str, object]: Record with compressed references only at known metadata boundaries.
    """
    result = dict(record)
    for key in ("input_domains", "input_inventory"):
        if key in result:
            result[key] = {"aggregation_ref": _store(mapping(result[key]), payloads)}
    if "work_partition" in result:
        work = dict(mapping(result["work_partition"]))
        inventory = {key: work.pop(key) for key in ("units", "initial")}
        work["inventory_ref"] = _store(inventory, payloads)
        result["work_partition"] = work
    for key in ("charts", "phases"):
        if key in result:
            result[key] = [_compact(mapping(item), payloads) for item in sequence(result[key])]
    if "baseline" in result:
        result["baseline"] = _compact(mapping(result["baseline"]), payloads)
    return result


def compact_report(report: dict[str, object]) -> dict[str, object]:
    """
    Produce standalone aggregation evidence without mutating the raw report.

    Args:
        report (dict[str, object]): Completed or interrupted recursive shard report.

    Returns:
        dict[str, object]: Ordinary findings and partition evidence plus lossless JSON payloads.
    """
    payloads: dict[str, object] = {}
    result = _compact(report, payloads)
    result["aggregation_data"] = payloads
    return result


def merge_payloads(payloads: dict[str, object], shared: dict[str, object]) -> None:
    """
    Intern identical encoded payloads across shards without accepting conflicting content.

    Args:
        payloads (dict[str, object]): Table updated to reuse the shared encoded strings.
        shared (dict[str, object]): Common content-addressed payload storage.

    Returns:
        None: Equal payloads share memory; conflicting checksum entries raise ValueError.
    """
    for identity, payload in payloads.items():
        if not isinstance(payload, str) or (identity in shared and shared[identity] != payload):
            raise ValueError("Conflicting or invalid aggregation payload")
        payloads[identity] = shared.setdefault(identity, payload)


def expand_inventory(work: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    """
    Restore one inventory for the existing ownership and completion checks.

    Args:
        work (dict[str, object]): Raw partition evidence or a partition with an inventory reference.
        payloads (dict[str, object]): Shared gzip and base64 JSON objects keyed by SHA-256.

    Returns:
        dict[str, object]: Complete partition evidence; missing or corrupt payloads raise ValueError.
    """
    if "inventory_ref" not in work:
        return work
    identity = str(work["inventory_ref"])
    payload = payloads.get(identity)
    if not isinstance(payload, str) or "units" in work or "initial" in work:
        raise ValueError("Missing or ambiguous aggregation inventory")
    try:
        raw = gzip.decompress(base64.b64decode(payload, validate=True))
    except (ValueError, OSError, EOFError, zlib.error) as exc:
        raise ValueError("Invalid compressed aggregation inventory") from exc
    if hashlib.sha256(raw).hexdigest() != identity:
        raise ValueError("Aggregation inventory checksum mismatch")
    inventory = mapping(json.loads(raw))
    if inventory.keys() != {"units", "initial"}:
        raise ValueError("Invalid aggregation inventory fields")
    result = dict(work)
    del result["inventory_ref"]
    result.update(inventory)
    return result
