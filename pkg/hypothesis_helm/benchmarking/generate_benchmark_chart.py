"""
Generate a finite Helm chart whose emitted scalar follows discretized normal quantiles.
"""

import argparse
import json
import math
import re
from pathlib import Path
from statistics import NormalDist, mean, pstdev
from textwrap import dedent

from hypothesis_helm.benchmarking.faults import select_faults, write_faults
from hypothesis_helm.benchmarking.mixtures import normalized_weights, write_mixture
from hypothesis_helm.benchmarking.structures import STRUCTURES, write_structure
from hypothesis_helm.benchmarking.topology import write_topology


def generate(
    output: Path,
    *,
    input_complexity: int = 100,
    mean_value: float = 0,
    stddev: float = 1,
    output_bins: int | None = None,
    precision: int = 6,
    lower: float | None = None,
    upper: float | None = None,
    bug_percent: float = 0,
    bug_orders: tuple[int, ...] | None = None,
    bug_seed: int = 2026,
    max_bugs: int = 1000,
    structure: str | None = None,
    topology_components: int = 0,
    topology_weights: dict[str, float] | None = None,
    topology_seed: int = 2026,
    topology_depth_weights: dict[int, float] | None = None,
    topology: bool = False,
    topology_opaque: bool = False,
    force: bool = False,
) -> dict[str, object]:
    """
    Build a generic Boolean-input chart using only compiler-supported template branches.

    Uniform active bits select midpoint quantiles of a possibly truncated normal.
    Remaining fields do not affect output. Finite quantization and rounding are explicit.

    Args:
        output (Path): Chart directory to create.
        input_complexity (int): Number of independent required Boolean schema inputs.
        mean_value (float): Mean of the underlying normal distribution.
        stddev (float): Positive standard deviation of the underlying normal distribution.
        output_bins (int | None): Power-of-two quantile count, or up to 256 chosen to fit.
        precision (int): Decimal places in the actual emitted scalar.
        lower (float | None): Optional lower truncation bound.
        upper (float | None): Optional upper truncation bound.
        bug_percent (float): Percentage of path-interaction assignments to corrupt.
        bug_orders (tuple[int, ...] | None): Trigger orders; defaults to two through six.
        bug_seed (int): Reproducible seed for fault placement.
        max_bugs (int): Maximum injected fault population to materialize.
        structure (str | None): Isolated structural profile for the strategy matrix.
        topology_components (int): Number of sampled structural components; zero disables mixtures.
        topology_weights (dict[str, float] | None): Relative category weights; default uniform.
        topology_seed (int): Seed for component types and shared input wiring.
        topology_depth_weights (dict[int, float] | None): Added gate depth distribution.
        topology (bool): Generate six additional live Boolean roles and resource projections.
        topology_opaque (bool): Add a loop to exercise conservative unknown-region handling.
        force (bool): Explicitly allow replacing generated files in an existing directory.

    Returns:
        dict[str, object]: Complete generator settings and actual finite distribution statistics.
    """
    if not 1 <= input_complexity <= 1024:
        raise ValueError("input complexity must be between 1 and 1024")
    defects, bug_spec = select_faults(
        input_complexity,
        bug_orders if bug_orders is not None else tuple(range(min(2, input_complexity), min(6, input_complexity) + 1)),
        bug_percent,
        bug_seed,
        max_bugs,
    )
    if not math.isfinite(mean_value) or not math.isfinite(stddev) or stddev <= 0:
        raise ValueError("mean must be finite and stddev must be finite and positive")
    if output_bins is None:
        output_bins = 2 ** min(8, max(1, input_complexity // 2))
    if output_bins < 2 or output_bins > 1024 or output_bins & (output_bins - 1):
        raise ValueError("output bins must be a power of two between 2 and 1024")
    active = output_bins.bit_length() - 1
    if topology_components < 0 or topology_components > 1024:
        raise ValueError("topology components must be between 0 and 1024")
    if topology_weights is not None and not topology_components:
        raise ValueError("topology weights require --topology-components")
    if topology_depth_weights is not None:
        if not topology_components or not topology_depth_weights:
            raise ValueError("depth weights require components and a nonempty distribution")
        if any(
            not isinstance(depth, int) or not 1 <= depth <= input_complexity - active - 1 or not math.isfinite(weight) or weight < 0
            for depth, weight in topology_depth_weights.items()
        ):
            raise ValueError("gate depths must fit spare Boolean inputs; weights must be finite and nonnegative")
        total = sum(topology_depth_weights.values())
        if not math.isfinite(total) or total <= 0:
            raise ValueError("depth weights must have a finite positive sum")
    if topology_components:
        normalized_weights(topology_weights)
        if active + 5 > input_complexity or structure or topology or topology_opaque or bug_percent:
            raise ValueError("topology mixtures require five spare inputs and no other structural or bug mode")
    if active > input_complexity or not 0 <= precision <= 12:
        raise ValueError("quantile bits must fit input complexity; precision must be 0..12")
    if structure is not None and (
        structure not in STRUCTURES or active + 4 > input_complexity or topology or topology_opaque or bug_percent
    ):
        raise ValueError("structure requires four spare inputs and cannot combine with topology or bugs")
    if (topology or topology_opaque) and active + 6 > input_complexity:
        raise ValueError("topology requires six inputs beyond the quantile selector bits")
    if any(value is not None and not math.isfinite(value) for value in (lower, upper)):
        raise ValueError("truncation bounds must be finite")
    if lower is not None and upper is not None and lower >= upper:
        raise ValueError("lower truncation bound must be less than upper")
    distribution = NormalDist(mean_value, stddev)
    start = distribution.cdf(lower) if lower is not None else 0.0
    stop = distribution.cdf(upper) if upper is not None else 1.0
    if not 0 <= start < stop <= 1:
        raise ValueError("truncation interval has no numerically representable probability mass")
    quantiles = [distribution.inv_cdf(start + (stop - start) * (index + 0.5) / output_bins) for index in range(output_bins)]
    if not all(math.isfinite(value) for value in quantiles):
        raise ValueError("distribution quantiles exceed finite floating-point range")
    strings = [f"{value:.{precision}f}" for value in quantiles]
    values = [float(value) for value in strings]
    if lower is not None and min(values) < lower or upper is not None and max(values) > upper:
        raise ValueError("rounding crosses truncation bounds; increase --precision")
    low, high = min(values), max(values)
    if low == high:
        raise ValueError("rounding collapses all outputs; increase --precision or --stddev")
    edges = [low + (high - low) * index / 32 for index in range(33)]
    spec: dict[str, object] = {
        "format_version": 2,
        "workload": "normal-quantile-v2",
        "input_complexity": input_complexity,
        "active_inputs": active,
        "unused_inputs": input_complexity - active,
        "possible_inputs": str(2**input_complexity),
        "mean": mean_value,
        "stddev": stddev,
        "lower": lower,
        "upper": upper,
        "output_bins": output_bins,
        "precision": precision,
        "output_strings": strings,
        "unique_emitted_values": len(set(strings)),
        "discrete_mean": mean(values),
        "discrete_stddev": pstdev(values),
        "histogram_edges": edges,
        "interpretation": "midpoint normal quantiles, not a continuous or exactly Gaussian output",
    }

    def branch(bit: int, index: int) -> str:
        """
        Lower the quantile lookup to direct Boolean control flow.

        Args:
            bit (int): Next Boolean selector bit.
            index (int): Quantile index assembled from previous branch decisions.

        Returns:
            str: Helm template emitting exactly one formatted scalar.
        """
        if bit == active:
            return strings[index]
        return (
            "{{ if .Values.input"
            + f"{bit:03d}"
            + " }}"
            + branch(bit + 1, index | (1 << bit))
            + "{{ else }}"
            + branch(bit + 1, index)
            + "{{ end }}"
        )

    if output.exists() and any(output.iterdir()) and not force:
        raise ValueError(f"{output} is not empty; choose another directory or use --force")
    (output / "templates").mkdir(parents=True, exist_ok=True)
    if force:
        for previous in (output / "templates").glob("structure-component-*.yaml"):
            previous.unlink()
    name = re.sub("[^a-z0-9-]", "-", output.name.lower()).strip("-") or "benchmark"
    (output / "Chart.yaml").write_text(
        dedent(
            f"""
            apiVersion: v2
            name: {name}
            version: 0.1.0
            description: Generated finite normal-quantile permutation benchmark
            """
        ).removeprefix("\n")
    )
    fields = [f"input{index:03d}" for index in range(input_complexity)]
    (output / "values.yaml").write_text("".join(f"{name}: false\n" for name in fields))
    (output / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": fields,
                "properties": {name: {"type": "boolean"} for name in fields},
            },
            indent=2,
        )
        + "\n"
    )
    (output / "templates/configmap.yaml").write_text(
        dedent(
            f"""
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: {{{{ .Release.Name }}}}
            data:
              value: "{branch(0, 0)}"
            """
        ).removeprefix("\n")
    )
    if structure is not None:
        spec["structure"] = write_structure(output, structure, active)
        spec["possible_inputs"] = str((3 if structure == "boundaries" else 2) * 2 ** (input_complexity - 1))
        spec["unused_inputs"] = (
            input_complexity
            - active
            - {
                "constraints": 2,
                "control-flow": 2,
                "dependencies": 1,
                "interactions": 4,
                "equivalence": 0,
                "boundaries": 1,
            }[structure]
        )
    elif force:
        (output / "templates/structure.yaml").unlink(missing_ok=True)
    if topology_components:
        mixture = write_mixture(
            output,
            active,
            input_complexity,
            topology_components,
            topology_weights,
            topology_seed,
            topology_depth_weights,
        )
        spec["structure"] = mixture
        spec["possible_inputs"] = str((3 if mixture["numeric_input"] is not None else 2) * 2 ** (input_complexity - 1))
        spec["domain_note"] = "Cartesian input count before cross-input constraints"
        spec["unused_inputs"] = None
    if topology or topology_opaque:
        spec["topology"] = write_topology(output, active, topology_opaque)
        spec["unused_inputs"] = input_complexity - active - 6
        spec["topology_inputs"] = 6
    elif force:
        (output / "templates/topology.yaml").unlink(missing_ok=True)
    if bug_percent:
        spec["bugs"] = bug_spec
    if defects:
        write_faults(output, defects)
    elif force:
        (output / "templates/faults.yaml").unlink(missing_ok=True)
    (output / "benchmark.json").write_text(json.dumps(spec, indent=2) + "\n")
    return spec


def main(argv: list[str] | None = None) -> int:
    """
    Generate a chart from user-controlled input complexity and distribution parameters.

    Args:
        argv (list[str] | None): CLI arguments or process arguments.

    Returns:
        int: Zero after writing a complete chart and distribution metadata.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-complexity", type=int, default=100)
    parser.add_argument("--mean", type=float, default=0)
    parser.add_argument("--stddev", type=float, default=1)
    parser.add_argument(
        "--output-bins",
        type=int,
        default=None,
        help="power-of-two quantile count; auto selects up to 256 to fit input complexity",
    )
    parser.add_argument("--precision", type=int, default=6)
    parser.add_argument("--lower", type=float)
    parser.add_argument("--upper", type=float)
    parser.add_argument(
        "--bug-percent",
        type=float,
        default=0,
        help="percent of path-interaction assignments seeded with faults",
    )
    parser.add_argument("--bug-orders", help="comma-separated trigger orders; default: 2 through 6")
    parser.add_argument("--bug-seed", type=int, default=2026)
    parser.add_argument("--max-bugs", type=int, default=1000)
    parser.add_argument(
        "--topology",
        action="store_true",
        help="add gated resources and interacting downstream projections",
    )
    parser.add_argument(
        "--topology-opaque",
        action="store_true",
        help="also add an unsupported loop for fallback measurements",
    )
    parser.add_argument("--structure", choices=STRUCTURES, help="generate an isolated structural matrix case")
    parser.add_argument(
        "--topology-components",
        type=int,
        default=0,
        help="sample this many structural components with shared input wiring",
    )
    parser.add_argument(
        "--topology-weight",
        action="append",
        default=[],
        metavar="NAME=WEIGHT",
        help="relative category weight; repeat; omitted categories get zero weight",
    )
    parser.add_argument("--topology-seed", type=int, default=2026)
    depths = parser.add_mutually_exclusive_group()
    depths.add_argument("--topology-depth", type=int, help="added Boolean gate depth per component")
    depths.add_argument(
        "--topology-depth-weight",
        action="append",
        metavar="DEPTH=WEIGHT",
        help="sample added gate depths with relative weights; repeat to define a mix",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    spec = generate(
        args.output,
        input_complexity=args.input_complexity,
        mean_value=args.mean,
        stddev=args.stddev,
        output_bins=args.output_bins,
        precision=args.precision,
        lower=args.lower,
        upper=args.upper,
        bug_percent=args.bug_percent,
        bug_orders=tuple(int(value) for value in args.bug_orders.split(",")) if args.bug_orders else None,
        bug_seed=args.bug_seed,
        max_bugs=args.max_bugs,
        structure=args.structure,
        topology_components=args.topology_components,
        topology_weights={name: float(weight) for name, weight in (item.split("=", 1) for item in args.topology_weight)}
        if args.topology_weight
        else None,
        topology_seed=args.topology_seed,
        topology_depth_weights={args.topology_depth: 1.0}
        if args.topology_depth is not None
        else {int(depth): float(weight) for depth, weight in (item.split("=", 1) for item in args.topology_depth_weight)}
        if args.topology_depth_weight
        else None,
        topology=args.topology,
        topology_opaque=args.topology_opaque,
        force=args.force,
    )
    print(
        json.dumps(
            {key: value for key, value in spec.items() if key not in ("output_strings", "histogram_edges")},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
