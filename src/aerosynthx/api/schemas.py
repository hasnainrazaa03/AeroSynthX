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
    use_llm: bool = Field(
        default=False,
        description="Parse with the configured LLM provider instead of the offline parser.",
    )
    execute: bool = Field(
        default=False,
        description="Run the generated case through OpenFOAM when the toolchain is available.",
    )
    timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Optional wall-clock budget in seconds; the run fails fast once exceeded.",
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
