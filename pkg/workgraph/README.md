# Workgraph

Workgraph schedules named operations once their prerequisites finish. It bounds
concurrent work, reserves the queue for exclusive operations, records progress,
and joins registered process owners before returning after failure or cancellation.

The Python import is `workgraph`. It is a sibling of `hypothesis_helm` under `pkg/`;
the root Poetry configuration includes both packages in the same distribution.
Workgraph uses only the Python standard library. It contains no Helm commands,
refresh stages, or project-specific filesystem paths.

## Integration

Create immutable `Operation` records with command arguments and prerequisite names,
then pass them to `OperationQueue`. Supply an `owner_factory` implementing the
`ProcessOwner` protocol: each owner must prevent further process creation when
stopped and retain its children until they have been joined. Repeated `stop` calls
must be safe. Applications can also supply cancellation and critical-section
context managers for their signal handling requirements.

The queue owns the worker threads and the supplied owners. The application owns
command definitions, process-group semantics, retry policy, and publication checks.
Commands with `allow_failure=True` retain their native exit code; use a required
verification operation to decide whether their artifacts are acceptable.

| Type | Responsibility |
| --- | --- |
| `Operation` | Command, prerequisites, exclusivity, failure acceptance, and optional deadline. |
| `ProcessOwner` | Interface for executing and reliably stopping one command tree. |
| `OperationQueue` | Ready-work scheduling, worker ownership, logs, and atomic journal updates. |

The journal records `pending`, `running`, `completed`, `failed`, `cancelled`, and
`blocked` states. Completed work is not automatically resumed by a new queue.
An empty inventory is valid. Cycles, missing prerequisites, and duplicate names
are rejected before commands run.

## Development

Use the root project's Poetry environment, lockfile, build, and check commands.
`poetry build` includes both import packages in the application wheel. The root
check command covers the library and its integration tests.
