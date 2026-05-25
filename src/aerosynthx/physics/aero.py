"""Pure aerodynamic primitives.

All functions take SI scalars and return SI scalars. They are pure: no
I/O, no state, no randomness. Domain violations raise :class:`DomainError`
with a stable code.
"""

from __future__ import annotations

import math

from aerosynthx.physics.errors import DomainError

# Defaults match ``aerosynthx.physics.atmosphere``.
DEFAULT_GAMMA_AIR: float = 1.4
DEFAULT_R_AIR_J_KG_K: float = 287.05287


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise DomainError(
            f"{name} must be finite, got {value!r}",
            code="physics.domain.non_finite",
        )


def _require_positive(name: str, value: float) -> None:
    _require_finite(name, value)
    if value <= 0.0:
        raise DomainError(
            f"{name} must be strictly positive, got {value!r}",
            code="physics.domain.non_positive",
        )


def _require_non_negative(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0.0:
        raise DomainError(
            f"{name} must be non-negative, got {value!r}",
            code="physics.domain.negative",
        )


def speed_of_sound(
    temperature_k: float,
    gamma: float = DEFAULT_GAMMA_AIR,
    gas_constant_j_kg_k: float = DEFAULT_R_AIR_J_KG_K,
) -> float:
    """Speed of sound in an ideal gas at ``temperature_k`` (m/s).

    ``a = sqrt(gamma * R * T)``.
    """
    _require_positive("temperature_k", temperature_k)
    _require_positive("gamma", gamma)
    _require_positive("gas_constant_j_kg_k", gas_constant_j_kg_k)
    return math.sqrt(gamma * gas_constant_j_kg_k * temperature_k)


def reynolds_number(
    velocity_m_s: float,
    length_m: float,
    kinematic_viscosity_m2_s: float,
) -> float:
    """Reynolds number ``Re = V * L / nu`` (dimensionless).

    All inputs must be strictly positive.
    """
    _require_positive("velocity_m_s", velocity_m_s)
    _require_positive("length_m", length_m)
    _require_positive("kinematic_viscosity_m2_s", kinematic_viscosity_m2_s)
    return velocity_m_s * length_m / kinematic_viscosity_m2_s


def mach_number(velocity_m_s: float, speed_of_sound_m_s: float) -> float:
    """Mach number ``Ma = V / a`` (dimensionless).

    ``velocity_m_s`` may be zero; ``speed_of_sound_m_s`` must be strictly
    positive.
    """
    _require_non_negative("velocity_m_s", velocity_m_s)
    _require_positive("speed_of_sound_m_s", speed_of_sound_m_s)
    return velocity_m_s / speed_of_sound_m_s


def dynamic_pressure(density_kg_m3: float, velocity_m_s: float) -> float:
    """Dynamic pressure ``q = 0.5 * rho * V**2`` (Pa).

    ``density_kg_m3`` must be strictly positive; ``velocity_m_s`` must be
    non-negative.
    """
    _require_positive("density_kg_m3", density_kg_m3)
    _require_non_negative("velocity_m_s", velocity_m_s)
    return 0.5 * density_kg_m3 * velocity_m_s * velocity_m_s
