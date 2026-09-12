"""
Verify parallel security scans use local schemas and preserve shard ownership and failures.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from hypothesis_helm.integrations import kubesec
from hypothesis_helm.integrations.sharding import Shard


@pytest.mark.parametrize("pre_sharded", [False, True])
def test_parallel_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pre_sharded: bool) -> None:
    """
    Run the real GNU scheduler with local schema arguments and one failing security scan.

    Args:
        tmp_path (Path): Isolated binary and reports.
        monkeypatch (pytest.MonkeyPatch): Substitute a fixed available CPU count.
        pre_sharded (bool): Whether to scan every incoming record or assign a partition.

    Returns:
        None: Resource ownership, CPU-sized concurrency and failure propagation are correct.
    """
    if not shutil.which("parallel"):
        pytest.skip("GNU Parallel is required")
    binary = tmp_path / "kubesec"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[0] == 'scan'\n"
        "assert args[args.index('--schema-location')+1].startswith('/')\n"
        "assert args[args.index('--kubernetes-version')+1] == '1.35.0'\n"
        "resource = json.loads(pathlib.Path(args[-1]).read_text())\n"
        "print(json.dumps({'resource': resource['metadata']['name'], 'args': args}))\n"
        "sys.exit(2 if resource['metadata']['name'] == 'bad' else 0)\n"
    )
    binary.chmod(0o755)
    monkeypatch.setattr(os, "process_cpu_count", lambda: 3)
    source = tmp_path / "manifests.jsonl"
    source.write_text(
        "\n".join(
            json.dumps({"apiVersion": "v1", "kind": kind, "metadata": {"name": name}})
            for kind, name in [
                ("Pod", "bad"),
                ("Pod", "good"),
                ("ConfigMap", "ignored"),
                ("Pod", "last"),
            ]
        )
        + "\n"
    )
    config = json.dumps(
        {"version": "1.35.0", "schemas": str(tmp_path / "schemas {}"), "identity": "test-snapshot"}
    )
    assert (
        kubesec.scan(
            source,
            tmp_path / "results with spaces",
            config,
            executable=str(binary),
            shard=Shard(1, 2),
            pre_sharded=pre_sharded,
        )
        == 1
    )
    output = tmp_path / "results with spaces/shards/1-of-2"
    summary = json.loads((output / "summary.json").read_text())
    assert summary["jobs"] == 3
    assert summary["scanned"] == (3 if pre_sharded else 1)
    assert summary["skipped"] == 1
    assert len((output / "joblog.tsv").read_text().splitlines()) == summary["scanned"] + 1
    assert len(list((output / "manifests").glob("*.json"))) == summary["scanned"]
    assert summary["schema_identity"] == "test-snapshot"


def test_worker_override() -> None:
    """
    Enforce a finite positive number of security workers.

    Returns:
        None: User limits override automatic detection and invalid values fail.
    """
    assert kubesec.worker_count("2") == 2
    for value in ("0", "-1", "all"):
        with pytest.raises(ValueError):
            kubesec.worker_count(value)
