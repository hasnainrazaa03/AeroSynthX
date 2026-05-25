"""Tests for ``aerosynthx.physics.aero``."""

from __future__ import annotations

import math

import pytest

from aerosynthx.physics import (
    dynamic_pressure,
    isa_atmosphere,
    mach_number,
    reynolds_number,
    speed_of_sound,
)
from aerosynthx.physics.errors import DomainError


class TestSpeedOfSound:
    def test_sea_level(self) -> None:
        assert speed_of_sound(288.15) == pytest.approx(340.294, rel=1e-4)

    def test_scales_with_sqrt_t(self) -> None:
        a1 = speed_of_sound(288.15)
        a2 = speed_of_sound(4 * 288.15)
        assert a2 / a1 == pytest.approx(2.0, rel=1e-9)

    def test_custom_gas(self) -> None:
        # Helium-ish (gamma=5/3, R=2077) just to ensure parameters are honored.
        a = speed_of_sound(288.15, gamma=5.0 / 3.0, gas_constant_j_kg_k=2077.0)
        expected = math.sqrt(5.0 / 3.0 * 2077.0 * 288.15)
        assert a == pytest.approx(expected)

    @pytest.mark.parametrize("bad_T", [0.0, -1.0, math.nan])
    def test_temperature_must_be_positive(self, bad_T: float) -> None:
        with pytest.raises(DomainError):
            speed_of_sound(bad_T)

    def test_gamma_must_be_positive(self) -> None:
        with pytest.raises(DomainError):
            speed_of_sound(288.15, gamma=0.0)

    def test_R_must_be_positive(self) -> None:
        with pytest.raises(DomainError):
            speed_of_sound(288.15, gas_constant_j_kg_k=-1.0)


class TestReynolds:
    def test_known_value(self) -> None:
        # V = 50 m/s, L = 1.2 m, nu = 1.5e-5 m²/s -> 4e6
        assert reynolds_number(50.0, 1.2, 1.5e-5) == pytest.approx(50.0 * 1.2 / 1.5e-5)

    def test_uses_sea_level_atmosphere(self) -> None:
        atm = isa_atmosphere(0.0)
        re = reynolds_number(50.0, 1.2, atm.kinematic_viscosity_m2_s)
        # Sanity: at sea level, V=50, L=1.2 -> O(4e6)
        assert 3e6 < re < 5e6

    @pytest.mark.parametrize(
        ("v", "L", "nu"),
        [(0.0, 1.0, 1e-5), (-1.0, 1.0, 1e-5), (1.0, 0.0, 1e-5), (1.0, 1.0, 0.0)],
    )
    def test_rejects_non_positive(self, v: float, L: float, nu: float) -> None:
        with pytest.raises(DomainError):
            reynolds_number(v, L, nu)


class TestMach:
    def test_known_value(self) -> None:
        assert mach_number(170.147, 340.294) == pytest.approx(0.5, rel=1e-4)

    def test_zero_velocity_allowed(self) -> None:
        assert mach_number(0.0, 340.0) == 0.0

    def test_negative_velocity_rejected(self) -> None:
        with pytest.raises(DomainError):
            mach_number(-1.0, 340.0)

    def test_zero_sos_rejected(self) -> None:
        with pytest.raises(DomainError):
            mach_number(50.0, 0.0)


class TestDynamicPressure:
    def test_known_value(self) -> None:
        # q = 0.5 * 1.225 * 50^2 = 1531.25 Pa
        assert dynamic_pressure(1.225, 50.0) == pytest.approx(1531.25)

    def test_zero_velocity(self) -> None:
        assert dynamic_pressure(1.225, 0.0) == 0.0

    @pytest.mark.parametrize(("rho", "v"), [(0.0, 50.0), (-1.0, 50.0), (1.225, -1.0)])
    def test_rejects_bad_inputs(self, rho: float, v: float) -> None:
        with pytest.raises(DomainError):
            dynamic_pressure(rho, v)
