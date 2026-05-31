"""End-to-end workflow orchestrator (see ``docs/phases/PHASE_5.md``).

Public API:

- :class:`Pipeline` -- staged execution from intent text to OpenFOAM case.
- :class:`RunResult` / :class:`StageResult` -- typed pipeline outputs.
- :class:`StageName` -- the ordered stage enum.
- :func:`load_run` -- read a persisted run from the SQLite store.
- :func:`init_db` / :func:`open_session` -- low-level persistence hooks.
- :func:`main` -- CLI entry point (also installed as ``aerosynthx``).
"""

from __future__ import annotations

from aerosynthx.workflow.artifacts import (
    ArchiveResult,
    ContentAddressedStore,
    StoreStats,
)
from aerosynthx.workflow.cancellation import CancellationToken, Deadline, RunControl
from aerosynthx.workflow.cli import main
from aerosynthx.workflow.db import RunRow, StageRow, init_db, open_session
from aerosynthx.workflow.errors import (
    RunCancelledError,
    RunNotFoundError,
    RunTimeoutError,
    StageError,
    WorkflowError,
)
from aerosynthx.workflow.locking import DEFAULT_RUN_LOCKS, RunLockRegistry
from aerosynthx.workflow.pipeline import (
    Pipeline,
    RunResult,
    StageResult,
    load_run,
)
from aerosynthx.workflow.progress import ProgressEvent, ProgressSink
from aerosynthx.workflow.retention import GarbageCollectResult, PruneResult
from aerosynthx.workflow.stages import STAGE_ORDER, StageName

__all__ = [
    "DEFAULT_RUN_LOCKS",
    "STAGE_ORDER",
    "ArchiveResult",
    "CancellationToken",
    "ContentAddressedStore",
    "Deadline",
    "GarbageCollectResult",
    "Pipeline",
    "ProgressEvent",
    "ProgressSink",
    "PruneResult",
    "RunCancelledError",
    "RunControl",
    "RunLockRegistry",
    "RunNotFoundError",
    "RunResult",
    "RunRow",
    "RunTimeoutError",
    "StageError",
    "StageName",
    "StageResult",
    "StageRow",
    "StoreStats",
    "WorkflowError",
    "init_db",
    "load_run",
    "main",
    "open_session",
]
