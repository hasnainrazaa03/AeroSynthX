"""Integration tests for the XFOIL runner."""

import shutil

import pytest

from aerosynthx.geometry.naca4 import naca4
from aerosynthx.intent.schemas import FlowCondition
from aerosynthx.xfoil.runner import run_xfoil

XFOIL_AVAILABLE = shutil.which("xfoil") is not None


@pytest.mark.skipif(not XFOIL_AVAILABLE, reason="xfoil binary not in PATH")
def test_xfoil_integration_naca0012():
    """
    Test the full XFOIL execution path with a NACA 0012 airfoil.
    This is a real integration test that calls the xfoil binary.
    """
    airfoil = naca4("0012")
    # At AoA=4 deg, for a NACA 0012 at Re=1e6, Cl should be around 0.45
    flow = FlowCondition(velocity_m_s=50, angle_of_attack_deg=4.0, reynolds_target=1e6)

    result = run_xfoil(airfoil, flow)

    assert result.alpha_deg == pytest.approx(4.0)
    assert result.cl == pytest.approx(0.45, abs=0.05)
    assert result.cd > 0
    # For a symmetric airfoil at non-zero alpha, Cm should be close to 0
    assert result.cm == pytest.approx(0.0, abs=0.01)
