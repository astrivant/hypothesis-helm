"""
Compare quadratic and quartic surfaces on the same reserved cells and repeats.
"""

import argparse
import hashlib
import json
from pathlib import Path

from attrs import asdict

from hypothesis_helm.benchmarking.analysis.quadratic import fit
from hypothesis_helm.benchmarking.analysis.symbolic import partition, surfaces
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.benchmarking.reporting.labels import current_labels
from hypothesis_helm.benchmarking.studies.symbolic_surface import score
from hypothesis_helm.schemas.contracts import mapping, sequence


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Write a separate comparison without modifying the original measurements or fits.

    Args:
        argv (list[str] | None): Explicit command options.
        workspace (FixtureWorkspace | None): Unused chart owner supplied by benchmark dispatch.

    Returns:
        int: Zero for completed comparisons, one if any model cannot be identified.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="default: polynomial-comparison/ beside the source")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--methods", nargs="+", default=[])
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    document = mapping(current_labels(json.loads(raw)))
    output = args.output or args.input.parent / "polynomial-comparison"
    if (output / "results.json").resolve() == args.input.resolve():
        parser.error("comparison output must not overwrite the source measurements")
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    repeats = int(str(mapping(document["metadata"])["repeats"]))
    selected = surfaces(document, args.methods)
    for index, surface in enumerate(selected):
        record = {key: value for key, value in surface.items() if key != "rows"}
        records.append(record)
        print(f"Polynomial comparison {index + 1}/{len(selected)}: {record['plane']} / {record['method']} / {record['metric']}", flush=True)
        try:
            split = partition([mapping(row) for row in sequence(surface["rows"])], repeats, args.seed)
        except ValueError as error:
            record.update(status="unavailable", reason=str(error))
            continue
        record["split"] = {group: [list(point) for point in points] for group, points in split.items()}
        models: dict[str, object] = {}
        record["models"] = models
        record["status"] = "completed"
        for name, degree in (("quadratic", 2), ("quartic", 4)):
            try:
                model = fit(split["train"], degree=degree)
            except ValueError as error:
                models[name] = {"status": "unavailable", "reason": str(error)}
                record["status"] = "unavailable"
                continue
            scores: dict[str, object] = {}
            for group in ("train", "cells", "seeds", "joint"):
                points = split[group]
                scores[group] = score([z for _, _, z in points], [model.predict(x, y) for x, y, _ in points])
            models[name] = {
                "status": "fitted",
                **asdict(model),
                "scores": scores,
                "predictions": [[x, y, model.predict(x, y)] for x, y, _ in split["observed"]],
            }
    ledger: dict[str, object] = {
        "source": str(args.input),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "seed": args.seed,
        "selection": "Fixed degree 2 versus 4; identical training cells; no holdout-based tuning",
        "fits": records,
    }
    (output / "results.json").write_text(json.dumps(ledger, indent=2, allow_nan=False) + "\n")
    from hypothesis_helm.benchmarking.reporting.polynomial_surface import plot

    plot(output, ledger)
    return int(any(record["status"] != "completed" for record in records))
