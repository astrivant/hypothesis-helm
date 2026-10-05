"""
Keep compact scan evidence lossless and reject corrupt partition inventories.
"""

from __future__ import annotations

import base64
import copy
import gzip
import json
from pathlib import Path

import pytest

from hypothesis_helm.execution.planning.partition import Partition, digest
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.evidence.transport import compact_report, expand_inventory
from hypothesis_helm.reporting.reports.shards import read_reports
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_compact_report_preserves_evidence(tmp_path: Path) -> None:
    """
    Deduplicate analysis while retaining findings, arbitrary user values and work evidence.

    Args:
        tmp_path (Path): Independent shard transport files.

    Returns:
        None: Every compressed object round-trips and shared payloads occupy memory once.
    """
    domains = {"identity": "domain", "constraints": [{"schema": {"enum": ["x" * 100_000]}}], "diagnostics": ["warning"]}
    work = Partition.paths(Shard(1, 2), [("alpha",), ("beta",)]).report()
    phase = {"status": "failed", "error": "example", "values": {"input_domains": domains}, "input_domains": domains}
    chart = {
        "input_domains": domains,
        "input_inventory": {"fields": ["alpha", "beta"]},
        "work_partition": work,
        "baseline": {"input_domains": domains},
        "phases": [phase],
        "audit": {"findings": ["audit finding"]},
    }
    report: dict[str, object] = {"source": {"revision": "original"}, "charts": [chart], "exit_code": 1}
    previous = copy.deepcopy(report)
    compact = compact_report(report)
    assert report == previous
    payloads = mapping(compact["aggregation_data"])
    assert len(payloads) == 3
    saved = mapping(sequence(compact["charts"])[0])
    assert expand_inventory(mapping(saved["work_partition"]), payloads) == work
    for key in ("input_domains", "input_inventory"):
        identity = str(mapping(saved[key])["aggregation_ref"])
        restored = json.loads(gzip.decompress(base64.b64decode(str(payloads[identity]))))
        assert restored == chart[key] and digest(restored) == identity
    assert saved["audit"] == chart["audit"] and compact["source"] == report["source"] and compact["exit_code"] == 1
    saved_phase = mapping(sequence(saved["phases"])[0])
    assert saved_phase == {**phase, "input_domains": saved["input_domains"]}
    assert mapping(saved["baseline"])["input_domains"] == saved["input_domains"]
    # A values key resembling report metadata must never be rewritten.
    assert saved_phase["values"] == phase["values"]
    paths = [tmp_path / f"{index}.json" for index in range(2)]
    for path in paths:
        path.write_text(json.dumps(compact))
    records = read_reports(paths)
    assert all(mapping(records[0]["aggregation_data"])[key] is mapping(records[1]["aggregation_data"])[key] for key in payloads)


@pytest.mark.parametrize("damage", ["missing", "encoding", "compression", "checksum", "fields", "ambiguous", "conflict"])
def test_compact_inventory_rejects_damage(tmp_path: Path, damage: str) -> None:
    """
    Refuse incomplete or altered transport before using compressed ownership evidence.

    Args:
        tmp_path (Path): Corrupted serialized records.
        damage (str): Invalid payload or reference to exercise.

    Returns:
        None: Malformed evidence raises ValueError instead of bypassing validation.
    """
    compact = compact_report({"work_partition": Partition.paths(Shard(1, 1), [("alpha",)]).report()})
    work = mapping(compact["work_partition"])
    payloads = mapping(compact["aggregation_data"])
    identity = str(work["inventory_ref"])
    if damage == "missing":
        payloads.clear()
    elif damage == "encoding":
        payloads[identity] = "not base64"
    elif damage == "compression":
        payloads[identity] = base64.b64encode(b"not gzip").decode()
    elif damage in {"checksum", "fields"}:
        raw = {"unexpected": True}
        if damage == "fields":
            work["inventory_ref"] = identity = digest(raw)
        payloads[identity] = base64.b64encode(gzip.compress(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode())).decode()
    elif damage == "ambiguous":
        work["units"] = {}
    else:
        path = tmp_path / "inputs.json"
        other = copy.deepcopy(compact)
        mapping(other["aggregation_data"])[identity] = "different payload"
        path.write_text(json.dumps([compact, other]))
        with pytest.raises(ValueError, match="aggregation payload"):
            read_reports([path])
        return
    with pytest.raises(ValueError, match="aggregation|Aggregation"):
        expand_inventory(work, payloads)
