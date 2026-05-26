"""Tests for ``aerosynthx.openfoam.flow_state``."""

from __future__ import annotations

import math

import pytest

from aerosynthx.intent.schemas import (
    AirfoilSpec,
    DesignIntent,
    FlowCondition,
    ProvenanceMap,
)
from aerosynthx.openfoam.errors import EnvelopeViolationError
from aerosynthx.openfoam.flow_state import (
    C_MU,
    DEFAULT_TURBULENCE_INTENSITY,
    DEFAULT_TURBULENCE_LENGTH_FRACTION,
    derive_flow_state,
)


def _intent(
    *,
    velocity_m_s: float | None = 50.0,
    mach: float | None = None,
    altitude_m: float | None = None,
    aoa_deg: float = 0.0,
    chord_m: float = 1.0,
) -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(family="naca4", designation="2412", chord_m=chord_m),
        flow=FlowCondition(
            altitude_m=altitude_m,
            velocity_m_s=velocity_m_s,
            mach=mach,
            angle_of_attack_deg=aoa_deg,
        ),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes=None,
    )


def test_velocity_path_sea_level() -> None:
    state = derive_flow_state(_intent(velocity_m_s=50.0, aoa_deg=0.0, chord_m=1.0))
    assert state.velocity_m_s == pytest.approx(50.0)
    assert state.velocity_vector_m_s[0] == pytest.approx(50.0)
    assert state.velocity_vector_m_s[1] == pytest.approx(0.0, abs=1e-12)
    assert state.velocity_vector_m_s[2] == 0.0
    assert state.altitude_m == 0.0
    # Sea-level ISA cross-checks.
    assert state.temperature_k == pytest.approx(288.15)
    assert state.density_kg_m3 == pytest.approx(1.225, rel=1e-3)
    # Sea-level speed of sound ~ 340.29 m/s.
    assert state.mach == pytest.approx(50.0 / 340.29, rel=1e-3)
    assert 0 < state.mach < 0.3


def test_mach_path_uses_speed_of_sound() -> None:
    state = derive_flow_state(_intent(velocity_m_s=None, mach=0.2, altitude_m=2000.0))
    assert state.altitude_m == 2000.0
    # U = mach * a; a at 2000 m ~ 332.5 m/s.
    assert state.velocity_m_s == pytest.approx(0.2 * 332.5, rel=1e-2)


def test_aoa_rotates_velocity_vector() -> None:
    state = derive_flow_state(_intent(velocity_m_s=10.0, aoa_deg=20.0))
    ux, uy, _ = state.velocity_vector_m_s
    assert ux == pytest.approx(10.0 * math.cos(math.radians(20.0)))
    assert uy == pytest.approx(10.0 * math.sin(math.radians(20.0)))


def test_reynolds_and_turbulence_formulas() -> None:
    chord = 0.5
    u = 30.0
    state = derive_flow_state(_intent(velocity_m_s=u, chord_m=chord, altitude_m=0.0, aoa_deg=0.0))
    expected_re = u * chord / state.kinematic_viscosity_m2_s
    assert state.reynolds_chord == pytest.approx(expected_re)
    assert state.turbulence_intensity == DEFAULT_TURBULENCE_INTENSITY
    assert state.turbulence_length_scale_m == pytest.approx(
        DEFAULT_TURBULENCE_LENGTH_FRACTION * chord
    )
    expected_k = 1.5 * (u * DEFAULT_TURBULENCE_INTENSITY) ** 2
    assert state.k_m2_s2 == pytest.approx(expected_k)
    expected_omega = math.sqrt(expected_k) / (
        C_MU**0.25 * DEFAULT_TURBULENCE_LENGTH_FRACTION * chord
    )
    assert state.omega_1_s == pytest.approx(expected_omega)


def test_rejects_supersonic_envelope_violation() -> None:
    # Schema would normally block this, but we exercise the defensive
    # check by constructing a borderline case at altitude where Mach
    # exceeds 0.3 even though velocity_m_s alone passed the schema.
    # 110 m/s at sea level -> Mach ~0.323 -> envelope violation.
    intent = _intent(velocity_m_s=110.0, altitude_m=0.0)
    with pytest.raises(EnvelopeViolationError) as exc:
        derive_flow_state(intent)
    assert exc.value.code == "openfoam.envelope.violation"
