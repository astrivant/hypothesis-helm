"""
Validate time budgets expressed in seconds or explicit duration units.
"""

import argparse
import math
import re
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType


def parse_time_limit(value: str) -> float:
    """
    Parse a positive finite duration with optional seconds, minutes or hours suffix.

    Args:
        value (str): Duration such as 180, 30s, 3m or 0.5h.

    Returns:
        float: Positive finite wall-clock budget in seconds.
    """
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([smh]?)", value.strip())
    if match is not None:
        seconds = float(match[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[match[2]]
        if math.isfinite(seconds) and seconds > 0:
            return seconds
    raise argparse.ArgumentTypeError("time limit must be positive, e.g. 180, 30s or 3m")


class TimeLimitReached(BaseException):
    """
    Stop execution without turning a budget deadline into a shrinking counterexample.
    """


@contextmanager
def execution_timer(seconds: float) -> Iterator[None]:
    """
    Interrupt an active main-thread iteration without retaining a process-wide alarm.

    Library calls in other threads or with an existing alarm use the runner's
    cooperative checks and bounded Helm subprocess timeout instead.

    Args:
        seconds (float): Remaining execution budget for this iteration.

    Yields:
        None: Execution protected by a temporary alarm where available.
    """
    if (
        threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "setitimer")
        or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0)
    ):
        yield
        return

    def expired(signum: int, frame: FrameType | None) -> None:
        """
        Unwind the current iteration without treating expiration as a test failure.

        Args:
            signum (int): Alarm signal number.
            frame (FrameType | None): Interrupted Python frame.

        Returns:
            None: Control transfers to the runner's graceful stop handler.
        """
        raise TimeLimitReached()

    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
