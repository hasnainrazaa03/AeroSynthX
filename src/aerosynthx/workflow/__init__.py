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

from aerosynthx.workflow.cli import main
from aerosynthx.workflow.db import RunRow, StageRow, init_db, open_session
from aerosynthx.workflow.errors import RunNotFoundError, StageError, WorkflowError
from aerosynthx.workflow.pipeline import (
    Pipeline,
    RunResult,
    StageResult,
    load_run,
)
from aerosynthx.workflow.stages import STAGE_ORDER, StageName

__all__ = [
    "STAGE_ORDER",
    "Pipeline",
    "RunNotFoundError",
    "RunResult",
    "RunRow",
    "StageError",
    "StageName",
    "StageResult",
    "StageRow",
    "WorkflowError",
    "init_db",
    "load_run",
    "main",
    "open_session",
]
