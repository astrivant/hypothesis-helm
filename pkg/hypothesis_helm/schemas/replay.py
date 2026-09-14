"""
Replay deterministic values by position without retaining generated configurations.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Iterator, Sequence
from typing import Generic, TypeVar, overload

T = TypeVar("T")
U = TypeVar("U")


class Replay(Sequence[T], Generic[T]):  # noqa: UP046 - pinned pydocstyle cannot parse PEP 695 classes.
    """
    Expose a repeatable indexed factory with lazy slicing and iteration.

    Factories must be deterministic and return independent mutable values. Views
    retain their source, whose contents must stay fixed for the lifetime of the view.
    """

    def __init__(self, size: int, at: Callable[[int], T]) -> None:
        """
        Keep only the population size and its position-to-value factory.

        Args:
            size (int): Number of available values.
            at (Callable[[int], T]): Deterministic factory for a valid nonnegative position.

        """
        if size < 0:
            raise ValueError("replay size must be nonnegative")
        self.size = size
        self.at = at

    def __len__(self) -> int:
        """
        Return the known population size.

        Returns:
            int: Number of replayable positions.
        """
        return self.size

    @overload
    def __getitem__(self, index: int) -> T:  # noqa: D105
        ...

    @overload
    def __getitem__(self, index: slice[int | None, int | None, int | None]) -> Replay[T]:  # noqa: D105
        ...

    def __getitem__(self, index: int | slice[int | None, int | None, int | None]) -> T | Replay[T]:
        """
        Generate one value or retain a compact positional slice.

        Args:
            index (int | slice[int | None, int | None, int | None]): Position or slice, including negative positions and steps.

        Returns:
            T | Replay[T]: Generated value or lazy slice with ordinary sequence bounds.
        """
        if isinstance(index, slice):
            return select(self, range(self.size)[index])
        position = index + self.size if index < 0 else index
        if not 0 <= position < self.size:
            raise IndexError(index)
        return self.at(position)

    def __iter__(self) -> Iterator[T]:
        """
        Reconstruct one value at a time in the original order.

        Yields:
            T: Value for the next position, without a retained population array.
        """
        for index in range(self.size):
            yield self.at(index)

    def __eq__(self, other: object) -> bool:
        """
        Compare sequence contents without materializing either side.

        Args:
            other (object): Candidate sequence to compare.

        Returns:
            bool: Whether both sequences have equal lengths and values in order.
        """
        return isinstance(other, Sequence) and len(self) == len(other) and all(a == b for a, b in zip(self, other, strict=True))


def select(source: Sequence[T], indices: Sequence[int]) -> Replay[T]:  # noqa: UP047
    """
    Retain selected positions instead of their generated objects.

    Args:
        source (Sequence[T]): Stable replay source.
        indices (Sequence[int]): Valid positions in their selected order.

    Returns:
        Replay[T]: Replayable selection owning a snapshot of its position list.
    """
    positions = indices if isinstance(indices, range) else tuple(indices)
    return Replay(len(positions), lambda index: source[positions[index]])


def transform(source: Sequence[T], function: Callable[[T], U]) -> Replay[U]:  # noqa: UP047
    """
    Defer a deterministic transformation until the selected object is needed.

    Args:
        source (Sequence[T]): Stable input sequence.
        function (Callable[[T], U]): Pure per-value transformation.

    Returns:
        Replay[U]: Positional transformed values without an output array.
    """
    return Replay(len(source), lambda index: function(source[index]))


def concatenate(*sources: Sequence[T]) -> Replay[T]:  # noqa: UP047
    """
    Join replayable populations without expanding their values.

    Args:
        *sources (Sequence[T]): Stable sequences in concatenation order.

    Returns:
        Replay[T]: Joined positional view retaining only sequence boundaries.
    """
    stops: list[int] = []
    for source in sources:
        stops.append((stops[-1] if stops else 0) + len(source))

    def at(index: int) -> T:
        """
        Locate the owning source and regenerate its value.

        Args:
            index (int): Valid position in the concatenated population.

        Returns:
            T: Value reconstructed by its source.
        """
        owner = bisect.bisect_right(stops, index)
        return sources[owner][index - (stops[owner - 1] if owner else 0)]

    return Replay(stops[-1] if stops else 0, at)
