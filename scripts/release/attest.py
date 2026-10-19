"""
Sign and verify one finalized Hypothesis Helm release against an independently trusted key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Sequence


def digest(path: Path) -> str:
    """
    Hash a regular release file without following symbolic links.

    Args:
        path (Path): Finalized artifact.

    Returns:
        str: SHA-256 digest.

    Raises:
        ValueError: The artifact is a symbolic link or not a regular file.
    """
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular artifact: {path.name}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(key: Path) -> str:
    """
    Derive the canonical public-key fingerprint from DER bytes.

    Args:
        key (Path): PEM public key.

    Returns:
        str: SHA-256 public-key fingerprint, distinct from the artifact hashes.
    """
    encoded = subprocess.check_output(["openssl", "pkey", "-pubin", "-in", str(key), "-outform", "DER"])
    return hashlib.sha256(encoded).hexdigest()


def inventory(directory: Path) -> dict[str, str]:
    """
    Bind every finalized payload and verification file except the manifest itself.

    Args:
        directory (Path): Flat release directory.

    Returns:
        dict[str, str]: Filename to digest mapping in canonical order.

    Raises:
        ValueError: A filename is unsuitable for a portable checksum manifest.
    """
    result: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.name in {"SHA256SUMS", "SHA256SUMS.sigstore.json"}:
            continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", path.name):
            raise ValueError("Release filenames must be portable basenames")
        result[path.name] = digest(path)
    return result


def check_manifest(directory: Path) -> None:
    """
    Reject omitted, altered, duplicate or unexpected release files.

    Args:
        directory (Path): Downloaded or prepared release directory.

    Returns:
        None: Every listed file matches and no payload was omitted.

    Raises:
        ValueError: The checksum manifest is malformed or incomplete.
    """
    expected: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9_.-]*)", line)
        if match is None or match[2] in expected:
            raise ValueError("Malformed or duplicate checksum entry")
        expected[match[2]] = match[1]
    if not expected or inventory(directory) != expected:
        raise ValueError("Release payload differs from its complete checksum manifest")


def signature(path: Path, key: str, *, signing: bool) -> None:
    """
    Use the maintained Cosign command for a detached blob signature.

    Args:
        path (Path): Exact finalized bytes to bind.
        key (str): Public key path or environment private-key reference.
        signing (bool): Whether to sign or verify.

    Returns:
        None: Cosign succeeded; its nonzero result remains a hard failure.
    """
    command = ["cosign", "sign-blob" if signing else "verify-blob", "--key", key, "--bundle", str(path) + ".sigstore.json"]
    if signing:
        command.extend(["--yes", "--signing-config", str(Path(__file__).with_name("signing-config.json"))])
    else:
        command.extend(["--offline", "--insecure-ignore-tlog"])
    command.append(str(path))
    subprocess.run(command, check=True)


def verify(directory: Path, tag: str, source: str, trusted: str) -> None:
    """
    Verify the complete release against caller-supplied source and trust anchors.

    Args:
        directory (Path): Flat release download directory.
        tag (str): Expected immutable tag.
        source (str): Expected full source revision.
        trusted (str): Independently obtained public-key fingerprint.

    Returns:
        None: The manifest signature, payload and source bindings are valid.

    Raises:
        ValueError: Trust, integrity or source bindings disagree.
    """
    version = str(Version(tag.removeprefix("v")))
    artifacts = {f"hypothesis_helm-{version}-py3-none-any.whl", f"hypothesis_helm-{version}.tar.gz"}
    expected = (
        artifacts
        | {name + ".sigstore.json" for name in artifacts}
        | {"cosign.pub", "public-key.sha256", "SOURCE.json", "SHA256SUMS", "SHA256SUMS.sigstore.json"}
    )
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("Release is missing required attachments or contains unexpected files")
    key = directory / "cosign.pub"
    if not re.fullmatch(r"[0-9a-f]{64}", trusted) or fingerprint(key) != trusted:
        raise ValueError("Release signing key does not match the trusted fingerprint")
    signature(directory / "SHA256SUMS", str(key), signing=False)
    check_manifest(directory)
    provenance = json.loads((directory / "SOURCE.json").read_text())
    if provenance.get("tag") != tag or provenance.get("commit") != source:
        raise ValueError("Release source does not match the selected tag and commit")
    for name in sorted(artifacts):
        signature(directory / name, str(key), signing=False)
    if (directory / "public-key.sha256").read_text().strip() != trusted:
        raise ValueError("Published fingerprint differs from the trusted key")


def prepare(directory: Path, tag: str, source: str, trusted: str) -> None:
    """
    Finalize signatures only after the exact build payload has been assembled.

    Args:
        directory (Path): Flat directory containing verified build artifacts.
        tag (str): Selected existing release tag.
        source (str): Selected full source revision.
        trusted (str): Expected repository signing fingerprint.

    Returns:
        None: The complete attachment set is signed and independently verified.

    Raises:
        ValueError: Payload, tag, source or signing identity is invalid.
    """
    if not tag.startswith("v"):
        raise ValueError("Expected a version tag")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Expected a full source revision")
    version = str(Version(tag[1:]))
    expected = {f"hypothesis_helm-{version}-py3-none-any.whl", f"hypothesis_helm-{version}.tar.gz"}
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("Build must contain exactly this version's wheel and source archive")
    artifacts = sorted(directory.iterdir())
    if len(artifacts) != 2 or len([path for path in artifacts if path.suffix == ".whl"]) != 1:
        raise ValueError("Expected one tested wheel and one source archive")
    if len([path for path in artifacts if path.name.endswith(".tar.gz")]) != 1:
        raise ValueError("Expected one tested source archive")
    for path in artifacts:
        digest(path)
    key = directory / "cosign.pub"
    key.write_bytes(subprocess.check_output(["cosign", "public-key", "--key", "env://COSIGN_PRIVATE_KEY"]))
    if fingerprint(key) != trusted:
        raise ValueError("Configured signing key differs from the repository trust anchor")
    (directory / "public-key.sha256").write_text(trusted + "\n")
    (directory / "SOURCE.json").write_text(json.dumps({"tag": tag, "commit": source}, sort_keys=True, indent=2) + "\n")
    for path in artifacts:
        signature(path, "env://COSIGN_PRIVATE_KEY", signing=True)
        signature(path, str(key), signing=False)
    (directory / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in inventory(directory).items()))
    signature(directory / "SHA256SUMS", "env://COSIGN_PRIVATE_KEY", signing=True)
    verify(directory, tag, source, trusted)


def main(argv: Sequence[str] | None = None) -> int:
    """
    Select preparation or read-only verification with one parser hierarchy.

    Args:
        argv (Sequence[str] | None): Explicit arguments or the process arguments.

    Returns:
        int: Zero after verification; malformed inputs fail before publication.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name, handler in (("prepare", prepare), ("verify", verify)):
        command = commands.add_parser(name)
        command.add_argument("--directory", type=Path, required=True)
        command.add_argument("--tag", required=True)
        command.add_argument("--source", required=True)
        command.add_argument("--fingerprint", required=True)
        command.set_defaults(handler=handler)
    args = parser.parse_args(argv)
    args.handler(args.directory, args.tag, args.source, args.fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
