"""Pydantic DTOs for the AeroSynthX HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Body of ``POST /api/v1/runs``."""

    intent_text: str = Field(..., min_length=1, description="Natural-language design intent.")
    resume: bool = Field(
        default=True,
        description="Reuse a previously-completed run with the same intent.",
    )


class RunSummary(BaseModel):
    """One-row digest returned by ``GET /api/v1/runs``."""

    run_id: str
    status: str
    intent_text: str
    created_at_iso: str
    completed_at_iso: str | None


class VersionInfo(BaseModel):
    """Body of ``GET /api/v1/version``."""

    name: str
    version: str
