"""US Standard Atmosphere 1976 (0 to 20 km).

Closed-form implementation covering:

- Troposphere: 0 to 11 000 m geopotential altitude, lapse rate -6.5 K/km.
- Lower stratosphere: 11 000 to 20 000 m, isothermal at 216.65 K.

Dynamic viscosity uses Sutherland's law for air.

Altitudes outside ``[0, 20 000] m`` raise :class:`AtmosphereError`.

References:
- U.S. Standard Atmosphere, 1976, NOAA-S/T 76-1562.
- Anderson, *Fundamentals of Aerodynamics*, 6th ed., Appendix C.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from aerosynthx.physics.errors import AtmosphereError

# --- Physical constants (US Std Atm 1976) ---
T0: Final[float] = 288.15  # K, sea-level temperature
P0: Final[float] = 101_325.0  # Pa, sea-level pressure
G0: Final[float] = 9.80665  # m/s^2, standard gravity
R_AIR: Final[float] = 287.05287  # J/(kg·K), specific gas constant, dry air
GAMMA_AIR: Final[float] = 1.4  # ratio of specific heats, diatomic ideal

# --- Layer boundaries ---
H_TROPOPAUSE: Final[float] = 11_000.0  # m
H_MAX: Final[float] = 20_000.0  # m, v0.1 envelope upper bound
LAPSE_TROPO: Final[float] = -6.5e-3  # K/m

# Conditions at the tropopause, computed once at module load:
_T_TROPOPAUSE: Final[float] = T0 + LAPSE_TROPO * H_TROPOPAUSE  # 216.65 K
_P_TROPOPAUSE: Final[float] = P0 * (_T_TROPOPAUSE / T0) ** (-G0 / (LAPSE_TROPO * R_AIR))

# --- Sutherland's law for air ---
SUTHERLAND_C1: Final[float] = 1.458e-6  # kg/(m·s·K^0.5)
SUTHERLAND_S: Final[float] = 110.4  # K


@dataclass(frozen=True, slots=True)
class AtmosphereState:
    """Atmospheric state at a single altitude.

    All values are SI. ``altitude_m`` is the input geopotential altitude.
    """

    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float
    dynamic_viscosity_pa_s: float
    kinematic_viscosity_m2_s: float


def _sutherland_viscosity(temperature_k: float) -> float:
    """Dynamic viscosity of air via Sutherland's law (Pa-s)."""
    return float(SUTHERLAND_C1 * temperature_k**1.5 / (temperature_k + SUTHERLAND_S))


def isa_atmosphere(altitude_m: float) -> AtmosphereState:
    """Compute the US Standard Atmosphere 1976 state at ``altitude_m``.

    Args:
        altitude_m: Geopotential altitude in meters. Must be within
            ``[0, 20 000]``.

    Returns:
        An :class:`AtmosphereState` at the requested altitude.

    Raises:
        AtmosphereError: If ``altitude_m`` is outside the supported range.
    """
    if not math.isfinite(altitude_m):
        raise AtmosphereError(
            f"altitude must be finite, got {altitude_m!r}",
            code="physics.atmosphere.invalid",
        )
    if altitude_m < 0.0 or altitude_m > H_MAX:
        raise AtmosphereError(
            f"altitude {altitude_m} m outside supported range [0, {H_MAX:.0f}] m",
            code="physics.atmosphere.out_of_range",
        )

    if altitude_m <= H_TROPOPAUSE:
        # Linear-lapse troposphere.
        temperature = T0 + LAPSE_TROPO * altitude_m
        pressure = P0 * (temperature / T0) ** (-G0 / (LAPSE_TROPO * R_AIR))
    else:
        # Isothermal lower stratosphere.
        temperature = _T_TROPOPAUSE
        pressure = _P_TROPOPAUSE * math.exp(
            -G0 * (altitude_m - H_TROPOPAUSE) / (R_AIR * _T_TROPOPAUSE)
        )

    density = pressure / (R_AIR * temperature)
    sos = math.sqrt(GAMMA_AIR * R_AIR * temperature)
    mu = _sutherland_viscosity(temperature)
    nu = mu / density

    return AtmosphereState(
        altitude_m=altitude_m,
        temperature_k=temperature,
        pressure_pa=pressure,
        density_kg_m3=density,
        speed_of_sound_m_s=sos,
        dynamic_viscosity_pa_s=mu,
        kinematic_viscosity_m2_s=nu,
    )
