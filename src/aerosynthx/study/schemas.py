"""Pydantic schemas for the study layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aerosynthx.intent.schemas import DesignIntent
from aerosynthx.workflow.pipeline import RunResult


class StudySpec(BaseModel):
    """Specification for a parametric study."""

    study_name: str = Field(..., min_length=1)
    base_intent: dict[str, Any]
    variables: dict[str, list[Any]]


class StudyResult(BaseModel):
    """Aggregated results of a completed study."""

    study_id: str
    study_name: str
    spec: StudySpec
    status: str
    runs: list[RunResult]
