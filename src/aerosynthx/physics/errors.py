"""Typed exception hierarchy for AeroSynthX.

Every error carries a stable, dotted ``code`` string. Codes are part of
the public contract and only change with a MAJOR version bump.
"""

from __future__ import annotations


class AeroSynthXError(Exception):
    """Root of all AeroSynthX exceptions.

    Subclasses must set a class-level ``code`` attribute. The code is
    a stable, dotted, lowercase identifier (e.g. ``physics.unit.invalid``)
    used at API boundaries for machine-readable error responses.
    """

    code: str = "aerosynthx.error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Render as ``[code] message``."""
        return f"[{self.code}] {super().__str__()}"


class PhysicsError(AeroSynthXError):
    """Base class for errors raised by ``aerosynthx.physics``."""

    code = "physics.error"


class UnitError(PhysicsError):
    """Raised for invalid unit strings or dimension mismatches."""

    code = "physics.unit.invalid"


class DomainError(PhysicsError):
    """Raised when a numeric input is outside the function's valid domain."""

    code = "physics.domain.invalid"


class AtmosphereError(PhysicsError):
    """Raised when an atmosphere query is outside the supported altitude range."""

    code = "physics.atmosphere.out_of_range"
