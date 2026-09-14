"""
Fingerprint application and harness sources for reproducible measurements.
"""

import hashlib
from pathlib import Path


def code_digest() -> str:
    """
    Identify measured application and harness code, including uncommitted changes.

    Returns:
        str: SHA-256 fingerprint of execution and harness Python sources.
    """
    digest = hashlib.sha256()
    base = Path(__file__).resolve().parents[2]
    for path in sorted(base.rglob("*.py")):
        if "tests" not in path.parts:
            digest.update(str(path.relative_to(base)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()
