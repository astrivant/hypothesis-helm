"""
Define source-bound workloads and measured backend results for paired comparisons.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from typing import TYPE_CHECKING

from attrs import frozen
from cattrs import Converter
from hypothesis_helm.compiler.backends.model import Factor, Limits, Node, Opcode, Plan, State, digest

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ("BACKENDS", "Case", "Hardware", "Lane", "Sample", "Workload", "read_lanes", "read_workload", "save", "validate_lane")

BACKENDS = ("reference", "cpu-vector", "gpu")
CONVERTER = Converter(forbid_extra_keys=True)


@frozen
class Workload:
    """
    Freeze common inputs before dispatching any hardware lane.

    Attributes:
        source (str): Exact source commit, or a synthetic local SHA.
        run (str): Dispatch run identifier, or local for an explicit local experiment.
        attempt (int): Dispatch attempt identifying this frozen measurement set.
        seed (int): Seed for independent finite dictionaries and candidate order.
        candidates (int): Number of candidates evaluated in every repetition.
        factors (int): Boolean dictionary count, grouped in fours.
        batches (tuple[int, ...]): Identical batch sizes used on every backend.
        repeats (int): Number of measured steady repetitions after the cold pass.
        version (int): Comparison format and workload-generation semantics.
    """

    source: str
    run: str
    attempt: int = 1
    seed: int = 2026
    candidates: int = 8192
    factors: int = 24
    batches: tuple[int, ...] = (64, 256, 1024, 4096)
    repeats: int = 5
    version: int = 1

    def validate(self) -> None:
        """
        Reject unsupported workloads before allocating a worker or trusting evidence.

        Returns:
            None: All lanes can execute the same finite bounded workload.

        Raises:
            ValueError: Provenance, sizes or repeat settings are unsupported.
        """
        if (
            self.version != 1
            or re.fullmatch(r"[0-9a-f]{40}", self.source) is None
            or re.fullmatch(r"local|[0-9]+", self.run) is None
            or self.attempt < 1
            or not 0 <= self.seed < 2**32
            or not 1 <= self.candidates <= 65536
            or not 4 <= self.factors <= 48
            or self.factors % 4
            or not 2 <= self.repeats <= 20
            or not 1 <= len(self.batches) <= 8
            or tuple(sorted(set(self.batches))) != self.batches
            or any(not 1 <= batch <= min(16384, self.candidates) for batch in self.batches)
        ):
            raise ValueError("invalid matched benchmark workload")

    @property
    def identity(self) -> str:
        """
        Identify every shared input including source, run, limits and repetition count.

        Returns:
            str: SHA-256 of the canonical manifest.
        """
        return hashlib.sha256(encode(self).encode()).hexdigest()

    def inputs(self, batch: int) -> tuple[Plan, tuple[int, ...], tuple[State, ...]]:
        """
        Build one immutable program, candidate stream and independent host oracle.

        Args:
            batch (int): A batch size declared in this manifest.

        Returns:
            tuple[Plan, tuple[int, ...], tuple[State, ...]]: Plan, ordered IDs and expected states.

        Raises:
            ValueError: The batch is not declared by the manifest.
        """
        self.validate()
        if batch not in self.batches:
            raise ValueError("batch is outside the matched workload")
        rng = random.Random(self.seed)
        factors = tuple(Factor((f"factor{index}",), 2, digest([False, True])) for index in range(self.factors))
        tables = tuple(tuple(rng.choice(tuple(State)) for _ in range(2)) for _ in factors)
        nodes = [Node(Opcode.LOOKUP, factor=index, table=table) for index, table in enumerate(tables)]
        groups = []
        for start in range(0, self.factors, 4):
            groups.append(len(nodes))
            nodes.append(Node(Opcode.ONE, operands=tuple(range(start, start + 4))))
        nodes.append(Node(Opcode.OR, operands=tuple(groups)))
        plan = Plan(self.identity, factors, tuple(nodes), len(nodes) - 1, limits=Limits(batch_size=batch))
        plan.validate()
        ids = tuple(rng.randrange(plan.cardinality) for _ in range(self.candidates))

        # Decode Boolean dictionaries independently of the packed/native evaluator.
        expected = []
        for number in ids:
            choices = [table[(number >> (self.factors - index - 1)) & 1] for index, table in enumerate(tables)]
            clauses = []
            for start in range(0, self.factors, 4):
                values = choices[start : start + 4]
                truths = values.count(State.TRUE)
                clauses.append(State.FALSE if truths > 1 else State.UNKNOWN if State.UNKNOWN in values else State(truths == 1))
            expected.append(State.TRUE if State.TRUE in clauses else State.UNKNOWN if State.UNKNOWN in clauses else State.FALSE)
        return plan, ids, tuple(expected)


@frozen
class Hardware:
    """
    Retain observed execution hardware and runtime without machine identifiers.

    Attributes:
        system (str): Operating system family.
        architecture (str): Observed machine architecture.
        cpus (int): Available logical CPU count.
        python (str): Exact interpreter version shared by the lanes.
        numpy (str): Exact shared numerical runtime version.
        compiler (str): Selected Numba or Torch version, or reference.
        accelerator (str): Observed GPU model, or CPU.
    """

    system: str
    architecture: str
    cpus: int
    python: str
    numpy: str
    compiler: str
    accelerator: str


@frozen
class Sample:
    """
    Separate synchronized evaluation, worker-boundary latency and host validation.

    Attributes:
        wall (float): Seconds for all requests including packing, IPC, transfer and decoding.
        engine (float): Engine-reported seconds including packing, transfer and synchronization.
        verification (float): Seconds for independent ordered-result validation.
    """

    wall: float
    engine: float
    verification: float


@frozen
class Case:
    """
    Retain a cold pass and steady repeats for one exact plan and batch size.

    Attributes:
        batch (int): Maximum candidates per request.
        plan (str): SHA-256 of the exact executable plan.
        output (str): SHA-256 of the validated ordered states.
        setup (float): Worker startup and adapter preparation seconds.
        cold (Sample): First complete pass including lazy compilation where applicable.
        samples (tuple[Sample, ...]): Complete warm steady repetitions.
    """

    batch: int
    plan: str
    output: str
    setup: float
    cold: Sample
    samples: tuple[Sample, ...]


@frozen
class Lane:
    """
    Bind actual backend execution and timing evidence to one frozen dispatch.

    Attributes:
        workload (str): SHA-256 of the shared manifest.
        backend (str): Explicit reference, cpu-vector or gpu selection.
        device (str): Observed engine device; fallback is prohibited.
        hardware (Hardware): Observed non-identifying host and runtime details.
        cases (tuple[Case, ...]): Complete ordered batch-size cases.
    """

    workload: str
    backend: str
    device: str
    hardware: Hardware
    cases: tuple[Case, ...]


def encode(value: object) -> str:
    """
    Serialize a named record canonically and reject non-finite JSON numbers.

    Args:
        value (object): Structured comparison record.

    Returns:
        str: Stable JSON with no environment or hidden runtime reads.
    """
    return json.dumps(CONVERTER.unstructure(value), sort_keys=True, indent=2, allow_nan=False) + "\n"


def save(path: Path, value: object) -> None:
    """
    Write a reviewed comparison record to an explicit output path.

    Args:
        path (Path): Caller-owned destination.
        value (object): Structured record or tuple of records.

    Returns:
        None: Parent directories and the canonical file exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value))


def read_workload(path: Path) -> Workload:
    """
    Read one manifest without accepting extra fields or lossy scalar conversions.

    Args:
        path (Path): Explicit retained manifest file.

    Returns:
        Workload: Structured input requiring semantic validation.
    """
    return CONVERTER.structure(json.loads(path.read_text()), Workload)


def read_lanes(path: Path) -> tuple[Lane, ...]:
    """
    Read one fanout lane or a committed tuple independent of the file name.

    Args:
        path (Path): Explicit retained lane or comparison measurement file.

    Returns:
        tuple[Lane, ...]: Typed lane records requiring full comparison validation.
    """
    value = json.loads(path.read_text())
    if isinstance(value, list):
        return CONVERTER.structure(value, tuple[Lane, ...])
    return (CONVERTER.structure(value, Lane),)


def strict_scalar(value: object, kind: type[object]) -> object:
    """
    Preserve JSON scalar types rather than coercing strings or booleans into numbers.

    Args:
        value (object): Decoded wire value.
        kind (type[object]): Declared primitive type.

    Returns:
        object: The unchanged scalar after exact type admission.

    Raises:
        ValueError: The JSON primitive has a different type.
    """
    if type(value) is not kind:
        raise ValueError("comparison scalar type does not match its declared field")
    return value


CONVERTER.register_structure_hook(int, strict_scalar)
CONVERTER.register_structure_hook(float, strict_scalar)
CONVERTER.register_structure_hook(str, strict_scalar)


def validate_lane(workload: Workload, lane: Lane) -> None:
    """
    Require complete source-bound measurements, real devices and exact oracle agreement.

    Args:
        workload (Workload): Frozen manifest shared by every lane.
        lane (Lane): One measured backend result.

    Returns:
        None: Every declared case and repetition has valid comparable evidence.

    Raises:
        ValueError: Evidence is incomplete, stale, mismatched or numerically invalid.
    """
    workload.validate()
    devices = {"reference": {"reference"}, "cpu-vector": {"cpu"}, "gpu": {"cuda", "mps"}}
    if (
        lane.workload != workload.identity
        or lane.backend not in BACKENDS
        or lane.device not in devices[lane.backend]
        or tuple(case.batch for case in lane.cases) != workload.batches
        or lane.hardware.cpus < 1
        or not all((lane.hardware.python, lane.hardware.numpy, lane.hardware.compiler, lane.hardware.accelerator))
        or (lane.backend == "gpu" and lane.hardware.accelerator == "CPU")
    ):
        raise ValueError("incomplete, mismatched or fallback backend evidence")
    for case in lane.cases:
        plan, _, expected = workload.inputs(case.batch)
        digest = hashlib.sha256(bytes(expected)).hexdigest()
        if case.plan != plan.identity or case.output != digest or len(case.samples) != workload.repeats:
            raise ValueError("missing repetitions or non-equivalent matched results")
        timings = (
            case.setup,
            *(value for sample in (case.cold, *case.samples) for value in (sample.wall, sample.engine, sample.verification)),
        )
        if any(not math.isfinite(value) or value < 0 for value in timings) or any(sample.wall <= 0 for sample in case.samples):
            raise ValueError("invalid benchmark duration")
