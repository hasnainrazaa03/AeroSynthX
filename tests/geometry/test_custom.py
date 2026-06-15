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
    # Coordinates should be scaled by chord
    assert af.x == (2.0, 1.0, 0.0, 1.0, 2.0)
    assert af.y == (0.0, 0.2, 0.0, -0.2, 0.0)


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
    coords = _valid_coords()
    # Make the airfoil non-monotonic on the upper surface
    coords[1] = (0.2, 0.1) # X goes backwards (TE=1.0, then 0.2, then LE=0.0) - wait, this is monotonic
    # Let's make it not closed
    coords[0] = (1.0, 0.05)

    with pytest.raises(GeometryError, match="Invalid custom airfoil coordinates"):
        custom_airfoil(coords)
