"""
Measure exclusive phase costs without treating unavailable counters as zero.
"""

from __future__ import annotations

import logging
import resource
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event, RLock, Thread

from attrs import asdict, define, field, frozen

__all__ = ("METRICS", "Phase", "Resources", "Snapshot", "phase_for", "snapshot")

LOGGER = logging.getLogger(__name__)
METRICS = {
    "wall_seconds": ("Wall time", "s", "sum"),
    "cpu_seconds": ("Process CPU time", "CPU s", "sum"),
    "child_cpu_seconds": ("Reaped child CPU time", "CPU s", "sum"),
    "rss_peak_bytes": ("Observed process RAM peak", "bytes", "max"),
    "gpu_seconds": ("CUDA stream elapsed time", "s", "sum"),
    "gpu_peak_bytes": ("CUDA allocator peak", "bytes", "max"),
    "disk_read_bytes": ("Storage bytes read (with reaped children)", "bytes", "sum"),
    "disk_write_bytes": ("Storage bytes dirtied (with reaped children)", "bytes", "sum"),
}


@frozen
class Snapshot:
    """
    Own process counters, separate child CPU, and current resident memory.

    Attributes:
        wall (float): Monotonic seconds.
        cpu (float): User and system CPU seconds across this process's threads.
        child_cpu (float): Cumulative CPU of terminated, waited-for children.
        rss (int | None): Current resident bytes, when supported.
        read (int | None): Storage read counter including waited-for children, when supported.
        write (int | None): Storage write counter including waited-for children, when supported.
    """

    wall: float
    cpu: float
    child_cpu: float
    rss: int | None = None
    read: int | None = None
    write: int | None = None


def snapshot(proc: Path = Path("/proc/self")) -> Snapshot:
    """
    Read Unix CPU counters and optional Linux resident-memory and storage counters.

    Args:
        proc (Path): Current process's procfs directory, injectable for verification.

    Returns:
        Snapshot: Unsupported or inaccessible Linux measurements remain None.
    """
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss = read = write = None
    try:
        resident = int((proc / "statm").read_text().split()[1])
        rss = resident * resource.getpagesize()
    except (OSError, ValueError, IndexError):
        pass
    try:
        counters = dict(line.split(":", 1) for line in (proc / "io").read_text().splitlines())
        read, write = int(counters["read_bytes"]), int(counters["write_bytes"])
    except (OSError, ValueError, KeyError):
        pass
    return Snapshot(time.perf_counter(), own.ru_utime + own.ru_stime, children.ru_utime + children.ru_stime, rss, read, write)


def phase_for(filename: str, function: str, inherited: str) -> str:
    """
    Classify known implementation boundaries and retain the caller's phase elsewhere.

    Args:
        filename (str): Executing definition's source filename.
        function (str): Qualified Python definition name.
        inherited (str): Nearest classified caller, including an explicit unclassified bucket.

    Returns:
        str: Stable phase label; paths alone never establish semantic intent.
    """
    path = filename.replace("\\", "/")
    if "/hypothesis_helm_benchmarking/reporting/" in path or "/hypothesis_helm/reporting/" in path:
        return "Reporting"
    if "/compiler/passes/pruning.py" in path or "/compiler/asts/templates.py" in path:
        return "Exact-equivalence analysis"
    if "/compiler/passes/topology.py" in path:
        return "Topology filtering"
    if "/compiler/backends/" in path:
        return "Predicate evaluation" if function.endswith("evaluate") else "Backend preparation and IPC"
    if "/schemas/generation/" in path:
        return "Candidate generation"
    if "/jsonschema/" in path:
        return "Schema validation"
    if "/charts/testing/rendering.py" in path:
        return "Helm rendering" if function == "render_output" else "Manifest validation"
    if "/yaml/" in path or "/ruamel/yaml/" in path or path.endswith("/values/yamlio.py"):
        return "YAML parsing and serialization"
    if "/compiler/randomness/rendering.py" in path:
        return "Helm rendering"
    if "/execution/checks/" in path:
        return "Property checks"
    return inherited


@define
class Phase:
    """
    Accumulate additive costs and observed peaks for one exclusive process phase.

    Attributes:
        name (str): Stable classification label.
        values (dict[str, float | None]): Metric values, with None for unavailable observations.
        rss_samples (int): Number of resident-memory observations in this phase.
        unavailable (list[str]): Counter streams that became unavailable or reset within this phase.
    """

    name: str
    values: dict[str, float | None] = field(factory=lambda: dict.fromkeys(METRICS))
    rss_samples: int = 0
    unavailable: list[str] = field(factory=list)

    def add(self, key: str, value: float) -> None:
        """
        Add an observed counter delta or take the larger observed peak.

        Args:
            key (str): Declared metric name.
            value (float): Observed nonnegative amount in the metric's units.

        Returns:
            None: Existing missing values become measured only after an observation.
        """
        if key in self.unavailable:
            return
        previous = self.values[key]
        self.values[key] = max(previous or 0.0, value) if METRICS[key][2] == "max" else (previous or 0.0) + value


class Resources:
    """
    Attribute phase transitions and sampled RAM to one owning process.
    """

    def __init__(self, read: Callable[[], Snapshot] = snapshot, interval: float = 0.025) -> None:
        """
        Start counters; launch the owned sampler explicitly after installing the hook.

        Args:
            read (Callable[[], Snapshot]): Operating-system counter reader.
            interval (float): Resident-memory sampling interval in seconds.
        """
        if interval <= 0:
            raise ValueError("Resource sampling interval must be positive")
        self.read = read
        self.interval = interval
        self.phases: dict[str, Phase] = {}
        self.active = "Other and orchestration"
        self.last = read()
        self.lock = RLock()
        self.stop = Event()
        self.thread = Thread(target=self._sample, name="benchmark-resource-sampler")
        self._memory(self.last)

    def start(self) -> None:
        """
        Start the sampler owned by this capture.

        Returns:
            None: Sampling ends and the thread is joined by finish.
        """
        LOGGER.info("Starting phase resource capture; RAM sample interval=%.3fs", self.interval)
        self.thread.start()

    def _memory(self, current: Snapshot) -> None:
        """
        Retain current resident usage without misusing the process lifetime high-water mark.

        Args:
            current (Snapshot): One current process observation.

        Returns:
            None: The observed peak remains a lower bound on the actual peak.
        """
        phase = self.phases.setdefault(self.active, Phase(self.active))
        if current.rss is not None:
            phase.add("rss_peak_bytes", float(current.rss))
            phase.rss_samples += 1

    def _sample(self) -> None:
        """
        Observe resident memory during native waits as well as Python execution.

        Returns:
            None: The stop event promptly ends the owned thread.
        """
        while not self.stop.wait(self.interval):
            with self.lock:
                self._memory(self.read())

    def transition(self, name: str, *, force: bool = False) -> None:
        """
        Close one exclusive interval before changing the active phase.

        Args:
            name (str): Next owning phase.
            force (bool): Close the tail even when the phase name is unchanged.

        Returns:
            None: Counter deltas are assigned once, and peaks are observed on both sides.
        """
        if name == self.active and not force:
            return
        with self.lock:
            current = self.read()
            phase = self.phases.setdefault(self.active, Phase(self.active))
            for key, before, after in (
                ("wall_seconds", self.last.wall, current.wall),
                ("cpu_seconds", self.last.cpu, current.cpu),
                ("child_cpu_seconds", self.last.child_cpu, current.child_cpu),
                ("disk_read_bytes", self.last.read, current.read),
                ("disk_write_bytes", self.last.write, current.write),
            ):
                if before is not None and after is not None and after >= before:
                    phase.add(key, after - before)
                else:
                    phase.values[key] = None
                    if key not in phase.unavailable:
                        phase.unavailable.append(key)
            self._memory(current)
            self.active = name
            self._memory(current)
            self.last = current

    def gpu(self, seconds: float, peak: int) -> None:
        """
        Record a synchronized CUDA interval in its executing predicate phase.

        Args:
            seconds (float): Current-stream event elapsed time, including possible stream idle time.
            peak (int): PyTorch allocator high-water mark during this isolated evaluation.

        Returns:
            None: Device observations remain separate from host CPU and wall time.
        """
        phase = self.phases.setdefault("Predicate evaluation", Phase("Predicate evaluation"))
        phase.add("gpu_seconds", seconds)
        phase.add("gpu_peak_bytes", float(peak))

    def finish(self) -> dict[str, object]:
        """
        Join sampling and retain all measurements, ownership and unavailable-metric semantics.

        Returns:
            dict[str, object]: Versioned resource receipt for independent ranking and redraw.
        """
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join()
        self.transition(self.active, force=True)
        LOGGER.info("Completed phase resource capture; phases=%d", len(self.phases))
        return {
            "format": "hypothesis-helm-phase-resources-v1",
            "sample_interval_seconds": self.interval,
            "scope": "CPU/RSS describe one process; child CPU is separate. Storage includes waited-for children. No live-tree totals.",
            "unavailable": "None means unsupported or unobserved; never substitute zero.",
            "phases": [asdict(self.phases[name]) for name in sorted(self.phases)],
        }
