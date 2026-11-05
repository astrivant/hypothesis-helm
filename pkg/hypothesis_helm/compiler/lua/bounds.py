"""
Transfer complete component tables once and reuse the exact Lua upper-bound kernel.
"""

from collections.abc import Callable, Sequence
from importlib.resources import files
from typing import TYPE_CHECKING, Protocol, cast

from lupa.lua54 import LuaError, LuaRuntime  # type: ignore[import-untyped]

__all__ = ("BoundEvaluator", "Runtime")


if TYPE_CHECKING:
    from hypothesis_helm.compiler.passes.complexity import Component


class Runtime(Protocol):
    """
    Describe the small Lupa interface used by bundled compiler kernels.
    """

    def execute(self, source: str) -> object:
        """
        Load a trusted packaged Lua source file.

        Args:
            source (str): Kernel source, never a chart template or values string.

        Returns:
            object: Lua factory returned by the source.
        """
        ...

    def table_from(self, data: object, *, recursive: bool = False) -> object:
        """
        Copy primitive Python containers into Lua-owned tables.

        Args:
            data (object): Integer tables or the current factor assignment.
            recursive (bool): Convert nested containers without Python object proxies.

        Returns:
            object: Table owned exclusively by this runtime.
        """
        ...


class BoundEvaluator:
    """
    Own one chart's Lua state, retaining Python for short searches and safe fallback.
    """

    def __init__(self, components: Sequence["Component"], *, max_memory_bytes: int) -> None:
        """
        Retain complete immutable evidence and defer runtime setup until a second bound is needed.

        Args:
            components (Sequence[Component]): Validated complete local output tables.
            max_memory_bytes (int): Positive Lua allocation budget for this analysis.
        """
        if max_memory_bytes < 1:
            raise ValueError("compiler.max_lua_memory_bytes must be positive")
        self.components = tuple(components)
        self.max_memory_bytes = max_memory_bytes
        self.runtime: Runtime | None = None
        self.evaluate: Callable[[object], object] | None = None
        self.lua_calls = 0
        self.python_calls = 0
        self.fallback_reason: str | None = None

    def prepare(self) -> None:
        """
        Compile the bundled script and transfer numeric evidence once.

        Returns:
            None: The callable and its runtime remain owned by this chart analysis.
        """
        self.runtime = cast(
            Runtime,
            LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True, max_memory=self.max_memory_bytes),
        )
        # Execute only our packaged arithmetic kernel; chart text never becomes Lua code.
        factory = cast(Callable[[object], object], self.runtime.execute(files(__package__).joinpath("bounds.lua").read_text()))
        # Keep all containers alive through recursive conversion; its identity memo
        # must not encounter reused IDs from ephemeral generator/tuple conversions.
        tables = self.runtime.table_from(
            [
                {
                    "factors": list(component.factors),
                    "cases": [
                        {"choices": list(case.choices), "levels": list(case.levels)}
                        for case in component.cases
                        if case.resources is not None
                    ],
                }
                for component in self.components
            ],
            recursive=True,
        )
        self.evaluate = cast(Callable[[object], object], factory(tables))

    def __call__(self, assigned: dict[int, int]) -> int:
        """
        Compute an admissible upper bound without using Lua overflow or failed execution as evidence.

        Args:
            assigned (dict[int, int]): Shared factor choices fixed by the current search branch.

        Returns:
            int: Exact reference bound, including -1 for an impossible component.
        """
        from hypothesis_helm.compiler.passes.complexity import bound

        if self.python_calls and self.fallback_reason is None:
            try:
                if self.runtime is None:
                    self.prepare()
                assert self.runtime is not None and self.evaluate is not None
                result = self.evaluate(self.runtime.table_from(assigned))
                if type(result) is int and result >= -1:
                    self.lua_calls += 1
                    return result
                self.fallback_reason = "bound exceeds Lua's exact integer range"
            except (LuaError, MemoryError, OverflowError) as error:
                self.fallback_reason = f"{type(error).__name__}: {error}"
            self.evaluate = None
            self.runtime = None
        self.python_calls += 1
        return bound(self.components, assigned)

    def report(self) -> dict[str, object]:
        """
        Report actual backend use and any fallback without changing the proof contract.

        Returns:
            dict[str, object]: Counts and runtime limit for this complexity search.
        """
        return {
            "engine": "lua54" if self.lua_calls else "python",
            "lua_calls": self.lua_calls,
            "python_calls": self.python_calls,
            "fallback_reason": self.fallback_reason,
            "max_memory_bytes": self.max_memory_bytes,
        }
