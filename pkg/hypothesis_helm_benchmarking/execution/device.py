"""
Measure CUDA evaluation intervals only inside an explicitly instrumented worker.
"""

from __future__ import annotations

import sys
from typing import Protocol

__all__ = ("CUDA", "DeviceInterval", "Event")


class Event(Protocol):
    """
    Describe the supported PyTorch CUDA timing-event operations.
    """

    def record(self) -> None:
        """
        Record this event on the current CUDA stream.

        Returns:
            None: The event is submitted to the owning stream.
        """
        ...

    def synchronize(self) -> None:
        """
        Wait for this event to complete.

        Returns:
            None: Earlier current-stream work has completed.
        """
        ...

    def elapsed_time(self, end_event: Event) -> float:
        """
        Return the elapsed device interval in milliseconds.

        Args:
            end_event (Event): Completed event on the same device.

        Returns:
            float: Device elapsed milliseconds, including any stream idle gaps.
        """
        ...


class CUDA(Protocol):
    """
    Confine PyTorch's optional dynamically loaded CUDA instrumentation API.
    """

    def Event(self, *, enable_timing: bool) -> Event:  # noqa: N802 - upstream API name.
        """
        Create an event without changing the selected device.

        Args:
            enable_timing (bool): Require timing support for this event.

        Returns:
            Event: A timing marker owned by this interval.
        """
        ...

    def reset_peak_memory_stats(self) -> None:
        """
        Reset allocator high-water marks inside the exclusively owned benchmark worker.

        Returns:
            None: Subsequent peaks include allocations retained at this boundary.
        """
        ...

    def max_memory_allocated(self) -> int:
        """
        Read the allocator high-water mark since the interval's reset.

        Returns:
            int: PyTorch-allocated device bytes, excluding external allocations.
        """
        ...


class DeviceInterval:
    """
    Own two device markers and a scoped allocator measurement.
    """

    def __init__(self, cuda: CUDA) -> None:
        """
        Start a CUDA interval without importing or initializing another accelerator.

        Args:
            cuda (CUDA): Existing owning worker's PyTorch CUDA adapter.
        """
        self.cuda = cuda
        self.begin = cuda.Event(enable_timing=True)
        self.end = cuda.Event(enable_timing=True)
        cuda.reset_peak_memory_stats()
        self.begin.record()

    @classmethod
    def current(cls, device: str) -> DeviceInterval | None:
        """
        Reuse the active Torch module only for a CUDA evaluation.

        Args:
            device (str): Physical backend selected by the executing engine.

        Returns:
            DeviceInterval | None: A CUDA interval, or None for an unsupported device.
        """
        torch = sys.modules.get("torch")
        return cls(torch.cuda) if device == "cuda" and torch is not None else None

    def finish(self) -> tuple[float, int]:
        """
        Complete and synchronize this interval before reading timing and allocation.

        Returns:
            tuple[float, int]: Current-stream elapsed seconds and allocator peak bytes.
        """
        self.end.record()
        self.end.synchronize()
        return self.begin.elapsed_time(self.end) / 1000.0, self.cuda.max_memory_allocated()
