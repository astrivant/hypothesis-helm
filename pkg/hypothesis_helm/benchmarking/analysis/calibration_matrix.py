"""
Cross-check nearby sampling profiles against fully observed calibration populations.
"""

import csv
import hashlib
import json
import statistics
from functools import partial
from pathlib import Path

from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.reporting.variation import repeated_line
from hypothesis_helm.execution.aggressive import changed_fields, matching_profiles
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.combinations import trim_values
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence

METRIC = "maximum-relative-coordinate-change-v1"
RADII = (0.1, 0.2, 0.35, 0.5)


def evaluate(output: Path, document: dict[str, object]) -> None:
    """
    Enable nearby matching only when calibration cross-checks show useful case reduction.

    Exact target descriptors are removed from lookup during each nearby-profile check.
    This reuses the calibration charts, so it is not independent validation of generalization.

    Args:
        output (Path): Destination for the evidence matrix and plots.
        document (dict[str, object]): Fully rendered generated-chart populations and sample floors.

    Returns:
        None: Decision, matrix and graph artifacts are written and attached to the calibration.
    """
    profiles = [mapping(row) for row in sequence(document["profiles"])]
    rows: list[dict[str, object]] = []
    for cell in profiles:
        reference = mapping(cell["reference"])
        defaults = mapping(reference["defaults"])
        cases = [mapping(row) for row in sequence(reference["cases"])]
        values = [mapping(row["values"]) for row in cases]
        bugs = {configuration_key(mapping(row["values"])): set(sequence(row["bugs"])) for row in cases}
        memberships = {configuration_key(mapping(row["values"])): str(row["region"]) for row in cases}
        groups: dict[str, list[dict[str, object]]] = {}
        for value in values:
            groups.setdefault(memberships[configuration_key(value)], []).append(value)
        evidence = mapping(cell["evidence"])
        trials, start = int(str(evidence["trials"])), int(str(evidence["seed_start"]))
        exact = [other for other in profiles if other["descriptor"] == cell["descriptor"]]
        settings: list[tuple[str, float, list[dict[str, object]], str]] = [("filter", 0, [], "ordinary"), ("exact", 0, exact, "exact")]
        alternatives = [other for other in profiles if other["descriptor"] != cell["descriptor"]]
        for radius in RADII:
            available = {**document, "profiles": alternatives, "approximation": {"enabled": True, "radius": radius, "metric": METRIC}}
            neighbors, method, _ = matching_profiles(available, mapping(cell["descriptor"]))
            settings.append((f"nearby-{radius:g}", radius, neighbors, method))
        observations: dict[str, list[tuple[int, int, float, bool]]] = {name: [] for name, *_ in settings}
        for seed in range(start, start + trials):
            retained = {configuration_key(value) for members in groups.values() for value in trim_values(members, 2, seed)}
            eligible = [value for value in values if configuration_key(value) in retained]
            protected: set[str] = set()
            seen: set[str] = set()
            for value in eligible:
                identity = configuration_key(value)
                region = memberships[identity]
                if region not in seen:
                    protected.add(identity)
                    seen.add(region)
            for name, _, matches, _ in settings:
                minimum = max((int(str(row["minimum_cases"])) for row in matches), default=1)
                field_floor = max((int(str(row["minimum_fields"])) for row in matches), default=0)
                selected, selection = Sampling(70 if matches else 100, minimum).select(
                    eligible,
                    configuration_key,
                    seed,
                    protected=protected,
                    fields=partial(changed_fields, defaults),
                    minimum_fields=field_floor,
                )
                found = set(sequence(reference["baseline_bugs"])) | set().union(*(bugs[configuration_key(value)] for value in selected))
                recall = len(found) / int(str(evidence["known_bugs"]))
                field_ok = int(str(selection["selected_fields"])) >= int(str(cell["minimum_fields"]))
                observations[name].append((len(selected), len(eligible), recall, field_ok))
        for name, radius, matches, method in settings:
            samples = observations[name]
            rows.append(
                {
                    "case": cell["case"],
                    "strategy": name,
                    "radius": radius,
                    "match": method,
                    "matched": bool(matches),
                    "maximum_score": mapping(mapping(cell["descriptor"])["features"])["maximum_score"],
                    "gate_depth": mapping(mapping(cell["descriptor"])["features"])["gate_depth"],
                    "input_fields": mapping(mapping(cell["descriptor"])["features"])["input_fields"],
                    "eligible": samples[0][1],
                    "mean_selected": statistics.mean(row[0] for row in samples),
                    "mean_extra_omitted": statistics.mean(row[1] - row[0] for row in samples),
                    "mean_bug_recall": statistics.mean(row[2] for row in samples),
                    "known_bugs": int(str(evidence["known_bugs"])),
                    "mean_bugs_found": statistics.mean(row[2] for row in samples) * int(str(evidence["known_bugs"])),
                    "minimum_bug_recall": min(row[2] for row in samples),
                    "target_successes": sum(row[2] >= 0.96 and row[3] for row in samples),
                    "trials": trials,
                    "protected_regions": len(groups),
                }
            )
    approved = []
    radius_results = []
    for radius in RADII:
        matched = [row for row in rows if row["radius"] == radius and row["matched"]]
        useful = [row for row in matched if float(str(row["mean_extra_omitted"])) > 0]
        passes = len(useful) >= 2 and all(
            int(str(row["trials"])) >= 100 and int(str(row["target_successes"])) / int(str(row["trials"])) >= 0.95 for row in matched
        )
        if passes:
            approved.append(radius)
        radius_results.append({"radius": radius, "matched_cases": len(matched), "useful_cases": len(useful), "passed": passes})
    policy: dict[str, object] = {
        "enabled": bool(approved),
        "radius": min(approved) if approved else 0,
        "metric": METRIC,
        "range": "each coordinate must remain within the measured range of compatible domain types and filter settings",
        "floor": "maximum case and field floors among neighbors within the selected radius",
        "evidence": radius_results,
        "independent_validation": False,
        "scope": (
            "Cross-checks reuse calibration fixtures with each target descriptor excluded from lookup; not an arbitrary-chart guarantee."
        ),
    }
    document["approximation"] = policy
    document["id"] = hashlib.sha256(configuration_key({"profiles": profiles, "approximation": policy}).encode()).hexdigest()
    (output / "calibration.json").write_text(json.dumps(document, indent=2) + "\n")
    (output / "matrix.json").write_text(json.dumps({"policy": policy, "rows": rows}, indent=2) + "\n")
    (output / "results.json").write_text(
        json.dumps({"metadata": document["metadata"], "rows": [{**row, "status": "complete"} for row in rows]}, indent=2) + "\n"
    )
    with (output / "matrix.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(output, rows, policy)


def plot(output: Path, rows: list[dict[str, object]], policy: dict[str, object]) -> None:
    """
    Plot retained counts, defect recall and variation across nearby generated structures.

    Args:
        output (Path): Matrix artifact directory.
        rows (list[dict[str, object]]): Measured selection outcomes over known rendered populations.
        policy (dict[str, object]): Decision to enable or disable nearby-profile lookup.

    Returns:
        None: Heatmaps and a readable matrix expose both reductions and fallback cases.
    """
    import numpy as np
    from matplotlib import pyplot as plt

    cases = list(dict.fromkeys(str(row["case"]) for row in rows))
    strategies = list(dict.fromkeys(str(row["strategy"]) for row in rows))
    indexed = {(row["case"], row["strategy"]): row for row in rows}
    figure, axes = plt.subplots(1, 2, figsize=(13, max(6, len(cases) * 0.24)))
    for axis, metric, title in (
        (axes[0], "mean_selected", "Eligible cases retained (%)"),
        (axes[1], "mean_bug_recall", "Distinct known bugs found (%)"),
    ):
        data = np.array(
            [
                [
                    100
                    * float(str(indexed[case, strategy][metric]))
                    / (float(str(indexed[case, strategy]["eligible"])) if metric == "mean_selected" else 1)
                    for strategy in strategies
                ]
                for case in cases
            ]
        )
        picture = axis.imshow(data, vmin=0, vmax=100, aspect="auto", cmap="viridis")
        axis.set_xticks(range(len(strategies)), strategies, rotation=40, ha="right")
        axis.set_yticks(range(len(cases)), cases, fontsize=7)
        axis.set_title(title)
        figure.colorbar(picture, ax=axis)
    finish(
        figure, output, "matching-matrix", "Nearby columns exclude the target descriptor from lookup; fallback retains all eligible cases."
    )
    figure, axis = plt.subplots(figsize=(9, 5))
    exact = [row for row in rows if row["strategy"] == "exact"]
    for index, fields in enumerate(sorted({int(str(row["input_fields"])) for row in exact})):
        subset = [row for row in exact if int(str(row["input_fields"])) == fields]
        depths = sorted({int(str(row["gate_depth"])) for row in subset})
        counts = [[float(str(row["mean_selected"])) for row in subset if int(str(row["gate_depth"])) == depth] for depth in depths]
        repeated_line(axis, depths, counts, f"{fields} input fields", f"C{index % 10}")
    axis.set(xlabel="Maximum gate depth", ylabel="Selected cases after filtering and sampling")
    axis.legend()
    axis.grid(alpha=0.2)
    finish(
        figure,
        output,
        "profile-variation",
        "Variation is across defect-placement means, not individual seeds; maximum output score alone does not determine these counts.",
    )
    lines = [
        "# Sampling evidence matrix",
        "",
        "[Calibration](README.md)",
        "",
        "![Selection and known-bug recall](matching-matrix.png)",
        "",
        "![Nearby profile variation](profile-variation.png)",
        "",
        f"Nearby matching enabled: **{policy['enabled']}**; selected maximum relative coordinate change: **{policy['radius']}**.",
        "The threshold is chosen from the same calibration study, not independent validation.",
        "",
        "Each nearby check removes every exact match for the target profile. Unknown or out-of-range targets keep ordinary filtering.",
        "Protected output regions are preserved. These results do not establish bug recall for random sampling alone.",
        "",
        "| Case | Strategy | Match | Selected / eligible | Mean known bugs found | Seeds meeting bug and field targets |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['strategy']} | {row['match']} | {float(str(row['mean_selected'])):.1f} / {row['eligible']} | "
            f"{float(str(row['mean_bugs_found'])):.1f} / {row['known_bugs']} ({float(str(row['mean_bug_recall'])):.1%}) | "
            f"{row['target_successes']} / {row['trials']} |"
        )
    lines += ["", "[CSV](matrix.csv) · [JSON and matching decision](matrix.json)", ""]
    (output / "MATRIX.md").write_text(with_contents("\n".join(lines)))
