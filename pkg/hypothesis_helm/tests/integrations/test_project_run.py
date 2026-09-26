"""
Verify that checkout commands and their children use the same project environment.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.tests import PROJECT_ROOT


@pytest.mark.parametrize("foreign_environment", [False, True])
def test_project_runner_exposes_tools_to_children(tmp_path: Path, foreign_environment: bool) -> None:
    """
    Find installed helpers from a clean CI shell or an unrelated activated environment.

    Args:
        tmp_path (Path): Isolated checkout with executable command and formatter stubs.
        foreign_environment (bool): Whether another environment already precedes system tools.

    Returns:
        None: Children find the project formatter, preserve arguments and propagate their exit status.
    """
    project = tmp_path / "checkout with spaces"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / "scripts/project-run.sh", scripts / "project-run.sh")
    environment = project / ".venv"
    binaries = environment / "bin"
    binaries.mkdir(parents=True)
    formatter = binaries / "shfmt"
    formatter.write_text('#!/bin/sh\nprintf "%s\\n" "$1"\nexit 7\n')
    formatter.chmod(0o755)
    command = binaries / "check-shell"
    command.write_text(
        dedent(f"""
            #!{sys.executable}
            import json
            import os
            import shutil
            import subprocess
            import sys

            print(json.dumps({{"formatter": shutil.which("shfmt"), "environment": os.environ.get("VIRTUAL_ENV")}}), flush=True)
            result = subprocess.run(["shfmt", *sys.argv[1:]], check=False)
            raise SystemExit(result.returncode)
            """).lstrip()
    )
    command.chmod(0o755)
    process_env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    process_env["PATH"] = os.defpath
    if foreign_environment:
        foreign = tmp_path / "unrelated"
        foreign_bin = foreign / "bin"
        foreign_bin.mkdir(parents=True)
        for name in ("shfmt", "check-shell"):
            executable = foreign_bin / name
            executable.write_text("#!/bin/sh\nexit 99\n")
            executable.chmod(0o755)
        process_env.update(VIRTUAL_ENV=str(foreign), PATH=f"{foreign_bin}:{os.defpath}")
    result = subprocess.run(
        ["/bin/bash", str(scripts / "project-run.sh"), "check-shell", "argument with spaces"],
        cwd=tmp_path,
        env=process_env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 7, result.stderr
    metadata, argument = result.stdout.splitlines()
    assert json.loads(metadata) == {"formatter": str(formatter), "environment": str(environment)}
    assert argument == "argument with spaces"
