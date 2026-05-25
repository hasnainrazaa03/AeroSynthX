"""Tests for ``aerosynthx.physics.units``."""

from __future__ import annotations

import math

import pytest

from aerosynthx.physics import to_si
from aerosynthx.physics.errors import UnitError


class TestHappyPath:
    def test_meter_to_meter(self) -> None:
        assert to_si(1.2, "m", dimension="length") == pytest.approx(1.2)

    def test_feet_to_meter(self) -> None:
        # 1 ft = 0.3048 m exactly
        assert to_si(1.0, "ft", dimension="length") == pytest.approx(0.3048)

    def test_knots_to_m_per_s(self) -> None:
        # 1 kt = 0.5144444... m/s
        assert to_si(1.0, "knot", dimension="velocity") == pytest.approx(0.5144444, rel=1e-5)

    def test_degC_to_kelvin(self) -> None:
        assert to_si(0.0, "degC", dimension="temperature") == pytest.approx(273.15)

    def test_dimensionless_passthrough(self) -> None:
        assert to_si(0.5, "dimensionless", dimension="dimensionless") == pytest.approx(0.5)

    def test_pressure_kpa(self) -> None:
        assert to_si(101.325, "kPa", dimension="pressure") == pytest.approx(101_325.0)

    def test_density_g_per_cm3(self) -> None:
        assert to_si(1.0, "g/cm**3", dimension="density") == pytest.approx(1000.0)

    def test_degree_to_radian(self) -> None:
        assert to_si(180.0, "degree", dimension="angle") == pytest.approx(math.pi)

    def test_without_dimension_uses_base_units(self) -> None:
        # 1 km in base units = 1000 m.
        assert to_si(1.0, "km") == pytest.approx(1000.0)


class TestRejection:
    def test_empty_unit(self) -> None:
        with pytest.raises(UnitError, match="non-empty"):
            to_si(1.0, "")

    def test_whitespace_unit(self) -> None:
        with pytest.raises(UnitError, match="non-empty"):
            to_si(1.0, "   ")

    def test_non_string_unit(self) -> None:
        with pytest.raises(UnitError):
            to_si(1.0, 5)  # type: ignore[arg-type]

    def test_unknown_unit(self) -> None:
        with pytest.raises(UnitError) as excinfo:
            to_si(1.0, "flibberty", dimension="length")
        assert excinfo.value.code == "physics.unit.invalid"

    def test_dimension_mismatch(self) -> None:
        with pytest.raises(UnitError) as excinfo:
            to_si(1.0, "kg", dimension="length")
        assert excinfo.value.code == "physics.unit.dimension_mismatch"

    def test_unknown_dimension_label(self) -> None:
        with pytest.raises(UnitError) as excinfo:
            to_si(1.0, "m", dimension="not_a_real_dimension")
        assert excinfo.value.code == "physics.unit.unknown_dimension"
