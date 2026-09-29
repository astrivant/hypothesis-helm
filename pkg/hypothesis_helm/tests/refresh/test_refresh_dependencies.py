"""
Require successful dependency preparation before testing or measuring a refresh.
"""

import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis_helm_benchmarking.refresh.plan import Refresh
from pipeline import OperationQueue

from hypothesis_helm.execution.runtime.processes import Processes
from hypothesis_helm.tests import PROJECT_ROOT


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "hypothesis-helm-builtins",
        "hypothesis-helm-builtins --check",
        "hypothesis-helm-catalog --output pkg/hypothesis_helm_catalog/data/input-domains.json",
        "hypothesis-helm-catalog --check",
        "go -C pkg/hypothesis_helm_catalog/upstream test -mod=readonly ./...",
        "hypothesis-helm-renderer --build",
        "hypothesis-helm-docs",
    ],
)
def test_dependencies_gate_refresh_checks(tmp_path: Path, failure: str | None) -> None:
    """
    Execute the preparation recipes with fresh assets and controlled tool failures.

    Args:
        tmp_path (Path): Isolated checkout, executables and operation journal.
        failure (str | None): Exact command that should prevent project checks.

    Returns:
        None: Checks see rebuilt catalogs and a renderer, or remain unstarted after a preparation failure.
    """
    recipe = Path("pkg/hypothesis_helm_benchmarking/refresh/recipes/operations.sh")
    (tmp_path / recipe).parent.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / recipe, tmp_path / recipe)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "check.sh").write_text('#!/usr/bin/env bash\nexec refresh-checks "$@"\n')
    binary = tmp_path / "bin"
    binary.mkdir()
    stub = dedent(
        f"""
        #!{sys.executable}
        import json
        import os
        import sys
        from pathlib import Path

        name = Path(sys.argv[0]).name
        command = " ".join([name, *sys.argv[1:]])
        with Path("calls.jsonl").open("a") as output:
            output.write(json.dumps(command) + "\\n")
        if command == os.environ.get("FAIL_COMMAND"):
            sys.exit(17)
        if name in {{"hypothesis-helm-builtins", "hypothesis-helm-catalog"}}:
            asset = Path(name + ".json")
            if "--check" in sys.argv:
                assert asset.read_text() == "rebuilt"
            else:
                asset.write_text("rebuilt")
        elif name == "hypothesis-helm-renderer":
            Path("renderer-ready").touch()
        elif name == "helm":
            print("v4.3.0")
        elif name == "refresh-checks":
            assert Path("renderer-ready").exists()
            for source in ("hypothesis-helm-builtins", "hypothesis-helm-catalog"):
                assert Path(source + ".json").read_text() == "rebuilt"
            Path("checks-completed").touch()
        """
    ).lstrip()
    for name in (
        "hypothesis-helm-builtins",
        "hypothesis-helm-catalog",
        "hypothesis-helm-renderer",
        "hypothesis-helm-docs",
        "cog",
        "go",
        "helm",
        "refresh-checks",
    ):
        tool = binary / name
        tool.write_text(stub)
        tool.chmod(0o755)
    root = tmp_path / "refresh"
    plan = Refresh(root).operations()
    operations = plan[: next(index + 1 for index, item in enumerate(plan) if item.name == "checks")]
    shard_options = ("-p", "hypothesis_helm.tests.sharding", "--suite-shard", "3/8")
    operations = tuple(replace(item, command=(*item.command, *shard_options)) if item.name == "checks" else item for item in operations)
    queue = OperationQueue(
        operations,
        workers=4,
        directory=root,
        cwd=tmp_path,
        environment=dict(os.environ, PATH=f"{binary}{os.pathsep}{os.environ['PATH']}", FAIL_COMMAND=failure or ""),
        owner_factory=Processes,
    )
    if failure:
        with pytest.raises(RuntimeError, match="Operation"):
            queue.run()
    else:
        queue.run()
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    if failure:
        assert calls[-1] == failure
        assert not any(call.startswith("refresh-checks") for call in calls)
    else:
        assert calls.index("hypothesis-helm-builtins --check") < calls.index("hypothesis-helm-catalog --check")
        assert calls.index("hypothesis-helm-catalog --check") < calls.index("hypothesis-helm-renderer --build")
        check_command = " ".join(("refresh-checks", *shard_options))
        assert calls.index("hypothesis-helm-renderer --build") < calls.index("hypothesis-helm-docs") < calls.index(check_command)
        assert (tmp_path / "checks-completed").exists()
    assert not (root / "frozen-source").exists()
