"""Tests for ``aerosynthx.physics.atmosphere``.

Reference values are from the US Standard Atmosphere 1976 tabulated data
(reproduced in Anderson, *Fundamentals of Aerodynamics*, Appendix C).
Tolerance is 0.5% relative; published tables and the closed-form
formulae agree within table-rounding error.
"""

from __future__ import annotations

import math

import pytest

from aerosynthx.physics import AtmosphereState, isa_atmosphere
from aerosynthx.physics.errors import AtmosphereError

REL_TOL = 5e-3  # 0.5%


# (altitude_m, T_K, P_Pa, rho_kg_m3)
REFERENCE_POINTS: list[tuple[float, float, float, float]] = [
    (0.0, 288.15, 101_325.0, 1.225),
    (1_000.0, 281.65, 89_874.6, 1.1117),
    (5_000.0, 255.65, 54_019.9, 0.7364),
    (11_000.0, 216.65, 22_632.1, 0.36391),
    (15_000.0, 216.65, 12_044.6, 0.19367),
    (20_000.0, 216.65, 5_474.9, 0.08803),
]


@pytest.mark.parametrize(("h", "T", "P", "rho"), REFERENCE_POINTS)
def test_isa_matches_reference(h: float, T: float, P: float, rho: float) -> None:
    state = isa_atmosphere(h)
    assert state.altitude_m == h
    assert state.temperature_k == pytest.approx(T, rel=REL_TOL)
    assert state.pressure_pa == pytest.approx(P, rel=REL_TOL)
    assert state.density_kg_m3 == pytest.approx(rho, rel=REL_TOL)


def test_sea_level_speed_of_sound() -> None:
    state = isa_atmosphere(0.0)
    # a = sqrt(gamma * R * T) at 288.15 K -> ~340.294 m/s
    assert state.speed_of_sound_m_s == pytest.approx(340.294, rel=1e-4)


def test_sea_level_viscosity() -> None:
    state = isa_atmosphere(0.0)
    # Sutherland's law at 288.15 K -> ~1.7894e-5 Pa·s
    assert state.dynamic_viscosity_pa_s == pytest.approx(1.7894e-5, rel=1e-3)
    expected_nu = state.dynamic_viscosity_pa_s / state.density_kg_m3
    assert state.kinematic_viscosity_m2_s == pytest.approx(expected_nu)


def test_tropopause_continuity() -> None:
    # Pressure and temperature must be continuous across the tropopause.
    below = isa_atmosphere(10_999.999)
    above = isa_atmosphere(11_000.001)
    assert below.temperature_k == pytest.approx(above.temperature_k, rel=1e-5)
    assert below.pressure_pa == pytest.approx(above.pressure_pa, rel=1e-5)


def test_stratosphere_is_isothermal() -> None:
    a = isa_atmosphere(12_000.0)
    b = isa_atmosphere(18_000.0)
    assert a.temperature_k == pytest.approx(b.temperature_k)


def test_returns_immutable_state() -> None:
    state = isa_atmosphere(0.0)
    assert isinstance(state, AtmosphereState)
    with pytest.raises(Exception):  # noqa: B017
        state.altitude_m = 999.0  # type: ignore[misc]


@pytest.mark.parametrize("h", [-1.0, -100.0, 20_001.0, 50_000.0])
def test_out_of_range_rejected(h: float) -> None:
    with pytest.raises(AtmosphereError) as excinfo:
        isa_atmosphere(h)
    assert excinfo.value.code == "physics.atmosphere.out_of_range"


@pytest.mark.parametrize("h", [math.nan, math.inf, -math.inf])
def test_non_finite_rejected(h: float) -> None:
    with pytest.raises(AtmosphereError) as excinfo:
        isa_atmosphere(h)
    assert excinfo.value.code == "physics.atmosphere.invalid"
