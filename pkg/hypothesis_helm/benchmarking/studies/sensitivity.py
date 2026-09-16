"""
Measure a dense mutation matrix on the shared benchmark chart.
"""

import argparse
import csv
import json
import math
import shutil
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from hypothesis_helm.analysis.cli import main as measure
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.charts import yamlio
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Measure every single flip and unordered pair at a reproducible mixed baseline.

    Args:
        argv (list[str] | None): Explicit arguments or process command line.
        workspace (FixtureWorkspace | None): Owner of the shared generated chart.

    Returns:
        int: Diagnostic exit status, preserving incomplete measurements.
    """
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=int, default=48, help="distinct Boolean paths; all unordered pairs are measured")
    parser.add_argument("--components", type=int, default=64, help="shared chart structures wired across the inputs")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--output", type=Path, help="fresh output directory; omit to update studies/sensitivity automatically")
    args = parser.parse_args(argv)
    if not 9 <= args.inputs <= 1024 or not 1 <= args.components <= 1024:
        parser.error("inputs must be 9..1024 and components must be 1..1024")
    publish = args.output is None
    if publish:
        args.output = Path(f"studies/sensitivity/runs/{time.time_ns()}")
    if args.output.exists():
        parser.error("choose a fresh output directory")
    budget = format(Decimal(str(args.time_limit)), "f")
    print(f"Sensitivity: {args.inputs} mutations, {math.comb(args.inputs, 2)} pairs, {args.inputs} sequence steps", flush=True)
    with tempfile.TemporaryDirectory(prefix="sensitivity-inputs-") as temporary:
        source = Path(temporary)
        generate(
            source / "chart",
            input_complexity=args.inputs,
            output_bins=16,
            topology_components=args.components,
            topology_weights={"control-flow": 1, "dependencies": 1, "interactions": 1, "equivalence": 1},
            topology_seed=args.seed,
            workspace=workspace,
        )
        chart = workspace.chart
        defaults = mapping(yamlio.load((chart / "values.yaml").read_text()))
        baseline = {name: index % 2 == 0 for index, name in enumerate(defaults)}
        (chart / "values.yaml").write_text(yamlio.dump(baseline))
        mutations = [{"name": name, "path": [name], "value": not value} for name, value in baseline.items()]
        mutation_file = source / "mutations.json"
        mutation_file.write_text(json.dumps(mutations, indent=2) + "\n")
        status = measure(
            [
                str(chart),
                "--mutations",
                str(mutation_file),
                "--output",
                str(args.output),
                "--plot",
                "--max-mutations",
                str(args.inputs),
                "--max-pairs",
                str(math.comb(args.inputs, 2)),
                "--time-limit",
                budget,
            ]
        )
        shutil.copy2(mutation_file, args.output / "mutations.json")
        shutil.copy2(chart / "benchmark-parameters.yaml", args.output / "parameters.yaml")
        (args.output / "chart-inputs.json").write_text(
            json.dumps({str(path.relative_to(chart)): path.read_text() for path in sorted(chart.rglob("*")) if path.is_file()}, indent=2)
            + "\n"
        )
    result_path = args.output / "results.json"
    result = mapping(json.loads(result_path.read_text()))
    result["metadata"] = {
        "code_sha256": code_digest(),
        "helm": Processes().run(["helm", "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
        "time_limit_seconds": args.time_limit,
        "inputs": args.inputs,
        "components": args.components,
        "seed": args.seed,
        "baseline": "alternating true/false in generator field order",
        "expected_pairs": math.comb(args.inputs, 2),
    }
    rows = [
        {"mutation": row["name"], "distance": row.get("distance"), "status": "passed" if row["status"] == "rendered" else row["status"]}
        for entry in sequence(result["mutations"])
        for row in [mapping(entry)]
    ]
    result["rows"] = rows
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    with (args.output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["mutation", "distance", "status"])
        writer.writeheader()
        writer.writerows(rows)
    with (args.output / "README.md").open("a") as stream:
        stream.write(
            f"\n## Reproduce this study\n\n"
            f"Shared benchmark chart: {args.inputs} Boolean inputs, {args.components} structural components, seed {args.seed}. "
            "The baseline alternates true and false; each mutation flips one distinct path. "
            "This measures one baseline, not the entire configuration space.\n\n"
            "Exact chart sources are retained in [chart-inputs.json](chart-inputs.json).\n\n"
            "This command updates the published study automatically after a successful run. "
            "Use --output to keep results separate; incomplete runs do not replace the published study.\n\n"
            "```bash\n"
            f"bash scripts/project-run.sh hypothesis-helm-benchmark sensitivity --inputs {args.inputs} "
            f"--components {args.components} --seed {args.seed} --time-limit {budget}\n"
            "```\n"
        )
    readme = args.output / "README.md"
    readme.write_text(with_contents(readme.read_text()))
    if publish:
        successful = (
            status == 0
            and len(rows) == args.inputs
            and all(row["status"] == "passed" for row in rows)
            and len(sequence(result["interactions"])) == math.comb(args.inputs, 2)
            and all("mixed_difference_l1" in mapping(row) for row in sequence(result["interactions"]))
            and len(sequence(result["sequence"])) == args.inputs
            and all("cumulative_path_length" in mapping(row) for row in sequence(result["sequence"]))
        )
        if successful:
            target = Path("studies/sensitivity")
            for artifact in args.output.iterdir():
                if artifact.is_file():
                    shutil.copy2(artifact, target / artifact.name)
            print(f"Published sensitivity study: {target / 'README.md'}; retained run: {args.output}")
        else:
            print(f"Published study unchanged: measurements incomplete or invalid; retained run: {args.output}")
            return 1
    return status
