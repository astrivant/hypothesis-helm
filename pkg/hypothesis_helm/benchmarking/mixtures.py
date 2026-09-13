"""
Distribute reproducible categorical topology components over shared chart inputs.
"""

import math
import random
from collections import Counter
from pathlib import Path

from hypothesis_helm.benchmarking.structures import STRUCTURES, write_structure


def normalized_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """
    Validate and normalize a categorical topology distribution.

    Args:
        weights (dict[str, float] | None): Relative weights, or uniform across all structures.

    Returns:
        dict[str, float]: Ordered probabilities; unspecified categories have zero probability.
    """
    selected = dict.fromkeys(STRUCTURES, 1.0) if weights is None else weights
    if set(selected) - set(STRUCTURES):
        raise ValueError("unknown topology weight category")
    if not selected or any(not math.isfinite(v) or v < 0 for v in selected.values()):
        raise ValueError("topology weights must be finite and nonnegative")
    total = sum(selected.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("topology weights must have a finite positive sum")
    return {name: selected.get(name, 0) / total for name in STRUCTURES}


def write_mixture(
    chart: Path,
    active: int,
    complexity: int,
    count: int,
    weights: dict[str, float] | None,
    seed: int,
    depth_weights: dict[int, float] | None = None,
) -> dict[str, object]:
    """
    Sample component types and input wiring while keeping numeric boundaries type compatible.

    Args:
        chart (Path): Existing base chart.
        active (int): Number of reserved normal-quantile selectors.
        complexity (int): Total number of declared inputs.
        count (int): Number of structural components.
        weights (dict[str, float] | None): Relative categorical topology weights.
        seed (int): Reproducible placement seed independent of fault and trim seeds.
        depth_weights (dict[int, float] | None): Probabilities for added Boolean gate depths.

    Returns:
        dict[str, object]: Requested probabilities, realized counts and exact component wiring.
    """
    probabilities = normalized_weights(weights)
    rng = random.Random(seed)
    names = rng.choices(list(probabilities), weights=list(probabilities.values()), k=count)
    numeric = complexity - 1 if "boundaries" in names else None
    boolean = [f"input{i:03d}" for i in range(active, complexity) if i != numeric]
    components = []
    depth_rng = random.Random(seed + 1)
    gate_rng = random.Random(seed + 2)
    for index, name in enumerate(names):
        paths = rng.sample(boolean, 4)
        if name == "boundaries":
            paths[0] = f"input{numeric:03d}"
        component = write_structure(chart, name, active, paths=paths, prefix=f"component-{index:03d}-")
        if depth_weights is not None:
            depth = depth_rng.choices(list(depth_weights), weights=list(depth_weights.values()))[0]
            gates = gate_rng.sample(boolean, len(boolean))[:depth]
            path = chart / "templates" / f"structure-component-{index:03d}.yaml"
            opening = "\n".join("{{ if .Values." + gate + " }}" for gate in gates)
            closing = "\n".join("{{ end }}" for _ in gates)
            path.write_text(opening + "\n" + path.read_text() + "\n" + closing + "\n")
            component["gate_paths"] = gates
            component["gate_depth"] = depth
        components.append(component)
    return {
        "name": "mixed",
        "distribution": "categorical",
        "seed": seed,
        "requested_probabilities": probabilities,
        "realized_counts": {name: names.count(name) for name in STRUCTURES},
        "component_count": count,
        "components": components,
        "depth_weights": {str(key): value for key, value in depth_weights.items()} if depth_weights is not None else None,
        "numeric_input": numeric,
        "wiring": "four distinct sampled paths per component; paths shared across components",
        "realized_probabilities": {name: value / count for name, value in Counter(names).items()},
    }
