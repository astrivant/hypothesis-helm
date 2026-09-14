"""
Define unique indexed inputs, balanced shard ownership and a bell-shaped observable.
"""

import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path
from statistics import NormalDist

from hypothesis_helm.charts.model import Chart, merge_values
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.schemas.contracts import configuration_key, mapping
from hypothesis_helm.schemas.replay import Replay

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
    unused = ((cycle * repeats + noise) * (noise_rng.getrandbits(unused_bits) | 1) + noise_rng.getrandbits(unused_bits)) % 2**unused_bits
    return {
        f"input{bit:03d}": bool((live >> bit) & 1) if bit < active else bool((unused >> (bit - active)) & 1) for bit in range(complexity)
    }


def partition_indices(total: int, shard: Shard | None, replicas: int) -> list[range]:
    """
    Partition a fixed global input prefix into disjoint CI shards and replica workers.

    Numbered inputs use modulo shard assignment, unlike hashed pytest property IDs.
    Contiguous local worker blocks retain locality without changing shard membership.

    Args:
        total (int): Number of distinct global input IDs in the workload.
        shard (Shard | None): Existing application CI shard coordinates.
        replicas (int): Requested local process count.

    Returns:
        list[range]: Disjoint replica assignments whose union is the selected shard.
    """
    if total < 1 or replicas < 1:
        raise ValueError("permutation and replica counts must be positive")
    selected = range(shard.index - 1, total, shard.total) if shard else range(total)
    return [selected[len(selected) * worker // replicas : len(selected) * (worker + 1) // replicas] for worker in range(replicas)]


def load_inputs(chart: Chart, source: Path | None) -> Sequence[dict[str, object]] | None:
    """
    Validate custom JSONL input uniqueness or require the standardized chart schema.

    Args:
        chart (Chart): Chart whose effective input identities define duplicate tests.
        source (Path | None): Optional user-supplied finite workload.

    Returns:
        Sequence[dict[str, object]] | None: Verified JSONL offsets yielding overrides or the indexed standard generator.
    """
    if source is None:
        spec_path = chart.path / "benchmark.json"
        if not spec_path.exists():
            raise ValueError("custom charts require --values with distinct JSONL overrides")
        spec = mapping(json.loads(spec_path.read_text()))
        complexity = int(str(spec["input_complexity"]))
        properties = mapping(chart.schema.get("properties"))
        names = spec.get("input_names", [f"input{index:03d}" for index in range(complexity)])
        assert isinstance(names, list)
        if set(properties) != set(names) or any(mapping(value).get("type") != "boolean" for value in properties.values()):
            raise ValueError("custom charts require --values with distinct JSONL overrides")
        return None
    source = source.resolve()
    positions: list[tuple[int, bytes]] = []
    identities: set[bytes] = set()
    with source.open("rb") as stream:
        while True:
            offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            value = mapping(json.loads(line))
            identity = hashlib.sha256(configuration_key(merge_values(chart.defaults, value)).encode()).digest()
            if identity in identities:
                raise ValueError("--values must contain nonempty, distinct effective inputs")
            identities.add(identity)
            positions.append((offset, hashlib.sha256(line).digest()))
    if not positions:
        raise ValueError("--values must contain nonempty, distinct effective inputs")

    def at(index: int) -> dict[str, object]:
        """
        Read one verified record without retaining parsed values or an open descriptor.

        Args:
            index (int): Valid record position in the original JSONL workload.

        Returns:
            dict[str, object]: Fresh values, rejecting changed input bytes before execution.
        """
        offset, expected = positions[index]
        with source.open("rb") as stream:
            stream.seek(offset)
            line = stream.readline()
        if hashlib.sha256(line).digest() != expected:
            raise ValueError("--values workload changed after validation")
        return mapping(json.loads(line))

    return Replay(len(positions), at)


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
    names = spec.get("input_names", [f"input{bit:03d}" for bit in range(active)])
    assert isinstance(names, list)
    index = sum(
        int(bool(values[str(names[bit])] if str(names[bit]) in values else values[f"input{bit:03d}"])) << bit for bit in range(active)
    )
    normal = NormalDist(float(str(spec["mean"])), float(str(spec["stddev"])))
    lower, upper = spec["lower"], spec["upper"]
    start = normal.cdf(float(str(lower))) if lower is not None else 0.0
    stop = normal.cdf(float(str(upper))) if upper is not None else 1.0
    probability = start + (stop - start) * (index + 0.5) / int(str(spec["output_bins"]))
    return f"{normal.inv_cdf(probability):.{int(str(spec['precision']))}f}"
