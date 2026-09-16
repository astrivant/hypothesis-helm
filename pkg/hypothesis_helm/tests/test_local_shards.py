"""
Exercise GNU Parallel command quoting, shard coverage and failure propagation.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("shards", [1, 2, 3, 4])
def test_local_shards(tmp_path: Path, shards: int) -> None:
    """
    Launch the packaged CLI outside the checkout with a recording Helm and one failing shard.

    Args:
        tmp_path (Path): Isolated executables, output and invocation records.
        shards (int): Requested concurrent application-shard count.

    Returns:
        None: Every shard runs once, arguments survive quoting and failures propagate.
    """
    if shutil.which("parallel") is None:
        pytest.skip("GNU Parallel is not installed")
    helm = tmp_path / "helm"
    helm.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "shard = args[args.index('--shard') + 1]\n"
        "pathlib.Path(os.environ['HH_RECORD'], shard.replace('/', '-')).write_text("
        "json.dumps(args))\n"
        "sys.exit(7 if shard.startswith('2/') else 0)\n"
    )
    helm.chmod(0o755)
    records = tmp_path / "records"
    records.mkdir()
    literal = "suite with 'quotes' {} $(touch INJECTED); `echo bad`"
    output = tmp_path / "results with spaces {}"
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("hypothesis-helm-benchmark")),
            "shards",
            "--shards",
            str(shards),
            "--output-dir",
            str(output),
            literal,
            "--",
            "--match",
            "literal {} $HOME",
        ],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "HH_RECORD": str(records)},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (result.returncode == 0) == (shards == 1), result.stderr
    assert len(list(records.iterdir())) == shards
    for index in range(1, shards + 1):
        args = json.loads((records / f"{index}-{shards}").read_text())
        assert args[:5] == ["hypothesis", "run", literal, "--match", "literal {} $HOME"]
        assert args[args.index("--shard") + 1] == f"{index}/{shards}"
        assert args[args.index("--jobs") + 1] == "1"
        assert "--no-cache" in args
    assert len((output / "joblog.tsv").read_text().splitlines()) == shards + 1
    assert not (tmp_path / "INJECTED").exists()
