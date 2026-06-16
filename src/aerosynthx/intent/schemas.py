"""Pydantic v2 schemas for the AeroSynthX intent layer."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    field_validator,
    model_validator,
)

Provenance = Literal["user_provided", "inferred"]

# Operating envelope constants
MAX_MACH_INCOMPRESSIBLE = 0.3
MAX_ABS_ALPHA_DEG = 20.0
MIN_ALTITUDE_M = 0.0
MAX_ALTITUDE_M = 20_000.0


class AirfoilSpec(BaseModel):
    """Airfoil family + designation + dimensional chord."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    family: Literal["naca4", "naca5", "custom"]
    designation: str | None = Field(default=None, description="NACA code, e.g. '2412' or '23012'.")
    chord_m: PositiveFloat
    coordinates: list[tuple[float, float]] | None = Field(default=None, description="User-supplied normalized coordinates for custom airfoils.")

    @model_validator(mode="after")
    def validate_family_fields(self) -> "AirfoilSpec":
        if self.family == "custom":
            if self.coordinates is None:
                raise ValueError("`coordinates` must be provided for `custom` airfoil family.")
            if self.designation is not None:
                raise ValueError("`designation` must not be provided for `custom` airfoil family.")
        else:
            if self.designation is None:
                raise ValueError(f"`designation` must be provided for `{self.family}` airfoil family.")
            if self.coordinates is not None:
                raise ValueError(f"`coordinates` must not be provided for `{self.family}` airfoil family.")
            if not self.designation.isdigit():
                raise ValueError("Designation must contain only digits.")
            if self.family == "naca4":
                if len(self.designation) != 4:
                    raise ValueError("NACA 4-digit designation must be 4 characters long.")
            elif self.family == "naca5":
                if len(self.designation) != 5:
                    raise ValueError("NACA 5-digit designation must be 5 characters long.")
        return self


class WingSpec(BaseModel):
    """Parametric definition of a 3D wing."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    span: PositiveFloat
    sweep_deg: float = 0.0
    dihedral_deg: float = 0.0
    twist_deg: float = 0.0
    root_airfoil: AirfoilSpec
    tip_airfoil: AirfoilSpec | None = None


class FlowCondition(BaseModel):
    """Freestream flow conditions."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    altitude_m: float | None = Field(default=None)
    velocity_m_s: PositiveFloat | None = None
    mach: float | None = Field(default=None, ge=0.0, lt=MAX_MACH_INCOMPRESSIBLE)
    angle_of_attack_deg: float | None = Field(default=None, ge=-MAX_ABS_ALPHA_DEG, le=MAX_ABS_ALPHA_DEG)
    reynolds_target: PositiveFloat | None = None
    alpha_start_deg: float | None = Field(default=None, ge=-MAX_ABS_ALPHA_DEG, le=MAX_ABS_ALPHA_DEG)
    alpha_end_deg: float | None = Field(default=None, ge=-MAX_ABS_ALPHA_DEG, le=MAX_ABS_ALPHA_DEG)
    alpha_increment_deg: PositiveFloat | None = None

    @model_validator(mode="after")
    def validate_flow_conditions(self) -> "FlowCondition":
        has_v = self.velocity_m_s is not None
        has_m = self.mach is not None
        if has_v and has_m:
            raise ValueError("specify exactly one of velocity_m_s or mach")
        if not has_v and not has_m:
            raise ValueError("at least one of velocity_m_s or mach must be provided")
        if has_m and self.altitude_m is None:
            raise ValueError("altitude_m is required when mach is provided")

        has_single_aoa = self.angle_of_attack_deg is not None
        has_sweep_aoa = self.alpha_start_deg is not None or self.alpha_end_deg is not None or self.alpha_increment_deg is not None
        if has_single_aoa and has_sweep_aoa:
            raise ValueError("specify either a single angle_of_attack_deg or a sweep range, not both")
        if not has_single_aoa and not has_sweep_aoa:
            raise ValueError("at least one of angle_of_attack_deg or a sweep range must be provided")
        if has_sweep_aoa and not (self.alpha_start_deg is not None and self.alpha_end_deg is not None and self.alpha_increment_deg is not None):
            raise ValueError("alpha_start_deg, alpha_end_deg, and alpha_increment_deg must all be provided for a sweep")
        if has_sweep_aoa and self.alpha_start_deg >= self.alpha_end_deg:
            raise ValueError("alpha_start_deg must be less than alpha_end_deg")
        return self


class Assumption(BaseModel):
    """A single inferred decision the parser made on the user's behalf."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    field_path: str = Field(..., description="Dotted path, e.g. 'flow.altitude_m'.")
    value: Any
    reason: str


class ProvenanceMap(BaseModel):
    """Map of dotted field paths to their provenance tag."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    fields: dict[str, Provenance]


class DesignIntent(BaseModel):
    """A complete, validated design intent."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    airfoil: AirfoilSpec | None = None
    wing: WingSpec | None = None
    flow: FlowCondition
    assumptions: list[Assumption] = Field(default_factory=list)
    provenance: ProvenanceMap
    notes: str | None = None

    @model_validator(mode="after")
    def validate_geometry_spec(self) -> "DesignIntent":
        if self.airfoil and self.wing:
            raise ValueError("specify either an airfoil or a wing, not both")
        if not self.airfoil and not self.wing:
            raise ValueError("at least one of airfoil or wing must be provided")
        return self


class ParseResult(BaseModel):
    """Outcome of parsing one natural-language input."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: DesignIntent
    raw_input: str
    model: str
    attempts: int = Field(..., ge=1)
