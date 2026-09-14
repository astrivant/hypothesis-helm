"""
Capture Python calling contexts with the standard profiling hook in each worker process.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import TypeVar

from attrs import asdict, define

PROFILE_DIRECTORY = "HYPOTHESIS_HELM_BENCHMARK_PROFILE_DIR"
_PROCESS_ID = uuid.uuid4().hex
T = TypeVar("T")


@define
class Frame:
    """
    Accumulate exclusive time at one position in the calling-context tree.

    Attributes:
        label (str): Filename, definition line, and qualified function name.
        parent (int): Parent frame index, or minus one for the root.
        self_seconds (float): Wall time excluding child calls and hook execution.
        calls (int): Observed Python call events at this position.
    """

    label: str
    parent: int
    self_seconds: float = 0.0
    calls: int = 0


class StackProfiler:
    """
    Preserve observed call stacks without reconstructing paths from aggregated caller counts.
    """

    def __init__(
        self,
        boundary: FrameType,
        *,
        timer: Callable[[], float] = time.perf_counter,
        max_nodes: int = 25000,
        max_depth: int = 128,
    ) -> None:
        """
        Initialize a bounded calling-context tree for one executing thread.

        Args:
            boundary (FrameType): Calling frame excluded from the captured stack.
            timer (Callable[[], float]): Monotonic wall clock, injectable for verification.
            max_nodes (int): Maximum retained tree nodes, including the root.
            max_depth (int): Maximum retained Python stack depth.

        """
        if max_nodes < 1 or max_depth < 1:
            raise ValueError("Profile node and depth limits must be positive")
        self.timer = timer
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.frames = [Frame("profiled entry", -1)]
        self.children: dict[tuple[int, str], int] = {}
        self.contexts: dict[int, int] = {id(boundary): 0}
        self.collapsed: set[int] = set()
        self.depths = [0]
        self.active = 0
        self.truncated_events = 0
        self.started = self.last = timer()

    def event(self, frame: FrameType, event: str, arg: object) -> None:
        """
        Attribute elapsed time before updating the stack on Python call or return.

        Args:
            frame (FrameType): Executing Python frame supplied by the interpreter.
            event (str): Standard sys.setprofile event name.
            arg (object): Interpreter event payload, deliberately not retained.

        Returns:
            None: Exclusive durations retain their observed caller context.
        """
        if event not in {"call", "return"}:
            return
        now = self.timer()
        self.frames[self.active].self_seconds += max(0.0, now - self.last)
        parent = self.contexts.get(id(frame.f_back), 0)
        if event == "call":
            code = frame.f_code
            label = f"{code.co_filename}:{code.co_firstlineno} ({code.co_qualname})"
            key = (parent, label)
            child = self.children.get(key)
            if (
                id(frame.f_back) in self.collapsed
                or self.depths[parent] >= self.max_depth
                or (child is None and len(self.frames) >= self.max_nodes)
            ):
                self.truncated_events += 1
                self.collapsed.add(id(frame))
                child = parent
            elif child is None:
                child = len(self.frames)
                self.frames.append(Frame(label, parent))
                self.children[key] = child
                self.depths.append(self.depths[parent] + 1)
            self.contexts[id(frame)] = child
            self.active = child
            self.frames[child].calls += 1
        else:
            self.contexts.pop(id(frame), None)
            self.collapsed.discard(id(frame))
            self.active = parent
        self.last = self.timer()

    def finish(self, *, include_tail: bool = True) -> dict[str, object]:
        """
        Close the final interval after the profiling hook has been removed.

        Args:
            include_tail (bool): Whether the hook remained active until normal shutdown.

        Returns:
            dict[str, object]: Flat tree, timing totals, and explicit capture limits.
        """
        now = self.timer()
        if include_tail:
            self.frames[self.active].self_seconds += max(0.0, now - self.last)
        return {
            "frames": [asdict(frame) for frame in self.frames],
            "captured_seconds": sum(frame.self_seconds for frame in self.frames),
            "elapsed_seconds": now - self.started,
            "truncated_events": self.truncated_events,
            "max_nodes": self.max_nodes,
            "max_depth": self.max_depth,
        }


def capture(  # noqa: UP047 - pinned pydocstyle 6 cannot parse PEP 695 function type parameters.
    function: Callable[[], T], directory: Path, role: str, metadata: dict[str, object] | None = None
) -> T:
    """
    Profile one entry and atomically save a unique file even when it raises.

    Args:
        function (Callable[[], T]): Entry executed in the current thread.
        directory (Path): Shared run directory; each process owns a unique output file.
        role (str): Coordinator or worker, kept separate when plotting.
        metadata (dict[str, object] | None): Benchmark assignment context.

    Returns:
        T: Original entry result, with exceptions propagated after saving.
    """
    if sys.getprofile() is not None:
        raise RuntimeError("A Python profiler is already active in this thread")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{role}-{os.getpid()}-{uuid.uuid4().hex}.json"
    profiler = StackProfiler(sys._getframe())
    status = "returned"
    sys.setprofile(profiler.event)
    try:
        return function()
    except BaseException:
        status = "raised"
        raise
    finally:
        complete = sys.getprofile() == profiler.event
        sys.setprofile(None)
        document = {
            "format": "hypothesis-helm-profile-v1",
            "profiler": "sys.setprofile",
            "clock": "wall seconds, excluding measured hook execution",
            "scope": "Executing Python thread; native calls and subprocess waits charged to their Python caller",
            "role": role,
            "pid": os.getpid(),
            "process_id": f"{os.getpid()}-{_PROCESS_ID}",
            "status": status,
            "capture_complete": complete,
            "metadata": metadata or {},
            **profiler.finish(include_tail=complete),
        }
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(target)


def profile_settings() -> dict[str, object] | None:
    """
    Mark benchmark measurements whose timings include instrumentation overhead.

    Returns:
        dict[str, object] | None: Active capture settings, or none for ordinary timing runs.
    """
    directory = os.environ.get(PROFILE_DIRECTORY)
    return {"directory": directory, "profiler": "sys.setprofile", "timings_include_overhead": True} if directory else None
