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

__all__ = ("compact_report", "expand_inventory", "expand_record", "merge_payloads")


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
    merge_payloads(mapping(result.pop("aggregation_data", {})), payloads)
    for key in ("input_domains", "input_inventory"):
        if key in result:
            analysis = mapping(result[key])
            if "aggregation_ref" not in analysis:
                result[key] = {"aggregation_ref": _store(analysis, payloads)}
    if "work_partition" in result:
        work = dict(mapping(result["work_partition"]))
        if "inventory_ref" not in work:
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
    Produce standalone aggregation evidence from raw or incrementally compacted records.

    Args:
        report (dict[str, object]): Chart or repository report, kept unchanged; nested payload tables are merged.

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
    inventory = _load(identity, payloads)
    if inventory.keys() != {"units", "initial"}:
        raise ValueError("Invalid aggregation inventory fields")
    result = dict(work)
    del result["inventory_ref"]
    result.update(inventory)
    return result


def _load(identity: str, payloads: dict[str, object]) -> dict[str, object]:
    """
    Decode and verify a single content-addressed analysis object.

    Args:
        identity (str): SHA-256 reference from a compact record.
        payloads (dict[str, object]): Shared encoded analysis objects.

    Returns:
        dict[str, object]: Original object; missing or corrupt data raises ValueError.
    """
    payload = payloads.get(identity)
    if not isinstance(payload, str):
        raise ValueError("Missing aggregation payload")
    try:
        raw = gzip.decompress(base64.b64decode(payload, validate=True))
    except (ValueError, OSError, EOFError, zlib.error) as exc:
        raise ValueError("Invalid compressed aggregation payload") from exc
    if hashlib.sha256(raw).hexdigest() != identity:
        raise ValueError("Aggregation payload checksum mismatch")
    return mapping(json.loads(raw))


def _expand(record: dict[str, object], payloads: dict[str, object], decoded: dict[str, dict[str, object]]) -> dict[str, object]:
    """
    Restore metadata only at report boundaries, sharing repeated decoded objects.

    Args:
        record (dict[str, object]): Compact chart, baseline or phase record.
        payloads (dict[str, object]): Complete encoded payload table.
        decoded (dict[str, dict[str, object]]): Decoded analysis cache owned by one expansion.

    Returns:
        dict[str, object]: Expanded record with user values and findings untouched.
    """
    result = {key: value for key, value in record.items() if key != "aggregation_data"}
    for key in ("input_domains", "input_inventory"):
        if key in result and "aggregation_ref" in (analysis := mapping(result[key])):
            identity = str(analysis["aggregation_ref"])
            if identity not in decoded:
                decoded[identity] = _load(identity, payloads)
            result[key] = decoded[identity]
    if "work_partition" in result:
        result["work_partition"] = expand_inventory(mapping(result["work_partition"]), payloads)
    for key in ("charts", "phases"):
        if key in result:
            result[key] = [_expand(mapping(item), payloads, decoded) for item in sequence(result[key])]
    if "baseline" in result:
        result["baseline"] = _expand(mapping(result["baseline"]), payloads, decoded)
    return result


def expand_record(record: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    """
    Restore one chart for raw publication without expanding the complete repository.

    Args:
        record (dict[str, object]): Compact record whose nested payload tables have been merged.
        payloads (dict[str, object]): Repository payload table produced by compact_report.

    Returns:
        dict[str, object]: Original record; repeated phase analysis shares memory until serialization completes.
    """
    return _expand(record, payloads, {})
