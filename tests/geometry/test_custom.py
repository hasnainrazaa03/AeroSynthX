"""Tests for the custom airfoil generator."""

import numpy as np
import pytest

from aerosynthx.geometry.custom import custom_airfoil
from aerosynthx.geometry.errors import GeometryError


def _valid_coords() -> list[tuple[float, float]]:
    """Returns a simple valid coordinate list (a triangle for testing)."""
    return [
        (1.0, 0.0),    # TE
        (0.5, 0.1),    # Upper
        (0.0, 0.0),    # LE
        (0.5, -0.1),   # Lower
        (1.0, 0.0),    # TE
    ]


def test_custom_airfoil_valid():
    """Test successful creation from valid coordinates."""
    af = custom_airfoil(_valid_coords(), chord_m=2.0)
    assert af.name == "Custom Airfoil"
    assert af.chord_m == 2.0
    # Coordinates should not be scaled by chord
    assert af.x == (1.0, 0.5, 0.0, 0.5, 1.0)
    assert af.y == (0.0, 0.1, 0.0, -0.1, 0.0)


def test_custom_airfoil_too_few_points():
    """Test rejection of insufficient points."""
    with pytest.raises(GeometryError, match="at least 3 coordinate points"):
        custom_airfoil([(1.0, 0.0), (0.0, 0.0)])


def test_custom_airfoil_not_normalized():
    """Test rejection of non-normalized coordinates."""
    coords = _valid_coords()
    # Shift x coordinates so min is not 0
    shifted = [(x + 0.1, y) for x, y in coords]
    with pytest.raises(GeometryError, match="must be normalized"):
        custom_airfoil(shifted)

    # Scale x coordinates so max is not 1
    scaled = [(x * 2.0, y) for x, y in coords]
    with pytest.raises(GeometryError, match="must be normalized"):
        custom_airfoil(scaled)


def test_custom_airfoil_fails_validation():
    """Test that underlying geometry validation failures are wrapped."""
    # Make the airfoil non-monotonic on the upper surface (x increases from 0.3 to 0.5)
    coords = [
        (1.0, 0.0),    # TE
        (0.3, 0.1),    # Upper 1
        (0.5, 0.08),   # Upper 2 (violation)
        (0.0, 0.0),    # LE
        (0.5, -0.1),   # Lower
        (1.0, 0.0),    # TE
    ]

    with pytest.raises(GeometryError, match="Invalid custom airfoil coordinates"):
        custom_airfoil(coords)

