"""
Report permutation workload, measured progress and previous-run comparisons.
"""

import hashlib
import json
import logging
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

from attrs import define, field

from hypothesis_helm.schemas.combinations import InteractionPlan

LOGGER = logging.getLogger(__name__)


@define
class PermutationStatistics:
    """
    Track successful iterations separately from attempts and persist a count baseline.

    Attributes:
        chart (Path): Source chart used to scope history within the artifact directory.
        plan (InteractionPlan): Complete finite interaction plan.
        directory (Path | None): Artifact destination, or no persistent history.
        planning_seconds (float): Measured time spent constructing the plan.
        context (dict[str, object]): Execution settings controlling historical timing reuse.
        attempted (int): Iterations started, including failures and interruptions.
        completed (int): Iterations that passed all checks.
        successful_seconds (float): Total execution time of successful iterations.
        rendered_successes (int): Successful iterations invoking Helm.
        render_seconds (float): Measured renderer time for successful iterations.
        check_seconds (float): Other successful iteration work.
        started (float): Monotonic execution start time.
        previous (dict[str, object]): Last valid run statistics for this chart.
        last_log (float): Monotonic timestamp of the preceding progress message.
    """

    chart: Path
    plan: InteractionPlan
    directory: Path | None
    planning_seconds: float
    context: dict[str, object]
    attempted: int = 0
    completed: int = 0
    successful_seconds: float = 0.0
    rendered_successes: int = 0
    render_seconds: float = 0.0
    check_seconds: float = 0.0
    started: float = field(factory=lambda: time.perf_counter())
    previous: dict[str, object] = field(factory=dict)
    last_log: float = 0.0

    def __attrs_post_init__(self) -> None:
        """
        Read compatible history and announce the planned work before rendering.

        Returns:
            None: Initial counts and historical timing are logged.
        """
        destination = self.history_path()
        if destination is not None and destination.exists():
            try:
                previous = json.loads(destination.read_text())
                if (
                    isinstance(previous, dict)
                    and previous.get("version") == 1
                    and previous.get("chart") == str(self.chart.resolve())
                    and type(previous.get("planned_iterations")) is int
                    and previous["planned_iterations"] > 0
                ):
                    self.previous = previous
                else:
                    LOGGER.warning("Ignoring incompatible permutation history: %s", destination)
            except (OSError, ValueError):
                LOGGER.warning("Ignoring unreadable permutation history: %s", destination)
        stats = self.snapshot()
        LOGGER.info(
            "Permutation plan: %d distinct configurations including defaults = %d iterations; "
            "%d duplicate cases removed; "
            "%d valid coverage assignments (strength %d); "
            "%d candidate assignments before constraints and deduplication; "
            "%d planning candidates in %.2fs",
            stats["unique_configurations"],
            stats["planned_iterations"],
            stats["duplicate_cases_removed"],
            self.plan.interactions,
            self.plan.strength,
            stats["candidate_assignments"],
            self.plan.candidates,
            self.planning_seconds,
        )
        previous_total = stats["previous_planned_iterations"]
        if previous_total is None:
            LOGGER.info("Permutation comparison: no previous run for this chart")
        else:
            LOGGER.info(
                "Permutation comparison: %s -> %s iterations (%+d versus previous); "
                "all %s iterations will run",
                previous_total,
                stats["planned_iterations"],
                stats["iteration_delta"],
                stats["planned_iterations"],
            )
        self.log_progress(stats)

    def history_path(self) -> Path | None:
        """
        Locate the chart-specific history independently of interaction strength.

        Returns:
            Path | None: Baseline destination when artifacts are enabled.
        """
        if self.directory is None:
            return None
        key = hashlib.sha256(str(self.chart.resolve()).encode()).hexdigest()
        return self.directory / "permutation-history" / f"{key}.json"

    def snapshot(self) -> dict[str, object]:
        """
        Calculate remaining work and an advisory estimate from measured execution.

        Returns:
            dict[str, object]: Current counts, timing, comparison and estimate provenance.
        """
        total = len(self.plan.values) + 1
        remaining = total - self.completed
        previous_total = self.previous.get("planned_iterations")
        delta = total - previous_total if isinstance(previous_total, int) else None
        average = None
        source = "unknown"
        if self.completed:
            average = self.successful_seconds / self.completed
            source = "current_run"
        elif self.previous.get("context") == self.context and not self.context.get(
            "custom_properties"
        ):
            historical = self.previous.get("seconds_per_iteration")
            if (
                type(historical) in (int, float)
                and isinstance(historical, int | float)
                and math.isfinite(historical)
                and historical >= 0
            ):
                average = float(historical)
                source = "previous_run"
        return {
            "cost_profile": {
                "seconds_per_render": self.render_seconds / self.rendered_successes
                if self.rendered_successes
                else None,
                "seconds_per_check": self.check_seconds / self.completed
                if self.completed
                else None,
            },
            "planned_iterations": total,
            "unique_configurations": total,
            "candidate_cases": self.plan.raw_cases + 1,
            "duplicate_cases_removed": self.plan.duplicate_cases_removed,
            "attempted_iterations": self.attempted,
            "completed_iterations": self.completed,
            "remaining_iterations": remaining,
            "unattempted_iterations": total - self.attempted,
            "previous_planned_iterations": previous_total,
            "iteration_delta": delta,
            "additional_iterations": max(0, delta) if delta is not None else None,
            "candidate_assignments": math.prod(len(domain) for domain in self.plan.domains),
            "planning_seconds": self.planning_seconds,
            "elapsed_seconds": max(0.0, time.perf_counter() - self.started),
            "seconds_per_iteration": average,
            "estimated_total_seconds": average * total if average is not None else None,
            "estimated_remaining_seconds": (
                0.0 if remaining == 0 else average * remaining if average is not None else None
            ),
            "estimate_source": source,
        }

    def advance(
        self, passed: bool, seconds: float, *, rendered: bool = False, render_seconds: float = 0.0
    ) -> None:
        """
        Count an attempted iteration and periodically emit measured progress.

        Args:
            passed (bool): Whether all checks for this iteration succeeded.
            seconds (float): Measured iteration duration.
            rendered (bool): Whether Helm was invoked.
            render_seconds (float): Measured renderer duration.

        Returns:
            None: Counts and successful timing samples are updated.
        """
        self.attempted += 1
        if passed:
            self.completed += 1
            self.successful_seconds += seconds
            self.rendered_successes += int(rendered)
            self.render_seconds += render_seconds
            self.check_seconds += max(0.0, seconds - render_seconds)
        now = time.perf_counter()
        if self.attempted == 1 or not passed or now - self.last_log >= 1:
            self.log_progress(self.snapshot())
            self.last_log = now

    def log_progress(self, stats: dict[str, object]) -> None:
        """
        Write a plain progress message through the stderr logging handler.

        Args:
            stats (dict[str, object]): Current statistics snapshot.

        Returns:
            None: Remaining work and advisory timing are logged without touching stdout.
        """
        eta = stats["estimated_remaining_seconds"]
        estimate = stats["estimated_total_seconds"]
        LOGGER.info(
            "Permutation progress: %s/%s completed, %s remaining (%s attempted); "
            "elapsed %.2fs; estimated total %s; ETA %s (%s)",
            stats["completed_iterations"],
            stats["planned_iterations"],
            stats["remaining_iterations"],
            stats["attempted_iterations"],
            stats["elapsed_seconds"],
            f"{estimate:.2f}s" if isinstance(estimate, int | float) else "unknown",
            f"{eta:.2f}s" if isinstance(eta, int | float) else "unknown",
            stats["estimate_source"],
        )

    def finish(self, status: str, error: str | None = None) -> dict[str, object]:
        """
        Log the final counts and atomically persist history for the next run.

        Args:
            status (str): Passed, failed, interrupted or time-limit execution outcome.
            error (str | None): Failure detail for the CI test result.

        Returns:
            dict[str, object]: Final statistics for the run report.
        """
        stats = self.snapshot()
        stats["exit_code"] = (
            0
            if status == "passed"
            else 130
            if status == "interrupted"
            else 124
            if status == "time-limit"
            else 1
        )
        LOGGER.info("Permutation run %s", status)
        self.log_progress(stats)
        destination = self.history_path()
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            assert self.directory is not None
            suite = ET.Element(
                "testsuite",
                {
                    "name": "helm-permutations",
                    "tests": "1",
                    "failures": "1" if status == "failed" else "0",
                    "errors": "1" if status in ("interrupted", "time-limit") else "0",
                    "time": str(stats["elapsed_seconds"]),
                },
            )
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": str(self.chart),
                    "name": self.plan.strategy,
                    "time": str(stats["elapsed_seconds"]),
                },
            )
            if status != "passed":
                failure = ET.SubElement(
                    case,
                    "error" if status in ("interrupted", "time-limit") else "failure",
                    {"message": error or f"Permutation run {status}; see report.json"},
                )
                failure.text = error or "Coverage is incomplete; see report.json"
            properties = ET.SubElement(case, "properties")
            for key in ("planned_iterations", "completed_iterations", "remaining_iterations"):
                ET.SubElement(properties, "property", {"name": key, "value": str(stats[key])})
            junit = self.directory / "junit.xml"
            temporary_junit = junit.with_suffix(f".{uuid4().hex}.tmp")
            ET.ElementTree(suite).write(temporary_junit, encoding="utf-8", xml_declaration=True)
            temporary_junit.replace(junit)
            history = {
                **stats,
                "version": 1,
                "chart": str(self.chart.resolve()),
                "context": self.context,
                "status": status,
                # Never turn an inherited estimate into a newly measured sample.
                "seconds_per_iteration": (
                    self.successful_seconds / self.completed if self.completed else None
                ),
            }
            temporary = destination.with_suffix(f".{uuid4().hex}.tmp")
            temporary.write_text(json.dumps(history, indent=2) + "\n")
            temporary.replace(destination)
        return stats
