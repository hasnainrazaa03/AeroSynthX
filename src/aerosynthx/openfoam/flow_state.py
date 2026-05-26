"""Derive a deterministic ``FlowState`` from a validated ``DesignIntent``.

This module is the bridge between the intent layer (which carries
user-stated and inferred *requested* conditions) and the OpenFOAM
case-writing layer (which needs concrete numeric values in SI units).

Defaults applied when not present in the intent are documented as
constants below; downstream consumers can also re-read the
:class:`FlowState` to inspect what was assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from aerosynthx.intent.schemas import DesignIntent
from aerosynthx.openfoam.errors import EnvelopeViolationError
from aerosynthx.physics.atmosphere import isa_atmosphere

# Defaults for missing intent fields when deriving flow state.
DEFAULT_TURBULENCE_INTENSITY: Final[float] = 0.05  # 5%, typical free-stream
DEFAULT_TURBULENCE_LENGTH_FRACTION: Final[float] = 0.07  # 7% of chord
C_MU: Final[float] = 0.09  # kOmegaSST closure constant
MAX_MACH_INCOMPRESSIBLE: Final[float] = 0.3


@dataclass(frozen=True, slots=True)
class FlowState:
    """Concrete SI flow state ready for CFD case writing.

    All values are deterministic functions of the input
    :class:`DesignIntent` and the US Standard Atmosphere 1976.
    """

    velocity_m_s: float
    velocity_vector_m_s: tuple[float, float, float]
    mach: float
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    kinematic_viscosity_m2_s: float
    reynolds_chord: float
    turbulence_intensity: float
    turbulence_length_scale_m: float
    k_m2_s2: float
    omega_1_s: float


def derive_flow_state(intent: DesignIntent) -> FlowState:
    """Map a :class:`DesignIntent` to a concrete :class:`FlowState`.

    Args:
        intent: A validated design intent. Must satisfy the v0.1
            operating envelope (incompressible, NACA 4-digit).

    Returns:
        A frozen :class:`FlowState`.

    Raises:
        EnvelopeViolationError: If the derived flow state lands
            outside the incompressible envelope (defence in depth).
    """
    altitude = intent.flow.altitude_m if intent.flow.altitude_m is not None else 0.0
    atm = isa_atmosphere(altitude)

    if intent.flow.velocity_m_s is not None:
        u = float(intent.flow.velocity_m_s)
        mach = u / atm.speed_of_sound_m_s
    else:
        # Schema guarantees exactly one of velocity / mach is set.
        assert intent.flow.mach is not None
        mach = float(intent.flow.mach)
        u = mach * atm.speed_of_sound_m_s

    if mach >= MAX_MACH_INCOMPRESSIBLE or not math.isfinite(mach):
        raise EnvelopeViolationError(
            f"derived Mach {mach:.4f} is not strictly below "
            f"{MAX_MACH_INCOMPRESSIBLE} (incompressible envelope)",
        )

    alpha = math.radians(intent.flow.angle_of_attack_deg)
    velocity_vector = (u * math.cos(alpha), u * math.sin(alpha), 0.0)

    chord = float(intent.airfoil.chord_m)
    reynolds = u * chord / atm.kinematic_viscosity_m2_s

    ti = DEFAULT_TURBULENCE_INTENSITY
    length_scale = DEFAULT_TURBULENCE_LENGTH_FRACTION * chord
    k = 1.5 * (u * ti) ** 2
    omega = math.sqrt(k) / (C_MU**0.25 * length_scale)

    return FlowState(
        velocity_m_s=u,
        velocity_vector_m_s=velocity_vector,
        mach=mach,
        altitude_m=altitude,
        temperature_k=atm.temperature_k,
        pressure_pa=atm.pressure_pa,
        density_kg_m3=atm.density_kg_m3,
        kinematic_viscosity_m2_s=atm.kinematic_viscosity_m2_s,
        reynolds_chord=reynolds,
        turbulence_intensity=ti,
        turbulence_length_scale_m=length_scale,
        k_m2_s2=k,
        omega_1_s=omega,
    )
