"""Unit tests for ``aerosynthx.physics.errors``."""

from __future__ import annotations

import pytest

from aerosynthx.physics import errors as E


def test_hierarchy_is_correct() -> None:
    assert issubclass(E.PhysicsError, E.AeroSynthXError)
    assert issubclass(E.UnitError, E.PhysicsError)
    assert issubclass(E.DomainError, E.PhysicsError)
    assert issubclass(E.AtmosphereError, E.PhysicsError)


def test_codes_are_stable() -> None:
    # Codes are part of the public contract. Pin them here.
    assert E.AeroSynthXError.code == "aerosynthx.error"
    assert E.PhysicsError.code == "physics.error"
    assert E.UnitError.code == "physics.unit.invalid"
    assert E.DomainError.code == "physics.domain.invalid"
    assert E.AtmosphereError.code == "physics.atmosphere.out_of_range"


def test_instance_code_override() -> None:
    err = E.UnitError("bad", code="physics.unit.dimension_mismatch")
    assert err.code == "physics.unit.dimension_mismatch"


def test_repr_includes_code() -> None:
    err = E.DomainError("velocity_m_s must be positive")
    msg = str(err)
    assert "physics.domain.invalid" in msg
    assert "velocity_m_s" in msg


def test_can_be_raised_and_caught_as_base() -> None:
    with pytest.raises(E.AeroSynthXError):
        raise E.UnitError("bad unit")
