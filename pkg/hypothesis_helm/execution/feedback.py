"""
Tune active concurrency from measured completion throughput.
"""

from attrs import define, field


@define
class PID:
    """
    Compute bounded concurrency adjustments from normalized throughput gradients.

    Attributes:
        integral (float): Clamped accumulated error.
        previous_error (float): Error used for the preceding control update.
        derivative (float): Low-pass filtered error derivative.
    """

    integral: float = 0.0
    previous_error: float = 0.0
    derivative: float = 0.0

    def step(self, error: float, seconds: float) -> float:
        """
        Apply proportional, integral, and filtered derivative feedback.

        Args:
            error (float): Normalized marginal throughput gain per added worker.
            seconds (float): Measurement interval in seconds.

        Returns:
            float: Adjustment bounded to one worker per measurement window.
        """
        dt = max(0.05, min(seconds, 30.0))
        if error * self.previous_error < 0:
            self.integral = 0.0
        self.derivative = 0.25 * (error - self.previous_error) / dt + 0.75 * self.derivative
        candidate = max(-1.0, min(1.0, self.integral + error * dt))
        output = 3.0 * error + 0.25 * candidate + 0.1 * self.derivative
        # Conditional integration prevents windup while the slew limit is active.
        if abs(output) <= 1.0 or output * error < 0:
            self.integral = candidate
        self.previous_error = error
        return max(-1.0, min(1.0, output))


@define
class ThroughputController:
    """
    Seek higher throughput with marginal-gain feedback and bounded exploration.

    Attributes:
        limit (int): Target number of active worker threads.
        maximum (int): Hard upper bound on active workers.
        started (float): Monotonic start of the current measurement window.
        pid (PID): Controller for normalized marginal throughput.
        throughput (float): Most recent measured completion rate.
    """

    limit: int
    maximum: int
    started: float
    pid: PID = field(factory=PID)
    throughput: float = 0.0
    _count: int = 0
    _previous_rate: float | None = None
    _previous_limit: int = 0
    _gradient: float = 0.25
    _position: float = field(init=False)
    _unchanged: int = 0

    def __attrs_post_init__(self) -> None:
        """
        Validate bounds and initialize the continuous actuator position.

        Returns:
            None: Initial concurrency is constrained to the permitted range.
        """
        if not 1 <= self.limit <= self.maximum:
            raise ValueError("controller requires 1 <= limit <= maximum")
        self._position = float(self.limit)

    def sample(self, rate: float, seconds: float) -> int:
        """
        Estimate marginal throughput and take a PID step toward zero marginal gain.

        Args:
            rate (float): Completed tests per second at the current concurrency.
            seconds (float): Duration of the completed measurement window.

        Returns:
            int: New target for active worker threads.
        """
        measured_limit = self.limit
        if self._previous_rate is not None and measured_limit != self._previous_limit:
            self._gradient = max(
                -1.0,
                min(
                    1.0,
                    (rate - self._previous_rate) / max(rate, self._previous_rate, 1e-9) / (measured_limit - self._previous_limit),
                ),
            )
            # On a throughput plateau, prefer fewer active workers.
            if abs(self._gradient) < 0.02:
                self._gradient = -0.05
        self._previous_rate = rate
        self._previous_limit = measured_limit
        self.throughput = rate
        proposed = self._position + self.pid.step(self._gradient, seconds)
        self._position = max(1.0, min(float(self.maximum), proposed))
        if self._position != proposed:
            self.pid.integral = 0.0
        self.limit = max(1, min(self.maximum, round(self._position)))
        self._unchanged = self._unchanged + 1 if self.limit == measured_limit else 0
        # Probe periodically when quantization or a boundary prevents movement.
        # A PID alone cannot discover an unknown throughput maximum.
        if self._unchanged >= 3 and self.maximum > 1:
            self.limit += -1 if self.limit > 1 and (self._gradient < 0 or self.limit == self.maximum) else 1
            self._position = float(self.limit)
            self.pid = PID()
            self._unchanged = 0
        return self.limit

    def completed(self, now: float, active: int, backlog: bool) -> int:
        """
        Observe each completed test and adjust only after a populated timing window.

        Args:
            now (float): Monotonic completion timestamp.
            active (int): In-flight tests immediately before this completion.
            backlog (bool): Whether unscheduled tests remain.

        Returns:
            int: Target concurrency, unchanged during startup, draining, or short windows.
        """
        if not backlog or active != self.limit:
            self.started = now
            self._count = 0
            return self.limit
        self._count += 1
        elapsed = now - self.started
        if self._count >= max(2, self.limit) and elapsed >= 0.1:
            self.sample(self._count / elapsed, elapsed)
            self.started = now
            self._count = 0
        return self.limit
