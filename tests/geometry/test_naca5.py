from pathlib import Path
import numpy as np
import pytest

from aerosynthx.geometry.errors import GeometryError
from aerosynthx.geometry.naca5 import naca5

# Get the directory of the current test file
TEST_DIR = Path(__file__).parent.resolve()


def test_naca5_valid_generation():
    """Test basic successful generation of a 5-digit airfoil."""
    af = naca5("23012", n_points=50)
    assert af.name == "NACA 23012"
    assert len(af.x) == len(af.y)
    assert len(af.x) > 0


def test_naca5_invalid_designations():
    """Test that invalid designations raise GeometryError."""
    with pytest.raises(GeometryError, match="not a valid 5-digit"):
        naca5("1234")  # too short

    with pytest.raises(GeometryError, match="not a valid 5-digit"):
        naca5("123456")  # too long

    with pytest.raises(GeometryError, match="not a valid 5-digit"):
        naca5("abcde")  # not digits


def test_naca5_unsupported_reflex():
    """Test that reflex camber (3rd digit != 0) is rejected."""
    with pytest.raises(GeometryError, match="Reflex camber"):
        naca5("23112")


def test_naca5_invalid_p_digit():
    """Test that p-digit = 0 is rejected."""
    with pytest.raises(GeometryError, match="P-digit cannot be zero"):
        naca5("20012")


def test_naca5_unsupported_profile():
    """Test that unsupported camber profiles are rejected."""
    # 260 is not in M_LUT
    with pytest.raises(GeometryError, match="Unsupported camber profile"):
        naca5("26012")


def test_naca5_closed_trailing_edge():
    """Test the closed_trailing_edge parameter."""
    af_closed = naca5("23012", n_points=50, closed_trailing_edge=True)
    af_open = naca5("23012", n_points=50, closed_trailing_edge=False)

    # For a closed TE, the start and end y-coords should be identical.
    assert af_closed.y[0] == af_closed.y[-1]

    # For an open TE, they should be different.
    assert af_open.y[0] != af_open.y[-1]


def test_naca5_golden_file_comparison():
    """Compare generated coordinates against a known-good reference file."""
    ref_path = TEST_DIR / "naca23012.dat"
    ref_coords = np.loadtxt(ref_path, skiprows=1)

    # Generate coordinates with the correct number of points to match the reference file
    total_points = ref_coords.shape[0]
    n_points = (total_points + 1) // 2
    af = naca5("23012", n_points=n_points, closed_trailing_edge=False)

    generated_coords = np.array([af.x, af.y]).T

    # Assert that the generated coordinates are very close to the reference file
    np.testing.assert_allclose(generated_coords, ref_coords, atol=1e-6, rtol=0)
