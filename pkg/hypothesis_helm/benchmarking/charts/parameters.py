"""
Load typed benchmark parameters and reproduce a retained chart configuration.
"""

from attrs import frozen

from hypothesis_helm.benchmarking.charts.stress import Stress


@frozen
class Parameters:
    """
    Describe the common chart generator without embedding generated Helm sources.

    Attributes:
        input_complexity (int): Number of variable inputs outside the fixed stress profile.
        mean_value (float): Normal distribution mean.
        stddev (float): Normal distribution standard deviation.
        output_bins (int | None): Number of discrete quantile outputs.
        precision (int): Output decimal places.
        lower (float | None): Lower distribution bound.
        upper (float | None): Upper distribution bound.
        bug_percent (float): Seeded interaction fault percentage.
        bug_orders (tuple[int, ...] | None): Fault interaction orders.
        bug_seed (int): Fault placement seed.
        max_bugs (int): Limit on materialized faults.
        structure (str | None): Isolated topology category.
        topology_components (int): Mixed topology component count.
        topology_weights (dict[str, float] | None): Relative category weights.
        topology_seed (int): Stable component placement seed.
        topology_depth_weights (dict[int, float] | None): Gate depth distribution.
        topology (bool): Enable the compact gated-resource profile.
        topology_opaque (bool): Include an unsupported loop to measure conservative fallback.
        stress (Stress | None): Combined worst-case controls.
        readable_inputs (bool): Name variable fields after their downstream roles.
    """

    input_complexity: int = 100
    mean_value: float = 0
    stddev: float = 1
    output_bins: int | None = None
    precision: int = 6
    lower: float | None = None
    upper: float | None = None
    bug_percent: float = 0
    bug_orders: tuple[int, ...] | None = None
    bug_seed: int = 2026
    max_bugs: int = 1000
    structure: str | None = None
    topology_components: int = 0
    topology_weights: dict[str, float] | None = None
    topology_seed: int = 2026
    topology_depth_weights: dict[int, float] | None = None
    topology: bool = False
    topology_opaque: bool = False
    stress: Stress | None = None
    readable_inputs: bool = True
