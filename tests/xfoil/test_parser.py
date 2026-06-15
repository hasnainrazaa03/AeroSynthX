"""Tests for the XFOIL output parser."""

import pytest

from aerosynthx.xfoil.errors import XfoilParseError
from aerosynthx.xfoil.parser import parse_polar_file

GOOD_POLAR_SINGLE = """
 XFOIL         Version 6.99
   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
   2.000   0.2235   0.00511   0.00175   0.0002   0.8604   1.0000
"""

GOOD_POLAR_SWEEP = """
 XFOIL         Version 6.99
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


def test_parse_polar_file_single_row():
    """Test parsing a polar file with a single data row."""
    results = parse_polar_file(GOOD_POLAR_SINGLE)
    assert len(results) == 1
    assert results[0].alpha_deg == pytest.approx(2.0)
    assert results[0].cl == pytest.approx(0.2235)


def test_parse_polar_file_multiple_rows():
    """Test parsing a polar file with multiple data rows from a sweep."""
    results = parse_polar_file(GOOD_POLAR_SWEEP)
    assert len(results) == 3
    assert results[0].alpha_deg == pytest.approx(0.0)
    assert results[1].alpha_deg == pytest.approx(1.0)
    assert results[2].alpha_deg == pytest.approx(2.0)
    assert results[1].cl == pytest.approx(0.1118)


def test_parse_polar_file_empty_file_returns_empty_list():
    """Test that an empty or malformed file returns an empty list."""
    results = parse_polar_file(EMPTY_POLAR)
    assert results == []


def test_parse_polar_file_no_data_rows_returns_empty_list():
    """Test that a file with headers but no data returns an empty list."""
    results = parse_polar_file(NO_DATA_POLAR)
    assert results == []
