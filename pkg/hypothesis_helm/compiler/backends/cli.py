"""
Compose backend controls and bounded plan exports into the existing command tree.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.compiler.backends.lowering import compile_plan
from hypothesis_helm.compiler.backends.model import Limits, digest
from hypothesis_helm.compiler.backends.scheduler import BackendOptions
from hypothesis_helm.schemas.generation.factors import factor_space

__all__ = ("add_options", "arguments", "export_plan", "options")


def arguments(backend: BackendOptions) -> tuple[str, ...]:
    """
    Retain explicit backend controls in resumable subprocess operation records.

    Args:
        backend (BackendOptions): Validated settings to forward to the same parser.

    Returns:
        tuple[str, ...]: Non-sensitive command arguments preserving every execution control.
    """
    return (
        "--execution-backend",
        backend.name,
        "--backend-fallback",
        backend.fallback,
        "--backend-batch-size",
        str(backend.limits.batch_size),
        "--backend-memory-mib",
        str(backend.limits.memory_bytes // 1024**2),
        "--backend-timeout",
        str(backend.limits.timeout),
        *(("--backend-verify",) if backend.verify else ()),
    )


def add_options(parser: argparse.ArgumentParser) -> None:
    """
    Attach the same validated backend interface to test and repository scan commands.

    Args:
        parser (argparse.ArgumentParser): Existing command parser.

    Returns:
        None: Adds explicit backend selection, bounds and diagnostics.
    """
    parser.add_argument(
        "--execution-backend",
        choices=("reference", "cpu-vector", "gpu"),
        default="reference",
        help="finite predicate engine; rendering and callbacks remain on the host",
    )
    parser.add_argument(
        "--backend-fallback",
        choices=("error", "reference"),
        default="error",
        help="explicit policy for unavailable or failed native backends",
    )
    parser.add_argument("--backend-batch-size", type=int, default=256, help="maximum candidates per compiled batch (1..16384)")
    parser.add_argument("--backend-memory-mib", type=int, default=64, help="bounded host/device allocation budget per batch")
    parser.add_argument("--backend-timeout", type=float, default=60.0, help="deadline in seconds for compiler/worker requests")
    parser.add_argument("--backend-verify", action="store_true", help="differentially check compiled predicates against the host validator")


def options(args: argparse.Namespace) -> BackendOptions:
    """
    Resolve options once at the orchestration boundary.

    Args:
        args (argparse.Namespace): Parsed command settings.

    Returns:
        BackendOptions: Typed immutable execution settings.
    """
    limits = Limits(
        batch_size=getattr(args, "backend_batch_size", 256),
        memory_bytes=getattr(args, "backend_memory_mib", 64) * 1024**2,
        timeout=getattr(args, "backend_timeout", 60.0),
    )
    if not 1 <= limits.batch_size <= 16384 or not 1 <= limits.memory_bytes <= 1024**3 or not 0 < limits.timeout <= 300:
        raise ValueError("backend limits require batch size 1..16384, memory 1..1024 MiB, timeout 0..300 seconds")
    return BackendOptions(
        getattr(args, "execution_backend", "reference"),
        getattr(args, "backend_fallback", "error"),
        limits,
        getattr(args, "backend_verify", False),
    )


def export_plan(args: argparse.Namespace) -> int:
    """
    Export versioned data without executing candidates or compiling chart-provided code.

    Args:
        args (argparse.Namespace): Chart path, factor bound and explicit output path.

    Returns:
        int: Zero after writing the validated plan.
    """
    logger = logging.getLogger(__name__)
    logger.info("Compiling finite plan")
    chart = Chart.load(args.chart)
    schema = chart.generation_schema()
    context = digest([schema, chart.defaults])
    plan = compile_plan(schema, factor_space(schema, args.max_cases), context_digest=context)
    destination = Path(args.emit_plan)
    # Exclusive creation prevents accidentally replacing another chart's retained plan.
    with destination.open("xb") as stream:
        stream.write(plan.encode() + b"\n")
    destination.chmod(0o600)
    logger.info("Exported plan nodes=%d factors=%d host_fragments=%d", len(plan.nodes), len(plan.factors), len(plan.fallbacks))
    return 0
