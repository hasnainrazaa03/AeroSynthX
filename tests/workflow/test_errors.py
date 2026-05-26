from __future__ import annotations

import pytest

from aerosynthx.physics.errors import AeroSynthXError
from aerosynthx.workflow.errors import RunNotFoundError, StageError, WorkflowError


@pytest.mark.parametrize(
    ("cls", "code"),
    [
        (WorkflowError, "workflow.error"),
        (StageError, "workflow.stage.failed"),
        (RunNotFoundError, "workflow.run.not_found"),
    ],
)
def test_workflow_errors_have_code(cls: type[WorkflowError], code: str) -> None:
    assert cls.code == code
    assert issubclass(cls, AeroSynthXError)


def test_stage_error_carries_stage_name_and_default_code() -> None:
    err = StageError("boom", stage="parse")
    assert err.stage == "parse"
    assert err.code == "workflow.stage.failed"
    assert "boom" in str(err)


def test_stage_error_accepts_custom_code() -> None:
    err = StageError("nope", stage="case", code="workflow.case.bad")
    assert err.code == "workflow.case.bad"
