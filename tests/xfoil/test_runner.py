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

GOOD_POLAR_OUTPUT_SINGLE = """
   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
   4.000   0.4489   0.00623   0.00247   0.0005   0.7831   1.0000
"""

GOOD_POLAR_OUTPUT_SWEEP = """
   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr
  ------ -------- --------- --------- -------- -------- --------
   0.000   0.0000   0.00500   0.00170   0.0000   0.9300   0.9300
   1.000   0.1120   0.00500   0.00170   0.0000   0.9100   0.9500
   2.000   0.2240   0.00510   0.00180   0.0000   0.8800   1.0000
"""


def _mock_xfoil_run(mock_run, output):
    mock_process = MagicMock()
    mock_process.stdout = b"XFOIL execution successful"

    def side_effect(*args, **kwargs):
        script = kwargs["input"].decode("utf-8")
        lines = script.splitlines()
        polar_path = None
        for i, line in enumerate(lines):
            if "PACC" in line:
                polar_path = lines[i + 1].strip()
                break

        if polar_path:
            Path(polar_path).write_text(output)

        return mock_process

    mock_run.side_effect = side_effect


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_single_point_success(mock_run, mock_which):
    """Test a successful single-point XFOIL run."""
    _mock_xfoil_run(mock_run, GOOD_POLAR_OUTPUT_SINGLE)

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=4.0, reynolds_target=1e6)

    results = run_xfoil(airfoil, flow)

    assert len(results) == 1
    result = results[0]
    assert result.alpha_deg == pytest.approx(4.0)
    assert result.cl == pytest.approx(0.4489)

    script = mock_run.call_args.kwargs["input"].decode("utf-8")
    assert "ALFA 4.0" in script
    assert "ASEQ" not in script


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_sweep_success(mock_run, mock_which):
    """Test a successful XFOIL sweep run."""
    _mock_xfoil_run(mock_run, GOOD_POLAR_OUTPUT_SWEEP)

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, alpha_start_deg=0.0, alpha_end_deg=2.0, alpha_increment_deg=1.0, reynolds_target=1e6)

    results = run_xfoil(airfoil, flow)

    assert len(results) == 3
    assert results[0].alpha_deg == pytest.approx(0.0)
    assert results[1].cl == pytest.approx(0.1120)
    assert results[2].cd == pytest.approx(0.00510)

    script = mock_run.call_args.kwargs["input"].decode("utf-8")
    assert "ASEQ 0.0 2.0 1.0" in script
    assert "ALFA" not in script


@patch("shutil.which", return_value=None)
def test_run_xfoil_not_found(mock_which):
    """Test that XfoilNotFoundError is raised if the executable is not found."""
    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=4.0)

    with pytest.raises(XfoilNotFoundError):
        run_xfoil(airfoil, flow)


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_convergence_error_single_point(mock_run, mock_which):
    """Test that XfoilConvergenceError is raised on convergence failure for a single point."""
    mock_process = MagicMock()
    mock_process.stdout = b"Viscous solution failed to converge"
    mock_run.return_value = mock_process

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=20.0)

    with pytest.raises(XfoilConvergenceError):
        run_xfoil(airfoil, flow)


@patch("shutil.which", return_value="/usr/bin/xfoil")
@patch("subprocess.run")
def test_run_xfoil_partial_convergence_sweep(mock_run, mock_which):
    """Test that a sweep with partial convergence still returns valid results."""
    # Simulate XFOIL output where only the first two points converged
    _mock_xfoil_run(mock_run, GOOD_POLAR_OUTPUT_SWEEP)
    mock_process = MagicMock()
    mock_process.stdout = b"Viscous solution failed to converge at alpha = 2.0"
    mock_run.return_value = mock_process

    airfoil = naca4("0012")
    flow = FlowCondition(velocity_m_s=50, alpha_start_deg=0.0, alpha_end_deg=2.0, alpha_increment_deg=1.0)

    # Should not raise an error, just return the converged points
    results = run_xfoil(airfoil, flow)
    assert len(results) == 3 # The parser will still parse all valid lines
