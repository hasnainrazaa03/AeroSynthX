"""Tests for the XFOIL runner."""

import re
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aerosynthx.geometry.naca4 import naca4
from aerosynthx.intent.schemas import FlowCondition
from aerosynthx.xfoil.errors import XfoilConvergenceError, XfoilNotFoundError
from aerosynthx.xfoil.runner import run_xfoil

GOOD_POLAR_OUTPUT = """
   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
   4.000   0.4489   0.00623   0.00247   0.0005   0.7831   1.0000
"""


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_success(mock_run, mock_which):
    """Test a successful XFOIL run."""
    # Mock the subprocess to simulate XFOIL creating a polar file
    mock_process = MagicMock()
    mock_process.stdout = b"XFOIL execution successful"

    def side_effect(*args, **kwargs):
        # Extract the polar file path from the script passed to xfoil
        script = kwargs["input"].decode("utf-8")
        # Find the line after PACC, which contains the polar file path
        lines = script.splitlines()
        polar_path = None
        for i, line in enumerate(lines):
            if "PACC" in line:
                polar_path = lines[i + 1].strip()
                break

        if polar_path:
            Path(polar_path).write_text(GOOD_POLAR_OUTPUT)

        return mock_process

    mock_run.side_effect = side_effect

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=4.0, reynolds_target=1e6)

    result = run_xfoil(airfoil, flow)

    assert result.alpha_deg == pytest.approx(4.0)
    assert result.cl == pytest.approx(0.4489)
    assert result.cd == pytest.approx(0.00623)
    assert result.cm == pytest.approx(0.0005)

    # Check that xfoil was called with the correct input
    call_args = mock_run.call_args
    script = call_args.kwargs["input"].decode("utf-8")
    assert "LOAD" in script
    assert "OPER" in script
    assert "VISC 1000000.0" in script
    assert "ALFA 4.0" in script


@patch("shutil.which", return_value=None)
def test_run_xfoil_not_found(mock_which):
    """Test that XfoilNotFoundError is raised if the executable is not found."""
    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=4.0)

    with pytest.raises(XfoilNotFoundError):
        run_xfoil(airfoil, flow)


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_convergence_error(mock_run, mock_which):
    """Test that XfoilConvergenceError is raised on convergence failure."""
    mock_process = MagicMock()
    mock_process.stdout = b"Viscous solution failed to converge"
    mock_run.return_value = mock_process

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=20.0) # High AoA likely to fail

    with pytest.raises(XfoilConvergenceError):
        run_xfoil(airfoil, flow)
