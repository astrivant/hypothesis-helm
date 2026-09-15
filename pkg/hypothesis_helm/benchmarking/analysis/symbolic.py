"""
Partition paired response-surface measurements before comparing fitted models.
"""

import math
import random
import statistics

from hypothesis_helm.schemas.contracts import mapping, sequence


def partition(rows: list[dict[str, object]], repeats: int, seed: int) -> dict[str, list[tuple[float, float, float]]]:
    """
    Reserve an entire repeat and interior factor cells before model training.

    Args:
        rows (list[dict[str, object]]): One plane, method and response, with x, y and response fields.
        repeats (int): Expected number of paired repeats.
        seed (int): Seed controlling the withheld cells.

    Returns:
        dict[str, list[tuple[float, float, float]]]: Training, cell, seed and joint holdouts, plus the full held-out-seed surface.
    """
    cells = sorted({(float(str(row["x"])), float(str(row["y"]))) for row in rows})
    seeds = sorted({int(str(row["repeat"])) for row in rows})
    xs, ys = sorted({x for x, _ in cells}), sorted({y for _, y in cells})
    if len(seeds) != repeats or repeats < 2 or len(cells) != len(xs) * len(ys):
        raise ValueError("require a complete rectangular grid and at least two paired repeats")
    batches = {(x, y): [row for row in rows if (float(str(row["x"])), float(str(row["y"]))) == (x, y)] for x, y in cells}
    for batch in batches.values():
        if (
            len(batch) != repeats
            or {int(str(row["repeat"])) for row in batch} != set(seeds)
            or any(row["status"] != "passed" for row in batch)
        ):
            raise ValueError("incomplete, duplicated or censored cell: symbolic fitting skipped")
        if not all(math.isfinite(float(str(row["response"]))) for row in batch):
            raise ValueError("nonfinite response")
    candidates = [(x, y) for x, y in cells if x not in (xs[0], xs[-1]) or y not in (ys[0], ys[-1])]
    random.Random(seed).shuffle(candidates)
    withheld = set(candidates[: max(1, math.ceil(len(cells) * 0.25))])
    if len(cells) - len(withheld) <= 6:
        raise ValueError("not enough training cells for an identifiable quadratic and holdout")
    result: dict[str, list[tuple[float, float, float]]] = {key: [] for key in ("train", "cells", "seeds", "joint", "observed")}
    for x, y in cells:
        batch = batches[x, y]
        training_mean = statistics.mean(float(str(row["response"])) for row in batch if int(str(row["repeat"])) != seeds[-1])
        held_out = next(float(str(row["response"])) for row in batch if int(str(row["repeat"])) == seeds[-1])
        result["cells" if (x, y) in withheld else "train"].append((x, y, training_mean))
        result["joint" if (x, y) in withheld else "seeds"].append((x, y, held_out))
        result["observed"].append((x, y, held_out))
    return result


def surfaces(document: dict[str, object], methods: list[str]) -> list[dict[str, object]]:
    """
    Select response arrays from either supported measurement ledger format.

    Args:
        document (dict[str, object]): Parsed measurements with normalized method labels.
        methods (list[str]): Requested methods, or an empty list for all recorded methods.

    Returns:
        list[dict[str, object]]: Independent method/metric surfaces with unchanged observed responses.
    """
    rows = [mapping(row) for row in sequence(document["rows"])]
    available = sorted({str(row["strategy"]) for row in rows})
    if set(methods) - set(available):
        raise ValueError("requested methods absent from source measurements")
    result: list[dict[str, object]] = []
    for plane in sorted({str(row.get("plane", row.get("axis"))) for row in rows}):
        for method in methods or available:
            batch = [row for row in rows if str(row.get("plane", row.get("axis"))) == plane and row["strategy"] == method]
            if not batch:
                continue
            for metric in ("total_seconds", "errors_missed"):
                result.append(
                    {
                        "plane": plane,
                        "method": method,
                        "metric": metric,
                        "rows": [
                            {
                                "x": row.get("x", row.get("axis_value")),
                                "y": row.get("y", row.get("error_percent")),
                                "repeat": row["repeat"],
                                "status": row["status"],
                                "response": row[metric],
                            }
                            for row in batch
                        ],
                    }
                )
    return result
