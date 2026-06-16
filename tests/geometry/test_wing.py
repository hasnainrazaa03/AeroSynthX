"""Tests for the 3D Wing generator."""

import numpy as np
import pytest

from aerosynthx.geometry.wing import Wing, generate_wing
from aerosynthx.intent.schemas import AirfoilSpec, WingSpec


def _basic_wing_spec() -> WingSpec:
    return WingSpec(
        span=10.0,
        root_chord=1.0,
        tip_chord=0.5,
        sweep_deg=0.0,
        dihedral_deg=0.0,
        twist_deg=0.0,
        root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=0.5),
    )


def test_generate_wing_basic():
    """Test generating a simple untapered, unswept wing."""
    # Use the same chord for root and tip to keep it simple
    spec = WingSpec(
        span=10.0,
        sweep_deg=0.0,
        dihedral_deg=0.0,
        twist_deg=0.0,
        root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
    )
    wing = generate_wing(spec, n_stations=3)

    assert isinstance(wing, Wing)
    assert wing.span == 10.0
    assert wing.root_chord == 1.0
    assert wing.tip_chord == 1.0
    assert len(wing.coordinates) == 3

    # Root station (z=0, wait our y is spanwise so y=0)
    root_points = wing.coordinates[0]
    # Check LE is at origin
    le_root = min(root_points, key=lambda p: p[0])
    assert np.isclose(le_root[0], 0.0)
    assert np.isclose(le_root[1], 0.0) # spanwise
    assert np.isclose(le_root[2], 0.0)

    # Tip station (y=5.0 for half span)
    tip_points = wing.coordinates[-1]
    le_tip = min(tip_points, key=lambda p: p[0])
    assert np.isclose(le_tip[0], 0.0)
    assert np.isclose(le_tip[1], 5.0) # spanwise half span
    assert np.isclose(le_tip[2], 0.0)


def test_generate_wing_with_sweep():
    """Test generating a swept wing."""
    spec = WingSpec(
        span=10.0,
        sweep_deg=45.0,
        root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
    )
    wing = generate_wing(spec, n_stations=2)

    root_points = wing.coordinates[0]
    tip_points = wing.coordinates[-1]

    le_root = min(root_points, key=lambda p: p[0])
    le_tip = min(tip_points, key=lambda p: p[0])

    # Sweep angle is 45 deg, so delta_x should equal delta_y
    delta_x = le_tip[0] - le_root[0]
    delta_y = le_tip[1] - le_root[1]
    assert np.isclose(delta_x, delta_y)
    assert np.isclose(delta_y, 5.0) # Half span


def test_generate_wing_with_dihedral():
    """Test generating a wing with dihedral."""
    spec = WingSpec(
        span=10.0,
        dihedral_deg=10.0,
        root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
    )
    wing = generate_wing(spec, n_stations=2)

    root_points = wing.coordinates[0]
    tip_points = wing.coordinates[-1]

    le_root = min(root_points, key=lambda p: p[0])
    le_tip = min(tip_points, key=lambda p: p[0])

    # Dihedral angle is 10 deg, so delta_z = delta_y * tan(10 deg)
    delta_y = le_tip[1] - le_root[1]
    delta_z = le_tip[2] - le_root[2]
    expected_z = delta_y * np.tan(np.radians(10.0))
    assert np.isclose(delta_z, expected_z)


def test_generate_wing_with_twist():
    """Test generating a twisted wing."""
    spec = WingSpec(
        span=10.0,
        twist_deg=5.0, # 5 degrees washout at tip
        root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
    )
    wing = generate_wing(spec, n_stations=2)

    root_points = wing.coordinates[0]
    tip_points = wing.coordinates[-1]

    # TE point should be rotated up (positive z) at the tip compared to the root
    te_root = max(root_points, key=lambda p: p[0])
    te_tip = max(tip_points, key=lambda p: p[0])

    # Since LE is origin and chord is 1, TE is at x=1.
    # With 5 deg twist, z = 1 * sin(5 deg)
    expected_z = np.sin(np.radians(5.0))
    assert np.isclose(te_tip[2], expected_z, atol=1e-3)


def test_generate_wing_default_tip():
    """Test that tip airfoil defaults to root airfoil profile."""
    spec = WingSpec(
        span=10.0,
        root_airfoil=AirfoilSpec(family="naca4", designation="2412", chord_m=2.0),
        # No tip airfoil provided
    )
    wing = generate_wing(spec, n_stations=2)
    assert wing.tip_airfoil.name == wing.root_airfoil.name
    assert wing.tip_chord == 2.0
