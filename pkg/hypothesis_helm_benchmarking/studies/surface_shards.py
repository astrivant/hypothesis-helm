"""
Verify paired error-surface shards before publishing one complete study.
"""

import json
from pathlib import Path

from hypothesis_helm.schemas.contracts import mapping, sequence

__all__ = ("merge",)


def merge(paths: list[Path]) -> dict[str, object]:
    """
    Combine disjoint, complete shards with identical experimental settings.

    Args:
        paths (list[Path]): Result ledgers from every requested shard.

    Returns:
        dict[str, object]: Verified full ledger with shard provenance.

    Raises:
        ValueError: Shards are missing, repeated or use different experimental settings.
    """
    from hypothesis_helm_benchmarking.studies.error_surface import verify

    if not paths:
        raise ValueError("No error-surface shards supplied")
    documents = [mapping(json.loads(path.read_text())) for path in paths]
    first = mapping(documents[0]["metadata"])
    count = int(str(first.get("shard_count", 1)))
    indices = [int(str(mapping(document["metadata"]).get("shard_index", 0))) for document in documents]
    if len(indices) != count or set(indices) != set(range(count)):
        raise ValueError("Require every error-surface shard exactly once")
    settings = {key: value for key, value in first.items() if key != "shard_index"}
    rows: list[object] = []
    populations: dict[str, object] = {}
    for document in sorted(documents, key=lambda item: int(str(mapping(item["metadata"])["shard_index"]))):
        metadata = mapping(document["metadata"])
        if {key: value for key, value in metadata.items() if key != "shard_index"} != settings:
            raise ValueError("Error-surface shard metadata differs")
        verify(document)
        rows.extend(sequence(document["rows"]))
        for digest, population in mapping(document["populations"]).items():
            if digest in populations and populations[digest] != population:
                raise ValueError("Error-surface population evidence differs")
            populations[digest] = population
    result: dict[str, object] = {
        "metadata": dict(settings, shard_count=1, shard_index=0, source_shards=count),
        "rows": rows,
        "populations": populations,
    }
    verify(result)
    return result
