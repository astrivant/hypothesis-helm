"""
Upload finalized draft release attachments in stable ascending-size order.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main(directory: Path) -> int:
    """
    Retry individual draft uploads without changing a published release.

    Args:
        directory (Path): Flat, verified attachment directory.

    Returns:
        int: Zero once each attachment has reached GitHub.
    """
    state = json.loads(
        subprocess.check_output(
            ["gh", "release", "view", os.environ["RELEASE_TAG"], "--repo", os.environ["GITHUB_REPOSITORY"], "--json", "isDraft"]
        )
    )
    if state.get("isDraft") is not True:
        raise ValueError("Uploads may replace draft attachments only")
    for path in sorted(directory.iterdir(), key=lambda item: (item.stat().st_size, item.name)):
        subprocess.run(
            ["gh", "release", "upload", os.environ["RELEASE_TAG"], str(path), "--repo", os.environ["GITHUB_REPOSITORY"], "--clobber"],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
