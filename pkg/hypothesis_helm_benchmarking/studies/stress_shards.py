"""
Validate stress progression ownership and collect reproducible case recipes from CI shards.
"""

import json
from pathlib import Path

from attrs import asdict
from cattrs import Converter
from hypothesis_helm.charts.values import yamlio
from hypothesis_helm.schemas.contracts import mapping, sequence

from hypothesis_helm_benchmarking.charts.stress import Stress, progression

__all__ = ("merge", "verify")


def verify(document: dict[str, object]) -> None:
    """
    Require every assigned step and strategy with consistent completion counts.

    Args:
        document (dict[str, object]): Completed measurement ledger.

    Returns:
        None: All assigned comparisons are present once, including valid empty shards.

    Raises:
        ValueError: Measurements are missing, duplicated, failed or inconsistent.
    """
    metadata = mapping(document["metadata"])
    count, index = int(str(metadata["shard_count"])), int(str(metadata["shard_index"]))
    steps = progression(Converter().structure(mapping(metadata["starting_parameters"])["stress"], Stress))
    length = int(str(metadata["steps"]))
    if count < 1 or not 0 <= index < count or not 1 <= length <= len(steps):
        raise ValueError("Invalid stress shard or progression bounds")
    if metadata["status"] != "complete" or metadata["generate_only"]:
        raise ValueError("Stress shard did not finish measuring")
    expected = {(step, method) for step in range(index, length, count) for method in sequence(metadata["strategies"])}
    rows = [mapping(row) for row in sequence(document["rows"])]
    if len(rows) != len(expected) or {(row["step"], row["strategy"]) for row in rows} != expected:
        raise ValueError("Missing or duplicate stress measurements")
    hashes: dict[int, object] = {}
    for row in rows:
        step = int(str(row["step"]))
        name, settings = steps[step]
        if row["case"] != name or row["parameters"] != asdict(settings):
            raise ValueError("Stress progression parameters differ")
        if row["status"] not in {"passed", "time-limit"} or row["error"] is not None:
            raise ValueError("Stress measurement failed")
        completed, selected, remaining = (int(str(row[key])) for key in ("completed", "selected", "remaining"))
        if not 0 <= completed <= selected or remaining != selected - completed or (row["status"] == "passed" and remaining):
            raise ValueError("Stress completion counts differ")
        if hashes.setdefault(step, row["chart_sha256"]) != row["chart_sha256"]:
            raise ValueError("Stress strategies measured different charts")


def merge(paths: list[Path], output: Path) -> dict[str, object]:
    """
    Verify every shard and case recipe before writing one ordered publication ledger.

    Args:
        paths (list[Path]): Downloaded shard ledgers with adjacent cases directories.
        output (Path): Fresh merged study directory.

    Returns:
        dict[str, object]: Complete progression ordered by step and strategy.

    Raises:
        ValueError: Shards, settings or recipes are incomplete or inconsistent.
    """
    from hypothesis_helm_benchmarking.studies.error_surface import save

    if not paths or (output / "results.json").exists():
        raise ValueError("Supply stress shards and a fresh output directory")
    documents = [mapping(json.loads(path.read_text())) for path in paths]
    first = mapping(documents[0]["metadata"])
    count = int(str(first["shard_count"]))
    indices = [int(str(mapping(item["metadata"])["shard_index"])) for item in documents]
    if len(indices) != count or set(indices) != set(range(count)):
        raise ValueError("Require every stress shard exactly once")
    settings = {key: value for key, value in first.items() if key != "shard_index"}
    rows: list[dict[str, object]] = []
    recipes: dict[str, str] = {}
    for path, document in zip(paths, documents, strict=True):
        if {key: value for key, value in mapping(document["metadata"]).items() if key != "shard_index"} != settings:
            raise ValueError("Stress shard metadata differs")
        verify(document)
        for row in map(mapping, sequence(document["rows"])):
            name = str(row["case"])
            # Case names come from the verified progression, never unchecked input paths.
            recipe = (path.parent / "cases" / f"{name}.yaml").read_text()
            parameters = mapping(mapping(yamlio.load(recipe))["parameters"])
            expected_parameters = dict(mapping(settings["starting_parameters"]), stress=row["parameters"])
            if parameters != expected_parameters:
                raise ValueError("Stress recipe parameters differ")
            if name in recipes and recipes[name] != recipe:
                raise ValueError("Stress recipes disagree")
            recipes[name] = recipe
            rows.append(row)
    methods = sequence(settings["strategies"])
    rows.sort(key=lambda row: (int(str(row["step"])), methods.index(row["strategy"])))
    result: dict[str, object] = {
        "metadata": dict(settings, shard_index=0, shard_count=1, source_shards=count),
        "rows": rows,
    }
    verify(result)
    (output / "cases").mkdir(parents=True, exist_ok=True)
    for name, recipe in recipes.items():
        (output / "cases" / f"{name}.yaml").write_text(recipe)
    save(output, result)
    return result
