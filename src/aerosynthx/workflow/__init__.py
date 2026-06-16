"""The AeroSynthX workflow orchestration layer.

This package is the "application" layer that stitches together the lower-level
engineering modules (intent, physics, geometry, openfoam) into a coherent,
end-to-end pipeline.

See ``docs/phases/PHASE_5.md``.
"""

from __future__ import annotations

from aerosynthx.workflow.artifacts import ContentAddressedStore, RelinkResult
from aerosynthx.workflow.cancellation import CancellationToken
from aerosynthx.workflow.db import init_db
from aerosynthx.workflow.errors import RunNotFoundError, StageError
from aerosynthx.workflow.locking import RunLockRegistry
from aerosynthx.workflow.pipeline import (
    Pipeline,
    RunListItem,
    RunPage,
    RunResult,
    StageResult,
    load_run,
    query_runs,
)
from aerosynthx.workflow.progress import ProgressEvent, ProgressSink
from aerosynthx.workflow.report import render_run_report
from aerosynthx.workflow.retention import GarbageCollectResult, PruneResult
from aerosynthx.workflow.cli import main
from aerosynthx.workflow.stages import STAGE_ORDER_2D, STAGE_ORDER_3D, StageName

__all__ = [
    "Pipeline",
    "RunResult",
    "StageResult",
    "RunListItem",
    "RunPage",
    "RunNotFoundError",
    "StageError",
    "CancellationToken",
    "ProgressSink",
    "ProgressEvent",
    "ContentAddressedStore",
    "RelinkResult",
    "PruneResult",
    "GarbageCollectResult",
    "RunLockRegistry",
    "StageName",
    "STAGE_ORDER_2D",
    "STAGE_ORDER_3D",
    "init_db",
    "load_run",
    "query_runs",
    "render_run_report",
    "main",
]
