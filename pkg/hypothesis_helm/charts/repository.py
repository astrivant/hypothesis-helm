"""
Resolve local directories and temporary Git checkouts for repository scans.
"""

from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlsplit

from attrs import define, field

LOGGER = logging.getLogger(__name__)


def remote_name(location: str) -> str | None:
    """
    Recognize HTTPS and Git SSH repositories without converting URLs to paths.

    Args:
        location (str): Local directory or repository clone URL.

    Returns:
        str | None: Safe repository basename, or None for a local directory.
    """
    if location.startswith(("https://", "ssh://")):
        parsed = urlsplit(location)
        if (
            not parsed.hostname
            or parsed.password is not None
            or (parsed.scheme == "https" and parsed.username is not None)
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use a repository clone URL without embedded credentials, query, or fragment")
        path = parsed.path
    elif re.fullmatch(r"[\w.-]+@[\w.-]+:.+", location):
        path = location.split(":", 1)[1]
    elif "://" in location or "::" in location:
        raise ValueError("Repository URLs must use HTTPS or SSH")
    else:
        return None
    name = path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    if not name or name in {".", ".."} or any(ord(char) < 32 for char in location):
        raise ValueError("Repository URL must name a repository")
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def run_git(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """
    Run Git noninteractively and reap its transport processes when stopped.

    Args:
        command (list[str]): Complete Git invocation without shell interpolation.
        timeout (float): Remaining checkout budget in seconds.

    Returns:
        subprocess.CompletedProcess[str]: Git output and exit status.
    """
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if "GIT_SSH" not in environment:
        environment.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        start_new_session=True,
    ) as process:
        try:
            output, error = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, output, error)


@define
class RepositorySource:
    """
    Keep repository provenance separate from the disposable checkout path.

    Attributes:
        location (str): Original repository URL or resolved local directory.
        root (Path): Local directory used for chart discovery.
        name (str): Basename used for retained reports and artifacts.
        remote (bool): Whether this source required a Git checkout or Helm download.
        revision (str | None): Resolved remote commit, when checkout succeeded.
        status (str): Ready, failed, timed out, or interrupted checkout.
        diagnostic (str): Checkout output or failure details retained in the report.
        kind (str): Git, local, or Helm package source.
        packages (list[dict[str, object]]): Requested Helm packages and download outcomes.
        inventory_complete (bool): Whether Helm finished enumerating the requested source.
    """

    location: str
    root: Path
    name: str
    remote: bool
    revision: str | None = None
    status: str = "ready"
    diagnostic: str = ""
    kind: str = "git"
    packages: list[dict[str, object]] = field(factory=list)
    inventory_complete: bool = False

    @classmethod
    def prepare(cls, location: str, scope: ExitStack, timeout: float, deadline: float | None) -> RepositorySource:
        """
        Clone a remote default branch, retaining its resolved commit and diagnostics.

        Args:
            location (str): Local directory or HTTPS/SSH Git URL.
            scope (ExitStack): Owns checkout cleanup after scanning and report writing.
            timeout (float): Checkout time limit in seconds.
            deadline (float | None): Monotonic deadline for the entire scan.

        Returns:
            RepositorySource: Prepared source or explicit incomplete-checkout result.
        """
        name = remote_name(location)
        if name is None:
            root = Path(location).expanduser().resolve()
            return cls(str(root), root, root.name, False, kind="local")
        temporary = scope.enter_context(tempfile.TemporaryDirectory(prefix="hypothesis-helm-repo-"))
        source = cls(location, Path(temporary) / name, name, True)
        LOGGER.info("Cloning repository: %s", location)
        stop = min(time.monotonic() + timeout, deadline if deadline is not None else float("inf"))
        try:
            remaining = stop - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("git clone", timeout)
            cloned = run_git(["git", "clone", "--depth", "1", "--", location, str(source.root)], remaining)
            source.diagnostic = cloned.stdout + cloned.stderr
            if cloned.returncode:
                source.status = "clone-failed"
                return source
            remaining = stop - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("git rev-parse", timeout)
            revision = run_git(["git", "-C", str(source.root), "rev-parse", "HEAD"], remaining)
            if revision.returncode:
                source.status = "clone-failed"
                source.diagnostic += revision.stdout + revision.stderr
            else:
                source.revision = revision.stdout.strip()
        except subprocess.TimeoutExpired:
            source.status = "scan-timeout" if deadline is not None and time.monotonic() >= deadline else "clone-timeout"
            source.diagnostic += "\nRepository checkout deadline reached"
        except KeyboardInterrupt:
            source.status = "interrupted"
            source.diagnostic += "\nRepository checkout interrupted"
        except OSError as exc:
            source.status = "clone-failed"
            source.diagnostic += f"\nCould not execute Git: {exc}"
        return source
