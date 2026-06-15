"""Parser for XFOIL output files."""

import re
from dataclasses import dataclass

from aerosynthx.xfoil.errors import XfoilParseError


@dataclass(frozen=True, slots=True)
class XfoilResult:
    """Aerodynamic coefficients calculated by XFOIL."""
    alpha_deg: float
    cl: float
    cd: float
    cm: float


def parse_polar_file(content: str, target_alpha: float | None = None) -> XfoilResult:
    """
    Parses an XFOIL polar file and extracts the aerodynamic coefficients.

    If target_alpha is provided, it attempts to find the exact row matching
    that alpha. Otherwise, it returns the first data row.

    Args:
        content: The raw text content of the XFOIL polar file.
        target_alpha: The angle of attack to look for (optional).

    Returns:
        An XfoilResult dataclass.

    Raises:
        XfoilParseError: If the file is malformed or no data is found.
    """
    lines = content.strip().splitlines()
    data_started = False

    for line in lines:
        if "------" in line:
            data_started = True
            continue

        if data_started:
            # Parse the data row
            # Format: alpha CL CD CDp CM Top_Xtr Bot_Xtr
            parts = line.split()
            if len(parts) >= 5:
                try:
                    alpha = float(parts[0])
                    cl = float(parts[1])
                    cd = float(parts[2])
                    cm = float(parts[4])

                    if target_alpha is not None:
                        # Allow a small tolerance for floating point matching
                        if abs(alpha - target_alpha) < 1e-4:
                            return XfoilResult(alpha_deg=alpha, cl=cl, cd=cd, cm=cm)
                    else:
                        return XfoilResult(alpha_deg=alpha, cl=cl, cd=cd, cm=cm)
                except ValueError:
                    continue # Skip lines that can't be parsed

    if target_alpha is not None:
         raise XfoilParseError(
            f"No data found in XFOIL polar file for alpha = {target_alpha}",
            code="xfoil.parse.no_data_for_alpha",
        )
    raise XfoilParseError(
        "No data rows found in XFOIL polar file.",
        code="xfoil.parse.empty_polar",
    )
