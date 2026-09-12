"""
Define unique indexed inputs, balanced shard ownership and a bell-shaped observable.
"""

import hashlib
import json
import random
from pathlib import Path
from statistics import NormalDist

from hypothesis_helm.charts.runner import Chart, merge_values
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.schemas.contracts import configuration_key, mapping

INPUTS = 100
LIVE = 8
MULTIPLICITY = 8
VERSION = "normal-quantile-v2"


def standard_values(
    index: int,
    seed: int,
    multiplicity: int = MULTIPLICITY,
    complexity: int = INPUTS,
    bins: int = 256,
) -> dict[str, object]:
    """
    Generate a bijective input stream with controlled exact output-class repetitions.

    Active bits select normal quantiles. Affine permutations of power-of-two bit
    domains preserve uniqueness across both live and unused input fields.

    Args:
        index (int): Stable nonnegative permutation ID below the full Boolean domain.
        seed (int): Seed controlling both bit-domain permutations.
        multiplicity (int): Power-of-two desired consecutive output-equivalence multiplicity.
        complexity (int): Number of independent Boolean input fields.
        bins (int): Power-of-two output quantile count.

    Returns:
        dict[str, object]: Distinct Boolean values covering the generated input hierarchy.
    """
    active = bins.bit_length() - 1
    unused_bits = complexity - active
    if not 0 <= index < 2**complexity or unused_bits < 0:
        raise ValueError("benchmark index exceeds the finite input domain")
    if multiplicity < 1 or multiplicity & (multiplicity - 1):
        raise ValueError("equivalence multiplicity must be a positive power of two")
    repeats = min(multiplicity, 2**unused_bits)
    cycle, position = divmod(index, bins * repeats)
    quantile, noise = divmod(position, repeats)
    live_rng = random.Random(f"{VERSION}:{seed}:live")
    live = (quantile * (live_rng.getrandbits(active) | 1) + live_rng.getrandbits(active)) % bins
    noise_rng = random.Random(f"{VERSION}:{seed}:unused")
    unused = (
        (cycle * repeats + noise) * (noise_rng.getrandbits(unused_bits) | 1)
        + noise_rng.getrandbits(unused_bits)
    ) % 2**unused_bits
    return {
        f"input{bit:03d}": bool((live >> bit) & 1)
        if bit < active
        else bool((unused >> (bit - active)) & 1)
        for bit in range(complexity)
    }


def partition_indices(total: int, shard: Shard | None, replicas: int) -> list[list[int]]:
    """
    Partition a fixed global input prefix into disjoint CI shards and replica workers.

    Numbered inputs use modulo shard assignment, unlike hashed pytest property IDs.
    Contiguous local worker blocks retain locality without changing shard membership.

    Args:
        total (int): Number of distinct global input IDs in the workload.
        shard (Shard | None): Existing application CI shard coordinates.
        replicas (int): Requested local process count.

    Returns:
        list[list[int]]: Disjoint replica assignments whose union is the selected shard.
    """
    if total < 1 or replicas < 1:
        raise ValueError("permutation and replica counts must be positive")
    selected = list(range(shard.index - 1, total, shard.total)) if shard else list(range(total))
    return [
        selected[len(selected) * worker // replicas : len(selected) * (worker + 1) // replicas]
        for worker in range(replicas)
    ]


def load_inputs(chart: Chart, source: Path | None) -> list[dict[str, object]] | None:
    """
    Validate custom JSONL input uniqueness or require the standardized chart schema.

    Args:
        chart (Chart): Chart whose effective input identities define duplicate tests.
        source (Path | None): Optional user-supplied finite workload.

    Returns:
        list[dict[str, object]] | None: Custom overrides or the indexed standard generator.
    """
    if source is None:
        spec_path = chart.path / "benchmark.json"
        if not spec_path.exists():
            raise ValueError("custom charts require --values with distinct JSONL overrides")
        spec = mapping(json.loads(spec_path.read_text()))
        complexity = int(str(spec["input_complexity"]))
        properties = mapping(chart.schema.get("properties"))
        if set(properties) != {f"input{index:03d}" for index in range(complexity)} or any(
            mapping(value).get("type") != "boolean" for value in properties.values()
        ):
            raise ValueError("custom charts require --values with distinct JSONL overrides")
        return None
    values = [mapping(json.loads(line)) for line in source.read_text().splitlines() if line.strip()]
    identities = {configuration_key(merge_values(chart.defaults, value)) for value in values}
    if not values or len(values) != len(identities):
        raise ValueError("--values must contain nonempty, distinct effective inputs")
    return values


def source_digest(directory: Path) -> str:
    """
    Fingerprint all chart files without recording machine-specific absolute paths.

    Args:
        directory (Path): Chart source directory.

    Returns:
        str: SHA-256 digest of relative names and complete file bytes.
    """
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def expected_output(values: dict[str, object], spec: dict[str, object]) -> str:
    """
    Independently calculate the scalar required by one generated chart input.

    This recomputes the quantile from distribution parameters rather than trusting
    the generated lookup table or the compiler's equivalence witness.

    Args:
        values (dict[str, object]): Effective Boolean chart values.
        spec (dict[str, object]): Declared distribution parameters and precision.

    Returns:
        str: Exact rounded scalar required from the rendered ConfigMap.
    """
    active = int(str(spec["active_inputs"]))
    index = sum(int(bool(values[f"input{bit:03d}"])) << bit for bit in range(active))
    normal = NormalDist(float(str(spec["mean"])), float(str(spec["stddev"])))
    lower, upper = spec["lower"], spec["upper"]
    start = normal.cdf(float(str(lower))) if lower is not None else 0.0
    stop = normal.cdf(float(str(upper))) if upper is not None else 1.0
    probability = start + (stop - start) * (index + 0.5) / int(str(spec["output_bins"]))
    return f"{normal.inv_cdf(probability):.{int(str(spec['precision']))}f}"
