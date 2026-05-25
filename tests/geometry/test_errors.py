"""Tests for the typed :class:`GeometryError` hierarchy."""

from __future__ import annotations

from aerosynthx.geometry.errors import GeometryError
from aerosynthx.physics.errors import AeroSynthXError


def test_geometry_error_inherits_aerosynthx_error() -> None:
    assert issubclass(GeometryError, AeroSynthXError)


def test_default_code_is_geometry_error() -> None:
    exc = GeometryError("boom")
    assert exc.code == "geometry.error"
    assert str(exc) == "[geometry.error] boom"


def test_code_override_is_preserved() -> None:
    exc = GeometryError("bad", code="geometry.test.case")
    assert exc.code == "geometry.test.case"
    assert "[geometry.test.case]" in str(exc)
