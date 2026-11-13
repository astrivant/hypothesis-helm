"""
Encode existing concrete cases without changing their order or materializing a Cartesian space.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator

from hypothesis_helm.compiler.backends.lowering import compile_plan
from hypothesis_helm.compiler.backends.model import State
from hypothesis_helm.compiler.backends.scheduler import BackendOptions, Report, Worker
from hypothesis_helm.exceptions.backends import BackendError, InvalidPlan
from hypothesis_helm.exceptions.schemas import NonFiniteSchema
from hypothesis_helm.schemas.contracts import configuration_key
from hypothesis_helm.schemas.generation.factors import factor_space

__all__ = ("ValueEvaluator",)


class ValueEvaluator:
    """
    Retain one exact dictionary encoder and native worker for a concrete case stream.
    """

    def __init__(self, schema: dict[str, object], options: BackendOptions) -> None:
        """
        Prepare finite dictionaries once; leave unsupported shapes on the declared host route.

        Args:
            schema (dict[str, object]): Validated input schema.
            options (BackendOptions): Explicit selection, bounds and fallback policy.
        """
        self.options = options
        self.report = Report(options.name, options.name)
        self.worker: Worker | None = None
        self.positions: list[dict[str, int]] = []
        self.paths: list[tuple[str, ...]] = []
        self.containers: dict[tuple[str, ...], set[str]] = {}
        self.required_containers: set[tuple[str, ...]] = set()
        if options.name == "reference":
            return
        try:
            space = factor_space(schema)
            plan = compile_plan(schema, space, limits=options.limits, encoding="dictionary-rows")
            self.report.plan_digest = plan.identity
            self.paths = space.paths
            self.positions = [{configuration_key(value): index for index, value in enumerate(domain)} for domain in space.domains]
            for path in self.paths:
                for length in range(len(path)):
                    self.containers.setdefault(path[:length], set()).add(path[length])
            pending: list[tuple[tuple[str, ...], dict[str, object]]] = [((), space.skeleton)]
            while pending:
                prefix, container = pending.pop()
                self.required_containers.add(prefix)
                self.containers.setdefault(prefix, set()).update(container)
                pending.extend(((*prefix, name), value) for name, value in container.items() if isinstance(value, dict))
            self.worker = Worker(plan, options.name)
        except (InvalidPlan, NonFiniteSchema, BackendError):
            if options.fallback != "reference":
                raise
            self.report.selected = "reference"
            self.report.fallback_reasons["unsupported-plan-or-runtime"] = 1

    def encode(self, values: dict[str, object]) -> tuple[int, ...] | None:
        """
        Require exact object shape before using a finite plan's closed-world assertions.

        Args:
            values (dict[str, object]): Caller-owned concrete candidate.

        Returns:
            tuple[int, ...] | None: Exact dictionary choices, or a mandatory host fallback.
        """
        containers: dict[tuple[str, ...], dict[str, object]] = {(): values}
        for path in sorted(self.containers, key=len):
            if path:
                parent = containers.get(path[:-1])
                child = parent.get(path[-1]) if parent is not None else None
                if not isinstance(child, dict):
                    return None
                containers[path] = child
            if containers[path].keys() - self.containers[path]:
                return None
        row = []
        for path, positions in zip(self.paths, self.positions, strict=True):
            parent = containers.get(path[:-1])
            if parent is None:
                return None
            assignment = {path[-1]: parent[path[-1]]} if path[-1] in parent else {}
            position = positions.get(configuration_key(assignment))
            if position is None:
                return None
            row.append(position)
        return tuple(row)

    def evaluate(self, cases: Iterable[tuple[int, dict[str, object]]]) -> Iterator[tuple[int, dict[str, object], State]]:
        """
        Stream bounded batches while retaining every original case and host fallback.

        Args:
            cases (Iterable[tuple[int, dict[str, object]]]): Stable IDs and already selected concrete inputs.

        Yields:
            tuple[int, dict[str, object], State]: Original case and its supported predicate outcome.
        """
        iterator = iter(cases)
        while batch := tuple(itertools.islice(iterator, self.options.limits.batch_size if self.worker is not None else 1)):
            states = [State.UNKNOWN] * len(batch)
            if self.worker is not None:
                encoded = [(index, self.encode(values)) for index, (_, values) in enumerate(batch)]
                admitted = [(index, row) for index, row in encoded if row is not None]
                if admitted:
                    ids = tuple(index for index, _ in admitted)
                    rows = tuple(row for _, row in admitted)
                    try:
                        result = self.worker.evaluate(ids, rows)
                        self.report.physical_cases += len(ids)
                        self.report.batches += 1
                        self.report.compute_seconds += result.seconds
                        for index, state in zip(ids, result.states, strict=True):
                            states[index] = state
                    except (BackendError, MemoryError):
                        if self.options.fallback != "reference":
                            raise
                        self.close()
                        self.report.selected = "reference"
                        self.report.fallback_reasons["worker-failure"] = 1
            for (number, values), state in zip(batch, states, strict=True):
                self.report.logical_cases += 1
                self.report.unknown_cases += int(state == State.UNKNOWN)
                yield number, values, state

    def close(self) -> None:
        """
        Release only this invocation's worker and native buffers.

        Returns:
            None: Repeated closure is safe.
        """
        if self.worker is not None:
            self.worker.close()
            self.worker = None
