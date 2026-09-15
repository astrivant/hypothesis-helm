"""
Compare optional PySR equations with quadratics using reserved benchmark cells and seeds.
"""

import argparse
import hashlib
import importlib
import json
import math
import tempfile
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from hypothesis_helm.benchmarking.analysis.quadratic import fit
from hypothesis_helm.benchmarking.analysis.symbolic import partition, surfaces
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.benchmarking.reporting.labels import current_labels
from hypothesis_helm.schemas.contracts import mapping, sequence


class Regressor(Protocol):
    """
    Describe the optional backend without importing Julia during ordinary commands.
    """

    def fit(self, x: NDArray[np.float64], y: NDArray[np.float64], *, variable_names: list[str]) -> object:
        """
        Train a model using only the reserved training observations.

        Args:
            x (NDArray[np.float64]): Training coordinates.
            y (NDArray[np.float64]): Measured responses.
            variable_names (list[str]): Names for readable equations.

        Returns:
            object: Backend-specific estimator result.
        """
        ...

    def predict(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """
        Evaluate the selected expression.

        Args:
            x (NDArray[np.float64]): Requested coordinates.

        Returns:
            NDArray[np.float64]: Predicted response values.
        """
        ...

    def sympy(self) -> object:
        """
        Export the selected expression.

        Returns:
            object: Symbolic expression for documentation, never evaluated from a saved report.
        """
        ...


def score(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    """
    Measure holdout prediction error without clipping impossible predictions.

    Args:
        actual (list[float]): Reserved observations.
        predicted (list[float]): Predictions in the original response units.

    Returns:
        dict[str, float | None]: RMSE and R squared, undefined R squared for constant observations.
    """
    if len(actual) != len(predicted) or not actual or not all(math.isfinite(v) for v in predicted):
        raise ValueError("empty, mismatched or nonfinite model predictions")
    a, p = np.asarray(actual), np.asarray(predicted)
    sse = float(np.sum((a - p) ** 2))
    total = float(np.sum((a - a.mean()) ** 2))
    return {"rmse": math.sqrt(sse / len(a)), "r_squared": 1 - sse / total if total else None}


def coordinates(points: list[tuple[float, float, float]], bounds: tuple[float, float, float, float]) -> NDArray[np.float64]:
    """
    Normalize inputs using training bounds only.

    Args:
        points (list[tuple[float, float, float]]): Factor coordinates and measured responses.
        bounds (tuple[float, float, float, float]): Training factor bounds.

    Returns:
        NDArray[np.float64]: Normalized u and v coordinates.
    """
    return np.array(
        [[2 * (x - bounds[0]) / (bounds[1] - bounds[0]) - 1, 2 * (y - bounds[2]) / (bounds[3] - bounds[2]) - 1] for x, y, _ in points],
        dtype=np.float64,
    )


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Analyze retained measurements without rerunning chart tests.

    Args:
        argv (list[str] | None): Explicit CLI options.
        workspace (FixtureWorkspace | None): Unused shared chart owner supplied by benchmark dispatch.

    Returns:
        int: Zero when every requested fit completes; one for unavailable or failed surfaces.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="existing results.json")
    parser.add_argument("--output", type=Path, help="default: symbolic/ beside the input ledger")
    parser.add_argument("--methods", nargs="+", default=[])
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument("--fit-timeout", type=float, default=60, help="seconds per search, excluding Julia initialization")
    parser.add_argument("--max-size", type=int, default=20, help="maximum expression complexity")
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.max_size < 7 or not math.isfinite(args.fit_timeout) or args.fit_timeout <= 0:
        parser.error("require positive iterations and timeout, and max-size at least 7")
    raw = args.input.read_bytes()
    document = mapping(current_labels(json.loads(raw)))
    selected = surfaces(document, args.methods)
    output = args.output or args.input.parent / "symbolic"
    if (output / "results.json").resolve() == args.input.resolve():
        parser.error("analysis output must not overwrite the source measurement ledger")
    output.mkdir(parents=True, exist_ok=True)
    try:
        backend = importlib.import_module("pysr")
    except ModuleNotFoundError as error:
        if error.name != "pysr":
            raise
        parser.error("install hypothesis-helm[symbolic] to enable optional PySR analysis")
    metadata = mapping(document["metadata"])
    records: list[dict[str, object]] = []
    ledger: dict[str, object] = {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source": str(args.input),
        "pysr_version": version("pysr"),
        "julia_version": str(backend.jl.seval("string(VERSION)")),
        "numpy_version": version("numpy"),
        "seed": args.seed,
        "iterations": args.iterations,
        "fit_timeout": args.fit_timeout,
        "max_size": args.max_size,
        "parallelism": "serial",
        "selection": "PySR best criterion on training data only; no holdout-based tuning",
        "fits": records,
    }
    for index, surface in enumerate(selected):
        record = {key: value for key, value in surface.items() if key != "rows"}
        records.append(record)
        print(f"Symbolic fit {index + 1}/{len(selected)}: {record['plane']} / {record['method']} / {record['metric']}", flush=True)
        started = monotonic()
        try:
            split = partition([mapping(row) for row in sequence(surface["rows"])], int(str(metadata["repeats"])), args.seed)
            quadratic = fit(split["train"])
            bounds = quadratic.bounds

            with tempfile.TemporaryDirectory(prefix="hypothesis-pysr-") as scratch:
                model = cast(
                    Regressor,
                    backend.PySRRegressor(
                        niterations=args.iterations,
                        maxsize=args.max_size,
                        binary_operators=["+", "-", "*", "/"],
                        unary_operators=["square", "exp"],
                        model_selection="best",
                        parallelism="serial",
                        deterministic=True,
                        random_state=args.seed,
                        timeout_in_seconds=args.fit_timeout,
                        precision=64,
                        progress=False,
                        verbosity=0,
                        input_stream="devnull",
                        output_directory=scratch,
                        populations=8,
                        population_size=27,
                    ),
                )
                model.fit(
                    coordinates(split["train"], bounds),
                    np.array([z for _, _, z in split["train"]], dtype=np.float64),
                    variable_names=["u", "v"],
                )
                record.update(
                    equation=str(model.sympy()),
                    bounds=bounds,
                    quadratic_coefficients=quadratic.coefficients,
                    split={group: [list(point) for point in points] for group, points in split.items()},
                )
                scores: dict[str, object] = {}
                for group in ("train", "cells", "seeds", "joint"):
                    points = split[group]
                    actual = [z for _, _, z in points]
                    scores[group] = {
                        "quadratic": score(actual, [quadratic.predict(x, y) for x, y, _ in points]),
                        "symbolic": score(actual, [float(z) for z in model.predict(coordinates(points, bounds))]),
                    }
                observed = split["observed"]
                predicted = [float(z) for z in model.predict(coordinates(observed, bounds))]
                score([z for _, _, z in observed], predicted)
                record.update(
                    status="complete",
                    scores=scores,
                    predictions=[
                        {"x": x, "y": y, "observed": z, "quadratic": quadratic.predict(x, y), "symbolic": predicted[i]}
                        for i, (x, y, z) in enumerate(observed)
                    ],
                )
        except (ValueError, RuntimeError) as error:
            record.update(status="unavailable", reason=str(error))
        except KeyboardInterrupt:
            record.update(status="interrupted", reason="analysis interrupted", analysis_seconds=monotonic() - started)
            (output / "results.json").write_text(json.dumps(ledger, indent=2, allow_nan=False) + "\n")
            from hypothesis_helm.benchmarking.reporting.symbolic import plot

            plot(output, ledger)
            return 130
        record["analysis_seconds"] = monotonic() - started
        (output / "results.json").write_text(json.dumps(ledger, indent=2, allow_nan=False) + "\n")
    from hypothesis_helm.benchmarking.reporting.symbolic import plot

    plot(output, ledger)
    if output.resolve() == (args.input.parent / "symbolic").resolve():
        guide = args.input.parent / "README.md"
        link = "[Symbolic equations versus quadratics on held-out data](symbolic/README.md)"
        if guide.is_file() and link not in guide.read_text():
            guide.write_text(guide.read_text().rstrip() + "\n\n" + link + "\n")
    return int(any(record["status"] != "complete" for record in records))
