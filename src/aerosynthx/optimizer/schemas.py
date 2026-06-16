"""Pydantic schemas for the optimization layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OptimizationSpec(BaseModel):
    """Specification for an optimization study."""

    objective: Literal["maximize_cl_cd", "minimize_cd", "target_cl"] = Field(..., description="The optimization objective.")
    target_cl: float | None = Field(default=None, description="Target lift coefficient for the 'target_cl' objective.")
    design_space: dict[str, list[Any]] = Field(..., description="The variables to explore.")
    base_intent: dict[str, Any] = Field(..., description="The base intent to be modified for each run.")

    @model_validator(mode="after")
    def validate_objective(self) -> "OptimizationSpec":
        if self.objective == "target_cl" and self.target_cl is None:
            raise ValueError("`target_cl` must be provided for the 'target_cl' objective.")
        return self


class OptimizationResult(BaseModel):
    """The final result of an optimization study."""

    optimization_id: str
    study_id: str
    best_run_id: str
    best_run_result: dict[str, Any]
