"""XFOIL execution wrapper."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.exporters import to_selig_dat
from aerosynthx.intent.schemas import FlowCondition
from aerosynthx.xfoil.errors import (
    XfoilConvergenceError,
    XfoilNotFoundError,
)
from aerosynthx.xfoil.parser import XfoilResult, parse_polar_file


def run_xfoil(airfoil: Airfoil, flow: FlowCondition) -> XfoilResult:
    """
    Runs XFOIL for a given airfoil and flow condition.

    Args:
        airfoil: The airfoil to analyze.
        flow: The flow conditions.

    Returns:
        An XfoilResult with the calculated coefficients.

    Raises:
        XfoilNotFoundError: If the xfoil executable is not found.
        XfoilConvergenceError: If XFOIL fails to converge.
    """
    xfoil_path = shutil.which("xfoil")
    if not xfoil_path:
        raise XfoilNotFoundError(
            "The 'xfoil' executable was not found on the system PATH. "
            "Please install XFOIL and ensure it is accessible.",
            code="xfoil.not_found",
        )

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        airfoil_file = temp_dir / "airfoil.dat"
        polar_file = temp_dir / "polar.dat"

        # Write airfoil coordinates to a temporary file
        airfoil_file.write_text(to_selig_dat(airfoil))

        # Generate XFOIL command script
        # Note: Reynolds number is required for viscous analysis in XFOIL.
        # The workflow should ensure Re is calculated before this step.
        reynolds = flow.reynolds_target or 1e6 # Default to 1M if not provided

        script = f"""
LOAD {airfoil_file}
OPER
VISC {reynolds}
PACC
{polar_file}

ALFA {flow.angle_of_attack_deg}
PACC
QUIT
"""

        # Run XFOIL
        process = subprocess.run(
            [xfoil_path],
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )

        # Check for convergence errors in stdout
        stdout = process.stdout.decode("utf-8")
        if "convergence failed" in stdout.lower():
            raise XfoilConvergenceError(
                f"XFOIL failed to converge for AoA = {flow.angle_of_attack_deg}",
                code="xfoil.convergence_failed",
            )

        if not polar_file.exists():
            raise XfoilConvergenceError(
                "XFOIL did not produce a polar file. It may have crashed or failed to converge.",
                code="xfoil.no_output",
            )

        # Parse the output file
        polar_content = polar_file.read_text()
        return parse_polar_file(polar_content, target_alpha=flow.angle_of_attack_deg)
