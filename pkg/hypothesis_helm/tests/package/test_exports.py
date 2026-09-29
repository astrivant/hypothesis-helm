"""
Keep maintained module exports explicit without leaking implementation dependencies.
"""

import ast
import importlib

import pytest

from hypothesis_helm.tests import PACKAGES_ROOT

PACKAGES = PACKAGES_ROOT
PROJECT_PACKAGES = {"hypothesis_helm", "hypothesis_helm_catalog", "hypothesis_helm_benchmarking"}


def test_every_maintained_module_declares_owned_exports() -> None:
    """
    Check all package sources without executing recipes or importing optional study dependencies.

    Returns:
        None: Export lists are literal, unique, and contain only local definitions or project re-exports.
    """
    for path in sorted(PACKAGES.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        declarations = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
        ]
        assert len(declarations) == 1, path
        exports = ast.literal_eval(declarations[0].value)
        assert isinstance(exports, (tuple, list)) and all(isinstance(name, str) for name in exports), path
        assert len(exports) == len(set(exports)), path
        assert not any(name.startswith("_") for name in exports), path
        definitions: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.add(node.name)
            elif isinstance(node, ast.Assign):
                definitions.update(target.id for target in node.targets if isinstance(target, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                definitions.add(node.target.id)
            elif isinstance(node, ast.TypeAlias):
                definitions.add(node.name.id)
        # Include lazy package facades and TYPE_CHECKING imports without loading their modules.
        imported: dict[str, set[str]] = {}
        for imported_node in ast.walk(tree):
            if isinstance(imported_node, (ast.Import, ast.ImportFrom)):
                for alias in imported_node.names:
                    name = alias.asname or (alias.name.split(".")[0] if isinstance(imported_node, ast.Import) else alias.name)
                    origin = alias.name if isinstance(imported_node, ast.Import) else imported_node.module or ""
                    imported.setdefault(name, set()).add(origin.split(".")[0])
        for name in exports:
            assert name in definitions or imported.get(name, set()) & PROJECT_PACKAGES, (path, name)
            if name not in definitions:
                assert imported[name] <= PROJECT_PACKAGES, (path, name, imported[name])


@pytest.mark.parametrize(
    "module_name",
    [
        "hypothesis_helm",
        "hypothesis_helm.charts.model",
        "hypothesis_helm.compiler.asts.lattice",
        "hypothesis_helm.compiler.asts.templates",
        "hypothesis_helm.schemas.contracts",
        "hypothesis_helm.reporting.reports.links",
        "hypothesis_helm_catalog",
        "hypothesis_helm_catalog.sources",
        "hypothesis_helm_benchmarking.refresh.operations",
        "hypothesis_helm_benchmarking.refresh.output",
    ],
)
def test_wildcard_import_exposes_only_the_declared_api(module_name: str) -> None:
    """
    Exercise real wildcard imports, including the lazy root API and project re-exports.

    Args:
        module_name (str): Maintained module with dependencies that must remain outside its wildcard API.

    Returns:
        None: Exported names resolve and dependency helpers stay out of the caller's namespace.
    """
    module = importlib.import_module(module_name)
    namespace: dict[str, object] = {}
    exec(f"from {module_name} import *", namespace)
    assert namespace.keys() - {"__builtins__"} == set(module.__all__)
    assert {"attrs", "frozen", "Map", "subprocess", "ThreadPoolExecutor", "logging", "json"}.isdisjoint(namespace)
    for name in module.__all__:
        assert namespace[name] is getattr(module, name)


def test_existing_package_facades_remain_available() -> None:
    """
    Preserve the intentional root imports while tightening wildcard boundaries.

    Returns:
        None: Public entry points retain their original identity.
    """
    import hypothesis_helm
    from hypothesis_helm.charts.model import Chart

    assert set(hypothesis_helm.__all__) == {"Chart", "check_chart", "coalesce", "env", "generate_tests", "refresh_env", "set_env"}
    assert hypothesis_helm.Chart is Chart
