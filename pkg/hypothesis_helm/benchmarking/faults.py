"""
Generate reproducible semantic faults with an explicit interaction-population denominator.
"""

import math
import random
from fractions import Fraction
from pathlib import Path

from attrs import asdict, frozen


@frozen
class Fault:
    """
    Represent an injected wrong-output condition independent of the coverage planner.

    Attributes:
        name (str): Stable injected defect identity.
        terms (dict[str, bool]): Simultaneous field assignments activating the defect.
    """

    name: str
    terms: dict[str, bool]

    def active(self, values: dict[str, object]) -> bool:
        """
        Evaluate the trigger independently from Helm template evaluation.

        Args:
            values (dict[str, object]): Complete planned configuration.

        Returns:
            bool: Whether this configuration should expose the injected wrong output.
        """
        return all(values[key] == expected for key, expected in self.terms.items())


def write_faults(path: Path, defects: list[Fault]) -> None:
    """
    Write conditional wrong-output fields into an existing generated chart.

    Args:
        path (Path): Chart root with an existing templates directory.
        defects (list[Fault]): Independent wrong-output trigger specifications.

    Returns:
        None: The generated fault template records correct or incorrect per-defect fields.
    """
    lines = ["apiVersion: v1", "kind: ConfigMap", "metadata:", "  name: injected-faults", "data:"]
    for defect in defects:
        terms = " ".join(f"(eq .Values.{key} {str(value).lower()})" for key, value in defect.terms.items())
        lines.append(f'  {defect.name}: "{{{{ if and {terms} }}}}incorrect{{{{ else }}}}expected{{{{ end }}}}"')
    (path / "templates/faults.yaml").write_text("\n".join(lines) + "\n")


def select_faults(complexity: int, orders: tuple[int, ...], percent: float, seed: int, limit: int) -> tuple[list[Fault], dict[str, object]]:
    """
    Sample a specified percentage of assignments at each requested interaction order.

    Args:
        complexity (int): Number of independently variable Boolean paths.
        orders (tuple[int, ...]): Fault interaction orders to sample.
        percent (float): Percentage of subset-pattern pairs to corrupt at each order.
        seed (int): Reproducible random fault selection seed.
        limit (int): Maximum total faults to materialize.

    Returns:
        tuple[list[Fault], dict[str, object]]: Faults and exact population/count metadata.
    """
    if not math.isfinite(percent) or not 0 <= percent <= 100 or limit < 1:
        raise ValueError("bug percent must be 0..100 and max bugs must be positive")
    if not orders or len(set(orders)) != len(orders) or not all(1 <= k <= complexity for k in orders):
        raise ValueError("bug orders must be distinct and within the input complexity")
    populations = {k: math.comb(complexity, k) * 2**k for k in sorted(orders)}
    counts = {k: int(Fraction(str(percent)) * size / 100) for k, size in populations.items()}
    if sum(counts.values()) > limit:
        raise ValueError("requested bug population exceeds --max-bugs; reduce percent or orders")
    rng = random.Random(seed)
    result: list[Fault] = []
    for order, population in populations.items():
        selected: set[int] = set()
        while len(selected) < counts[order]:
            selected.add(rng.randrange(population))
        for encoded in sorted(selected):
            rank, pattern = divmod(encoded, 2**order)
            subset: list[int] = []
            start = 0
            for remaining in range(order - 1, -1, -1):
                for candidate in range(start, complexity - remaining):
                    block = math.comb(complexity - candidate - 1, remaining)
                    if rank < block:
                        subset.append(candidate)
                        start = candidate + 1
                        break
                    rank -= block
            result.append(
                Fault(
                    f"bug{len(result):04d}",
                    {f"input{bit:03d}": bool(pattern & (1 << position)) for position, bit in enumerate(subset)},
                )
            )
    return result, {
        "requested_percent": percent,
        "seed": seed,
        "definition": "percentage of path-subset / Boolean-pattern pairs per order; rounded down",
        "orders": [
            {
                "order": k,
                "population": str(populations[k]),
                "injected": counts[k],
                "actual_percent": 100 * counts[k] / populations[k],
            }
            for k in populations
        ],
        "total_faults": len(result),
        "faults": [asdict(defect) for defect in result],
    }
