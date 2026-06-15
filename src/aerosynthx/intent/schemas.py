"""Pydantic v2 schemas for the AeroSynthX intent layer.

These models are the contract between the natural-language layer (LLM
or offline parser) and the downstream engineering pipeline. They enforce
the v0.1 operating envelope:

- 2D incompressible (``mach < 0.3``).
- NACA 4-digit, 5-digit, or custom user-supplied airfoils.
- Exactly one of ``velocity_m_s`` or ``mach`` provided; the other is
  derived downstream by the workflow layer.

The schemas deliberately do NOT compute physics values. Any inferred
defaults that need numerical reasoning are produced upstream (by the
offline parser or LLM) and explicitly recorded in ``provenance`` and
``assumptions``.
"""

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

# Operating envelope constants (mirrored in docs/ARCHITECTURE.md).
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
        """Ensure fields are consistent with the specified family."""
        if self.family == "custom":
            if self.coordinates is None:
                raise ValueError("`coordinates` must be provided for `custom` airfoil family.")
            if self.designation is not None:
                raise ValueError("`designation` must not be provided for `custom` airfoil family.")
        else: # NACA families
            if self.designation is None:
                raise ValueError(f"`designation` must be provided for `{self.family}` airfoil family.")
            if self.coordinates is not None:
                raise ValueError(f"`coordinates` must not be provided for `{self.family}` airfoil family.")

            if not self.designation.isdigit():
                raise ValueError("Designation must contain only digits.")

            if self.family == "naca4":
                if len(self.designation) != 4:
                    raise ValueError("NACA 4-digit designation must be 4 characters long.")
                m = int(self.designation[0])
                p = int(self.designation[1])
                t = int(self.designation[2:4])
                if m > 0 and p == 0:
                    raise ValueError("NACA 4-digit: non-zero camber requires a non-zero camber position.")
                if t == 0:
                    raise ValueError("NACA 4-digit: zero thickness is not a valid airfoil.")

            elif self.family == "naca5":
                if len(self.designation) != 5:
                    raise ValueError("NACA 5-digit designation must be 5 characters long.")
                t = int(self.designation[3:])
                if t == 0:
                    raise ValueError("NACA 5-digit: zero thickness is not a valid airfoil.")

        return self


class FlowCondition(BaseModel):
    """Freestream flow conditions for a 2D analysis.

    Exactly one of ``velocity_m_s`` and ``mach`` must be set; the
    workflow layer computes the missing one from atmosphere.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    altitude_m: float | None = Field(
        default=None,
        description=(
            "Geometric altitude for ISA lookup; required if mach is given without velocity."
        ),
    )
    velocity_m_s: PositiveFloat | None = None
    mach: float | None = Field(default=None, ge=0.0, lt=MAX_MACH_INCOMPRESSIBLE)
    angle_of_attack_deg: float = Field(..., ge=-MAX_ABS_ALPHA_DEG, le=MAX_ABS_ALPHA_DEG)
    reynolds_target: PositiveFloat | None = None

    @field_validator("altitude_m")
    @classmethod
    def _validate_altitude(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < MIN_ALTITUDE_M or v > MAX_ALTITUDE_M:
            raise ValueError(
                f"altitude_m must lie in [{MIN_ALTITUDE_M}, {MAX_ALTITUDE_M}], got {v}"
            )
        return v

    @model_validator(mode="after")
    def _exactly_one_speed(self) -> FlowCondition:
        has_v = self.velocity_m_s is not None
        has_m = self.mach is not None
        if has_v and has_m:
            raise ValueError(
                "specify exactly one of velocity_m_s or mach; the other is derived downstream"
            )
        if not has_v and not has_m:
            raise ValueError("at least one of velocity_m_s or mach must be provided")
        if has_m and self.altitude_m is None:
            raise ValueError("altitude_m is required when mach is provided without velocity_m_s")
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
    """A complete, validated design intent ready for the workflow layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    airfoil: AirfoilSpec
    flow: FlowCondition
    assumptions: list[Assumption] = Field(default_factory=list)
    provenance: ProvenanceMap
    notes: str | None = None


class ParseResult(BaseModel):
    """Outcome of parsing one natural-language input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: DesignIntent
    raw_input: str
    model: str
    attempts: int = Field(..., ge=1)


def design_intent_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for :class:`DesignIntent`.

    Exposed so the LLM client can be given a schema description without
    re-importing Pydantic in the caller.
    """
    return DesignIntent.model_json_schema()
