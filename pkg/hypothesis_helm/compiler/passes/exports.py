"""
Export deterministic concrete baselines beside every discovered application chart.
"""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis_helm.charts.scan import discover_charts
from hypothesis_helm.compiler.passes.inputs import load_input_chart
from hypothesis_helm.compiler.passes.minimum import export_minimal


def export_repository(
    source: Path,
    filename: str = "values-minimal.yaml",
    *,
    helm: str = "helm",
    timeout: float = 30,
    budget: float = 30,
    files_list: Path | None = None,
) -> int:
    """
    Export each chart independently and optionally record its YAML and proof paths for staging.

    Args:
        source (Path): Local repository or chart directory.
        filename (str): Basename placed in each discovered chart directory.
        helm (str): Helm executable.
        timeout (float): Per-command timeout in seconds.
        budget (float): Verification budget per chart in seconds.
        files_list (Path | None): NUL-delimited absolute YAML and proof paths for safe Git pathspec input.

    Returns:
        int: Zero when every application chart exports successfully, one otherwise.
    """
    if (
        not filename
        or filename in {".", "..", "values.yaml", "Chart.yaml", "values.schema.json"}
        or "/" in filename
        or "\\" in filename
        or "\0" in filename
        or not filename.endswith((".yaml", ".yml"))
    ):
        raise ValueError("--filename must be a YAML basename distinct from source chart inputs")
    source = source.resolve()
    records = discover_charts(source)
    if not records:
        raise ValueError(f"No Chart.yaml files found under {source}")
    exported: list[Path] = []
    failed = False
    exported_charts = 0
    for record in records:
        if record["status"] != "pending":
            failed = True
            continue
        if record.get("kind") == "library":
            record.update(status="not-applicable", reason="Library has no standalone manifests")
            continue
        chart_path = source / str(record["chart"])
        target = chart_path / filename
        try:
            if target.is_symlink():
                raise ValueError("Minimal-values destination must not be a symbolic link")
            result = export_minimal(load_input_chart(chart_path), target, helm=helm, timeout=timeout, budget=budget)
            record.update(status="exported", export=result)
            exported.extend((target.resolve(), Path(str(result["proof"])).resolve()))
            exported_charts += 1
        except Exception as exc:
            record.update(status="failed", error=str(exc))
            failed = True
    if files_list is not None:
        files_list.parent.mkdir(parents=True, exist_ok=True)
        files_list.write_bytes(b"".join(str(path).encode() + b"\0" for path in exported))
    print(json.dumps({"charts": records, "exported": exported_charts}, indent=2))
    return int(failed)
