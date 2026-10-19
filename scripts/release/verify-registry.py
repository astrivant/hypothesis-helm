"""
Compare published PyPI files with the exact tested wheel and source archive.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


def verify(directory: Path, tag: str) -> None:
    """
    Allow bounded registry propagation, then verify metadata and downloaded bytes.

    Args:
        directory (Path): Tested Python distributions from this source revision.
        tag (str): Selected version tag.

    Returns:
        None: Every expected registry artifact has the exact tested SHA-256 digest.

    Raises:
        ValueError: Registry membership or artifact bytes differ from the tested build.
        HTTPError: Registry metadata remains unavailable after the propagation window.
    """
    expected = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir() if path.name.endswith((".whl", ".tar.gz"))
    }
    if len(expected) != 2:
        raise ValueError("Expected one tested wheel and source archive")
    for attempt in range(6):
        try:
            with urlopen(f"https://pypi.org/pypi/hypothesis-helm/{tag.removeprefix('v')}/json", timeout=30) as response:
                value = json.load(response)
            break
        except HTTPError as error:
            if error.code != HTTPStatus.NOT_FOUND or attempt == 5:
                raise
            time.sleep(2**attempt)
    files = value["urls"]
    if any(item.get("yanked", False) for item in files):
        raise ValueError("Registry release contains yanked artifacts")
    if {item["filename"]: item["digests"]["sha256"] for item in files} != expected:
        raise ValueError("PyPI metadata differs from the tested artifact set")
    for item in files:
        if not item["url"].startswith("https://files.pythonhosted.org/"):
            raise ValueError("Unexpected PyPI artifact origin")
        with urlopen(item["url"], timeout=30) as response:
            if not response.geturl().startswith("https://files.pythonhosted.org/"):
                raise ValueError("Unexpected artifact redirect")
            content = response.read(32 * 1024 * 1024 + 1)
        if hashlib.sha256(content).hexdigest() != expected[item["filename"]]:
            raise ValueError("Downloaded registry bytes differ from the tested artifact")


if __name__ == "__main__":
    verify(Path(sys.argv[1]), sys.argv[2])
