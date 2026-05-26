"""Errors raised by ``aerosynthx.workflow``."""

from __future__ import annotations

from aerosynthx.physics.errors import AeroSynthXError


class WorkflowError(AeroSynthXError):
    """Base class for workflow-layer errors."""

    code = "workflow.error"


class StageError(WorkflowError):
    """Raised when a pipeline stage fails."""

    code = "workflow.stage.failed"

    def __init__(self, message: str, *, stage: str, code: str | None = None) -> None:
        super().__init__(message, code=code)
        self.stage = stage


class RunNotFoundError(WorkflowError):
    """Raised when a requested run id has no record in the run store."""

    code = "workflow.run.not_found"
