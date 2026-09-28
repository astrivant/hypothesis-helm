"""
Verify structural sparsity shards and retain their complete replay recipes for publication.
"""

import json
from pathlib import Path

from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.schemas.contracts import mapping, sequence

from hypothesis_helm_benchmarking.charts.structural_sparsity import PLACEMENTS

__all__ = ("merge",)


def merge(paths: list[Path], output: Path) -> dict[str, object]:
    """
    Combine every paired shard with matching settings, measurements and chart recipes.

    Args:
        paths (list[Path]): Downloaded result ledgers with adjacent cases directories.
        output (Path): Fresh merged study directory.

    Returns:
        dict[str, object]: Complete ledger retaining the serial case and shuffled method order.

    Raises:
        ValueError: Shard identities, metadata or replay recipes are inconsistent.
        AssertionError: Assigned measurements are incomplete, duplicated or inconsistent.
    """
    from hypothesis_helm_benchmarking.studies.filtering import save
    from hypothesis_helm_benchmarking.studies.structural_sparsity import verify

    if not paths or (output / "results.json").exists():
        raise ValueError("Supply structural sparsity shards and a fresh output directory")
    documents = [mapping(json.loads(path.read_text())) for path in paths]
    first = mapping(documents[0]["metadata"])
    count = int(str(first["shard_count"]))
    indices = [int(str(mapping(document["metadata"])["shard_index"])) for document in documents]
    if len(indices) != count or set(indices) != set(range(count)):
        raise ValueError("Require every structural sparsity shard exactly once")
    settings = {key: value for key, value in first.items() if key != "shard_index"}
    if any(
        {key: value for key, value in mapping(document["metadata"]).items() if key != "shard_index"} != settings for document in documents
    ):
        raise ValueError("Structural sparsity shard metadata differs")
    rows: list[dict[str, object]] = []
    recipes: dict[str, str] = {}
    for path, document in zip(paths, documents, strict=True):
        verify(document)
        for row in map(mapping, sequence(document["rows"])):
            breadth, depth = int(str(row["breadth"])), int(str(row["depth"]))
            placement = str(row["placement"])
            name = f"breadth-{breadth}-depth-{depth}-{placement}"
            if placement not in PLACEMENTS or row["case"] != name:
                raise ValueError("Structural sparsity case identity differs")
            recipe = (path.parent / "cases" / f"{name}.yaml").read_text()
            operations = mapping(mapping(yamlio.load(recipe)).get("operations", {}))
            expected = {"breadth": breadth, "depth": depth, "placement": placement, "seed": settings["seed"]}
            if operations.get("structural_sparsity") != expected:
                raise ValueError("Structural sparsity recipe parameters differ")
            if name in recipes and recipes[name] != recipe:
                raise ValueError("Structural sparsity recipes disagree")
            recipes[name] = recipe
            rows.append(row)
    # Stable sorting retains the measured method order within each case/repeat pair.
    rows.sort(
        key=lambda row: (
            sequence(settings["breadths"]).index(row["breadth"]),
            sequence(settings["depths"]).index(row["depth"]),
            sequence(settings["placements"]).index(row["placement"]),
            int(str(row["repeat"])),
        )
    )
    result: dict[str, object] = {
        "metadata": dict(settings, shard_count=1, shard_index=0, source_shards=count),
        "rows": rows,
    }
    verify(result)
    (output / "cases").mkdir(parents=True, exist_ok=True)
    for name, recipe in recipes.items():
        (output / "cases" / f"{name}.yaml").write_text(recipe)
    save(output, result)
    return result
