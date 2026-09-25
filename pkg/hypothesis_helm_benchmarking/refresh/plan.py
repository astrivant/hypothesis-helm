"""
Declare the complete refresh inventory and its measurement and publication barriers.
"""

from pathlib import Path

from attrs import frozen
from pipeline import Operation

__all__ = ("PREPARATION", "Refresh", "STUDIES", "source_path")


PREPARATION = ("compiler-builtins", "schema-catalog", "native-renderer", "dependency-docs", "checks", "dependencies", "initialize")


STUDIES = (
    "performance",
    "discovery",
    "bug-density",
    "sparsity",
    "structure-sparsity",
    "structural-sparsity",
    "matrix",
    "pca",
    "expansion",
    "structure-depth",
    "nesting",
    "stress",
    "sampling",
    "sensitivity",
    "sensitivity-ordering",
    "calibration-variation",
    "filtering",
    "error-surface",
)


def source_path(project: Path) -> str:
    """
    Expose Python imports from the package folders in a source checkout.

    Args:
        project (Path): Checkout root containing pkg/.

    Returns:
        str: PYTHONPATH entries for the core, catalog, benchmarks, and pipeline.
    """
    return str(project / "pkg")


@frozen
class Refresh:
    """
    Group measurement, diagram, repository and publication operations into one workflow.

    Attributes:
        root (Path): New run directory relative to the project checkout.
    """

    root: Path

    def operations(self) -> tuple[Operation, ...]:
        """
        Build an inspectable inventory with explicit dependencies and isolated measurements.

        Returns:
            tuple[Operation, ...]: All refresh stages in stable scheduling preference order.
        """
        operations: list[Operation] = []

        def stage(name: str, *requires: str, exclusive: bool = False, allow_failure: bool = False) -> None:
            """
            Bind an inventory entry to the readable Bash recipe for that stage.

            Args:
                name (str): Stage identifier shared with the recipe dispatcher.
                *requires (str): Direct operation dependencies.
                exclusive (bool): Run without competing operations in this refresh.
                allow_failure (bool): Defer acceptance to an explicit downstream verifier.

            Returns:
                None: The immutable operation is appended to the inventory.
            """
            recipe = (
                Path("pkg/hypothesis_helm_benchmarking/refresh/recipes/operations.sh")
                if name in PREPARATION
                else self.root / "operations.sh"
            )
            operations.append(Operation(name, ("bash", str(recipe), name, str(self.root)), requires, exclusive, allow_failure))

        # Prepare generated contracts and the optional renderer before tests can
        # consume stale assets or skip native coverage on a fresh checkout.
        stage("compiler-builtins", exclusive=True)
        stage("schema-catalog", "compiler-builtins", exclusive=True)
        stage("native-renderer", "schema-catalog", exclusive=True)
        stage("dependency-docs", "native-renderer", exclusive=True)
        stage("checks", "dependency-docs", exclusive=True)
        stage("dependencies", "checks", exclusive=True)
        stage("initialize", "dependencies", exclusive=True)
        stage("prepare-fixtures", "initialize")
        previous = "prepare-fixtures"
        for name in STUDIES:
            stage(name, previous, exclusive=True)
            previous = name
        stage("measurements-finished", previous)
        stage("verify-measurements", "measurements-finished")
        stage("profile", "verify-measurements", exclusive=True)
        stage("flamegraphs", "profile")
        stage("discovery-tables", "verify-measurements")
        stage("sparsity-tables", "verify-measurements")
        stage("polish-sparsity", "sparsity-tables")
        stage("topologies", "verify-measurements")
        stage("plan-topology-retries", "topologies")
        stage("retry-topologies", "plan-topology-retries")
        stage("catalog-topologies", "retry-topologies")
        stage("verify-topologies", "catalog-topologies")
        stage("publish", "verify-topologies", "discovery-tables", "polish-sparsity", "flamegraphs", exclusive=True)
        stage("update-benchmarks", "publish", exclusive=True)
        stage("diagrams-finished", "update-benchmarks")
        stage("bitnami", "diagrams-finished", exclusive=True, allow_failure=True)
        stage("bitnami-finalize", "bitnami", exclusive=True)
        stage("prometheus", "bitnami-finalize", exclusive=True, allow_failure=True)
        stage("prometheus-finalize", "prometheus", exclusive=True)
        stage("all-finished", "prometheus-finalize")
        stage("update-documentation", "all-finished", exclusive=True)
        stage("verify-publication", "update-documentation", exclusive=True)
        stage("ruff", "verify-publication", exclusive=True)
        stage("publication-finished", "ruff", exclusive=True)
        return tuple(operations)
