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


def parse_polar_file(content: str) -> list[XfoilResult]:
    """
    Parses an XFOIL polar file and extracts the aerodynamic coefficients for all data rows.

    Args:
        content: The raw text content of the XFOIL polar file.

    Returns:
        A list of XfoilResult dataclasses.
    """
    lines = content.strip().splitlines()
    data_started = False
    results = []

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
                    results.append(XfoilResult(alpha_deg=alpha, cl=cl, cd=cd, cm=cm))
                except (ValueError, IndexError):
                    # Skip lines that can't be parsed
                    continue

    return results
