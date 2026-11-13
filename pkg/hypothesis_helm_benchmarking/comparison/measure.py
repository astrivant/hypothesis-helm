"""
Measure the production worker boundary on identical seeded finite programs.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from hypothesis_helm.compiler.backends.scheduler import Worker

from hypothesis_helm_benchmarking.comparison.model import BACKENDS, Case, Hardware, Lane, Sample, Workload, validate_lane

if TYPE_CHECKING:
    from hypothesis_helm.compiler.backends.engine import Engine
    from hypothesis_helm.compiler.backends.model import Plan, State

__all__ = ("measure",)
LOGGER = logging.getLogger(__name__)


def measure(
    workload: Workload,
    backend: str,
    hardware: Hardware,
    clock: Callable[[], float],
    factory: Callable[[Plan, str], Engine] = Worker,
) -> Lane:
    """
    Measure cold and warm synchronous passes, closing every owned worker on failure.

    Args:
        workload (Workload): Frozen common inputs including repeat and batch settings.
        backend (str): Explicit engine, without automatic fallback.
        hardware (Hardware): Observed host/runtime supplied at the orchestration boundary.
        clock (Callable[[], float]): Monotonic seconds used for wall durations.
        factory (Callable[[Plan, str], Engine]): Owned worker constructor, injectable for contract tests.

    Returns:
        Lane: Validated ordered evidence, including the actual device.

    Raises:
        ValueError: A worker returns reordered, different or incomplete results.
    """
    workload.validate()
    if backend not in BACKENDS:
        raise ValueError("unknown matched benchmark backend")
    cases = []
    device = ""
    for batch in workload.batches:
        plan, ids, expected = workload.inputs(batch)
        LOGGER.info("Measuring matched backend=%s batch=%d candidates=%d", backend, batch, len(ids))
        started = clock()
        worker = factory(plan, backend)
        setup = clock() - started
        try:
            if device and device != worker.device:
                raise ValueError("matched benchmark changed devices")
            device = worker.device
            samples = []
            for _ in range(workload.repeats + 1):
                states: list[State] = []
                engine = 0.0
                started = clock()
                for offset in range(0, len(ids), batch):
                    numbers = ids[offset : offset + batch]
                    result = worker.evaluate(numbers)
                    if result.ids != numbers:
                        raise ValueError("matched benchmark returned reordered candidates")
                    states.extend(result.states)
                    engine += result.seconds
                wall = clock() - started
                verification_start = clock()
                if tuple(states) != expected:
                    raise ValueError("matched benchmark does not agree with the independent oracle")
                samples.append(Sample(wall, engine, clock() - verification_start))
            cases.append(Case(batch, plan.identity, hashlib.sha256(bytes(expected)).hexdigest(), setup, samples[0], tuple(samples[1:])))
        finally:
            worker.close()
    lane = Lane(workload.identity, backend, device, hardware, tuple(cases))
    validate_lane(workload, lane)
    LOGGER.info("Completed matched backend=%s device=%s cases=%d", backend, device, len(cases))
    return lane
