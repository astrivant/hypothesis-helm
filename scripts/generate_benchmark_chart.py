"""
Generate a finite Helm chart whose emitted scalar follows discretized normal quantiles.
"""

import argparse
import json
import math
import re
from pathlib import Path
from statistics import NormalDist, mean, pstdev


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
        force (bool): Explicitly allow replacing generated files in an existing directory.

    Returns:
        dict[str, object]: Complete generator settings and actual finite distribution statistics.
    """
    if not 1 <= input_complexity <= 1024:
        raise ValueError("input complexity must be between 1 and 1024")
    if not math.isfinite(mean_value) or not math.isfinite(stddev) or stddev <= 0:
        raise ValueError("mean must be finite and stddev must be finite and positive")
    if output_bins is None:
        output_bins = 2 ** min(8, max(1, input_complexity // 2))
    if output_bins < 2 or output_bins > 1024 or output_bins & (output_bins - 1):
        raise ValueError("output bins must be a power of two between 2 and 1024")
    active = output_bins.bit_length() - 1
    if active > input_complexity or not 0 <= precision <= 12:
        raise ValueError("quantile bits must fit input complexity; precision must be 0..12")
    if any(value is not None and not math.isfinite(value) for value in (lower, upper)):
        raise ValueError("truncation bounds must be finite")
    if lower is not None and upper is not None and lower >= upper:
        raise ValueError("lower truncation bound must be less than upper")
    distribution = NormalDist(mean_value, stddev)
    start = distribution.cdf(lower) if lower is not None else 0.0
    stop = distribution.cdf(upper) if upper is not None else 1.0
    if not 0 <= start < stop <= 1:
        raise ValueError("truncation interval has no numerically representable probability mass")
    quantiles = [
        distribution.inv_cdf(start + (stop - start) * (index + 0.5) / output_bins)
        for index in range(output_bins)
    ]
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
    name = re.sub("[^a-z0-9-]", "-", output.name.lower()).strip("-") or "benchmark"
    (output / "Chart.yaml").write_text(
        f"apiVersion: v2\nname: {name}\nversion: 0.1.0\n"
        "description: Generated finite normal-quantile permutation benchmark\n"
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
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ .Release.Name }}\ndata:\n"
        + '  value: "'
        + branch(0, 0)
        + '"\n'
    )
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
        force=args.force,
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in spec.items()
                if key not in ("output_strings", "histogram_edges")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
