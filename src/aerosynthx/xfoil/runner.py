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


def run_xfoil(airfoil: Airfoil, flow: FlowCondition) -> list[XfoilResult]:
    """
    Runs XFOIL for a given airfoil and flow condition.

    Args:
        airfoil: The airfoil to analyze.
        flow: The flow conditions.

    Returns:
        A list of XfoilResult objects with the calculated coefficients.

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
        reynolds = flow.reynolds_target or 1e6  # Default to 1M if not provided

        # Determine if it's a single point or a sweep
        is_sweep = flow.alpha_start_deg is not None

        script = f"""
LOAD {airfoil_file}
OPER
VISC {reynolds}
PACC
{polar_file}

"""
        if is_sweep:
            script += f"ASEQ {flow.alpha_start_deg} {flow.alpha_end_deg} {flow.alpha_increment_deg}\n"
        else:
            script += f"ALFA {flow.angle_of_attack_deg}\n"

        script += """
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
            # For sweeps, this is not a fatal error, as some points may have converged.
            # We will let the parser handle the partial results.
            # For a single point analysis, it is a fatal error.
            if not is_sweep:
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
        return parse_polar_file(polar_content)
