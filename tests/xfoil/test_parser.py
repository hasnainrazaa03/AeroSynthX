"""Tests for the XFOIL output parser."""

import pytest

from aerosynthx.xfoil.errors import XfoilParseError
from aerosynthx.xfoil.parser import parse_polar_file

GOOD_POLAR = """
 XFOIL         Version 6.99

 Calculated polar for: NACA 0012

 1 Reynolds number fixed          Mach number fixed

 xtrf =   1.000 (top)        1.000 (bottom)
 Mach =   0.000     Re =     1.000 e 6     Ncrit =   9.000

   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
   0.000   0.0000   0.00494   0.00164   0.0000   0.9416   0.9416
   1.000   0.1118   0.00498   0.00166   0.0001   0.9022   0.9702
   2.000   0.2235   0.00511   0.00175   0.0002   0.8604   1.0000
"""

EMPTY_POLAR = """
 XFOIL         Version 6.99
"""

NO_DATA_POLAR = """
 XFOIL         Version 6.99
   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
"""


def test_parse_polar_file_first_row():
    """Test parsing the first data row when no target alpha is given."""
    result = parse_polar_file(GOOD_POLAR)
    assert result.alpha_deg == pytest.approx(0.0)
    assert result.cl == pytest.approx(0.0)
    assert result.cd == pytest.approx(0.00494)
    assert result.cm == pytest.approx(0.0)


def test_parse_polar_file_with_target_alpha():
    """Test finding a specific row by alpha."""
    result = parse_polar_file(GOOD_POLAR, target_alpha=2.0)
    assert result.alpha_deg == pytest.approx(2.0)
    assert result.cl == pytest.approx(0.2235)
    assert result.cd == pytest.approx(0.00511)
    assert result.cm == pytest.approx(0.0002)


def test_parse_polar_file_target_not_found():
    """Test that an error is raised if the target alpha is not in the file."""
    with pytest.raises(XfoilParseError, match="No data found"):
        parse_polar_file(GOOD_POLAR, target_alpha=3.0)


def test_parse_polar_file_empty_file():
    """Test that an error is raised for an empty or malformed file."""
    with pytest.raises(XfoilParseError, match="No data rows found"):
        parse_polar_file(EMPTY_POLAR)


def test_parse_polar_file_no_data_rows():
    """Test that an error is raised if the file has headers but no data."""
    with pytest.raises(XfoilParseError, match="No data rows found"):
        parse_polar_file(NO_DATA_POLAR)
