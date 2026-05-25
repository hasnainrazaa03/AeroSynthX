"""Deterministic engineering physics core.

Public API:

- ``to_si`` -- convert a value with a unit string into a canonical SI float.
- ``isa_atmosphere`` -- US Standard Atmosphere 1976 query (0 to 20 km).
- ``AtmosphereState`` -- immutable result of an atmosphere query.
- ``speed_of_sound`` / ``reynolds_number`` / ``mach_number`` /
  ``dynamic_pressure`` -- pure aerodynamic formulae.
- Exception hierarchy: ``AeroSynthXError`` -> ``PhysicsError`` ->
  ``UnitError``, ``DomainError``, ``AtmosphereError``.

Everything in this package is pure: no I/O, no globals (apart from a
shared ``pint`` registry kept inside ``units``), no randomness.
"""

from __future__ import annotations

from aerosynthx.physics.aero import (
    dynamic_pressure,
    mach_number,
    reynolds_number,
    speed_of_sound,
)
from aerosynthx.physics.atmosphere import AtmosphereState, isa_atmosphere
from aerosynthx.physics.errors import (
    AeroSynthXError,
    AtmosphereError,
    DomainError,
    PhysicsError,
    UnitError,
)
from aerosynthx.physics.units import to_si

__all__ = [
    "AeroSynthXError",
    "AtmosphereError",
    "AtmosphereState",
    "DomainError",
    "PhysicsError",
    "UnitError",
    "dynamic_pressure",
    "isa_atmosphere",
    "mach_number",
    "reynolds_number",
    "speed_of_sound",
    "to_si",
]
