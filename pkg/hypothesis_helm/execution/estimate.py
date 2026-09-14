"""
Estimate selected property work without executing fixtures or property examples.
"""

import ast
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from hypothesis_helm.execution.cache import fingerprint, read_outcomes, seed_key
from hypothesis_helm.execution.environment import in_ci
from hypothesis_helm.execution.parallel import worker_limit
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import DEFAULT_SAMPLING, Sampling
from hypothesis_helm.execution.sampling import ENVIRONMENT as SAMPLING_ENVIRONMENT
from hypothesis_helm.execution.sampling import REPORT as SAMPLING_REPORT
from hypothesis_helm.execution.structure import inspect_structure
from hypothesis_helm.execution.traversal import validate_strategy
from hypothesis_helm.integrations.sharding import Shard


def budgets(module: Path) -> dict[str, int | None]:
    """
    Read literal Hypothesis example budgets from generated property decorators.

    Args:
        module (Path): Python suite source.

    Returns:
        dict[str, int | None]: Function names and known successful-example budgets.
    """
    result: dict[str, int | None] = {}
    for node in ast.parse(module.read_text()).body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        result[node.name] = None
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id != "settings":
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "max_examples" and isinstance(keyword.value, ast.Constant):
                        value = keyword.value.value
                        if isinstance(value, int) and not isinstance(value, bool):
                            result[node.name] = value
    return result


def estimate_suite(
    directory: Path,
    *,
    suite_location: Path | None = None,
    seed: int = 0,
    traversal_strategy: str = "random",
    sampling: Sampling = DEFAULT_SAMPLING,
    match: str | None = None,
    jobs: int | Literal["auto"] = "auto",
    shard: Shard | None = None,
    artifact_dir: Path | None = None,
    cache_dir: Path | None = None,
    cache: bool = True,
    rerun: str = "auto",
    schema_state: dict[str, object] | None = None,
) -> dict[str, object]:
    """
    Collect properties and inspect compatible outcomes without changing run artifacts.

    Args:
        directory (Path): Actual suite source, possibly generated in temporary storage.
        suite_location (Path | None): Logical generated suite location for fingerprinting.
        seed (int): Hypothesis seed used by the prospective run.
        traversal_strategy (str): Path order used by the prospective invocation.
        sampling (Sampling): Optional retained percentage and minimum sample after filtering.
        match (str | None): Pytest keyword filter.
        jobs (int | Literal["auto"]): Worker setting for the prospective run.
        shard (Shard | None): Optional shard selection.
        artifact_dir (Path | None): Normal report root.
        cache_dir (Path | None): Optional persistent outcome cache root.
        cache (bool): Whether the prospective run uses cached outcomes.
        rerun (str): Auto, all, or failed selection policy.
        schema_state (dict[str, object] | None): Cached schema availability and uncertainty.

    Returns:
        dict[str, object]: Work estimate with exact property counts and nominal budgets.
    """
    maximum = worker_limit(jobs)
    directory = directory.resolve()
    logical = (suite_location or directory).resolve()
    module = directory / "test_chart_values.py"
    if not module.is_file():
        raise ValueError(f"no generated test suite found at {module}")
    results = (artifact_dir or logical).resolve()
    if shard:
        results = results / "shards" / shard.name
    cache_root = (cache_dir or results / "cache").resolve()
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith("HYPOTHESIS_HELM_") and key != "HYPOTHESIS_HELM_CONFORMITY":
            environment.pop(key)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    traversal_strategy = validate_strategy(traversal_strategy)
    environment["HYPOTHESIS_HELM_TRAVERSAL_STRATEGY"] = traversal_strategy
    environment["HYPOTHESIS_HELM_TRAVERSAL_SEED"] = str(seed)
    environment[SAMPLING_ENVIRONMENT] = json.dumps({"percent": sampling.percent, "minimum": sampling.minimum})
    with TemporaryDirectory(prefix="hypothesis-helm-estimate-") as temporary:
        workspace = Path(temporary)
        config = workspace / "pytest.ini"
        config.write_text("[pytest]\n")
        sampling_file = workspace / "sampling.json"
        environment[SAMPLING_REPORT] = str(sampling_file)
        inventory = workspace / "nodes.json"
        environment["HYPOTHESIS_HELM_COLLECT"] = str(inventory)
        assignment = workspace / "shard.json"
        if shard:
            environment["HYPOTHESIS_HELM_SHARD"] = f"{shard.index}/{shard.total}"
            environment["HYPOTHESIS_HELM_SHARD_REPORT"] = str(assignment)
        command = [
            str(Path(sys.executable).with_name("pytest")),
            "-c",
            str(config),
            "--rootdir",
            str(directory),
            "--confcutdir",
            str(directory),
            "-p",
            "no:cacheprovider",
            "-p",
            "hypothesis.extra.pytestplugin",
            "-p",
            "hypothesis_helm.reporting.progress",
            "--collect-only",
            "-q",
        ]
        if match is not None:
            command += ["-k", match]
        command.append(str(module))
        completed = Processes().run(command, cwd=directory, env=environment, capture_output=True, text=True, check=False)
        if completed.returncode not in (0, 5):
            raise ValueError(f"dry-run collection failed:\n{completed.stdout}{completed.stderr}")
        nodes: list[str] = json.loads(inventory.read_text()) if inventory.exists() else []
        assigned = json.loads(assignment.read_text()) if assignment.exists() else None
        sampling_report = json.loads(sampling_file.read_text()) if sampling_file.exists() else None
    retry = rerun == "failed" or (rerun == "auto" and not in_ci(environment))
    compatible = schema_state is None or schema_state.get("status") == "cached"
    cache_file = (
        cache_root
        / seed_key(seed)
        / (
            fingerprint(
                directory,
                seed,
                match,
                str(shard),
                (cache_root, (artifact_dir or logical).resolve()),
                suite_location=logical,
            )
            + ".json"
        )
    )
    marker = inspect_structure(directory, cache_root, seed, suite_location=logical) if cache else None
    outcomes = read_outcomes(cache_file) if cache and compatible else {}
    examples = budgets(module)
    properties = []
    for node in nodes:
        previous = outcomes.get(node)
        skipped = retry and previous == "passed"
        properties.append(
            {
                "test": node,
                "cached_outcome": previous,
                "action": "reuse" if skipped else "run",
                "max_examples": examples.get(node.split("::")[-1].split("[")[0]),
            }
        )
    scheduled = [entry for entry in properties if entry["action"] == "run"]
    known = [entry["max_examples"] for entry in scheduled]
    budget = sum(value for value in known if isinstance(value, int))
    return {
        "status": "dry-run",
        "seed": seed,
        "sampling": sampling_report,
        "traversal_strategy": traversal_strategy,
        "suite": str(logical),
        "values_structure": marker.report() if marker is not None else None,
        "schema_cache": schema_state,
        "result_cache": str(cache_file) if cache and compatible else None,
        "cache_hit": bool(outcomes),
        "rerun": "failed" if retry else "all",
        "matched_properties": assigned["matched"] if assigned else len(nodes),
        "selected_properties": len(nodes),
        "scheduled_properties": len(scheduled),
        "reused_properties": len(nodes) - len(scheduled),
        "successful_example_budget": budget if all(v is not None for v in known) else None,
        "worker_limit": min(maximum, len(scheduled)),
        "properties": properties,
        "estimated_seconds": 0 if not scheduled else None,
        "notes": [
            "Budgets count successful Hypothesis examples, not exact renders or validations.",
            "Shrinking, replay, rejection, and finite domains can change actual work.",
            "Collection imports suite modules but does not execute fixtures or properties.",
        ],
    }
