"""NACA 5-digit series airfoil generator."""

import math

import numpy as np

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.curves import cosine_spacing
from aerosynthx.geometry.errors import GeometryError
from aerosynthx.physics.units import to_si

# Constants from NACA Report 824 for 5-digit series camber lines
M_LUT = {
    "210": 0.0580,
    "220": 0.1260,
    "230": 0.2025,
    "240": 0.2900,
    "250": 0.3910,
}
K1_LUT = {
    "210": 361.4,
    "220": 51.64,
    "230": 15.957,
    "240": 6.643,
    "250": 3.230,
}


def naca5(
    designation: str,
    *,
    n_points: int = 200,
    chord_m: float = 1.0,
    closed_trailing_edge: bool = True,
) -> Airfoil:
    """Generate coordinates for a NACA 5-digit series airfoil.

    The logic implements the standard NACA 5-digit formulation as described
    in classic texts like Abbott & Von Doenhoff, "Theory of Wing Sections".

    Args:
        designation: The 5-digit NACA designation (e.g., "23012").
        n_points: The total number of points to generate for the airfoil.
        chord_m: The chord length in meters.
        closed_trailing_edge: If True, ensures the trailing edge has zero thickness.

    Returns:
        An Airfoil object with the generated coordinates.

    Raises:
        GeometryError: If the designation is not a valid 5-digit string.
    """
    if not designation.isdigit() or len(designation) != 5:
        raise GeometryError(
            f"'{designation}' is not a valid 5-digit NACA designation.",
            code="geometry.naca5.invalid_designation",
        )

    # Parse the designation
    # Example: 23012
    # L = 2  (first digit * 0.15 = design lift coefficient)
    # P = 3  (second digit * 5 = location of max camber in %)
    # S = 0  (third digit, 0 for simple camber, 1 for reflex)
    # T = 12 (last two digits / 100 = max thickness as % of chord)
    l_digit = int(designation[0])
    p_digit = int(designation[1])
    s_digit = int(designation[2])
    t_digits = int(designation[3:])

    if s_digit != 0:
        raise GeometryError(
            "Reflex camber (3rd digit != 0) is not yet supported.",
            code="geometry.naca5.unsupported_reflex",
        )

    c_l_i = l_digit * 0.15
    p = p_digit * 0.05
    t = t_digits / 100.0

    if p == 0:
        raise GeometryError(
            "P-digit cannot be zero for NACA 5-digit series.",
            code="geometry.naca5.invalid_p_digit",
        )

    profile_key = designation[:3]
    if profile_key not in M_LUT:
        raise GeometryError(
            f"Unsupported camber profile '{profile_key}'. Supported profiles are: {list(M_LUT.keys())}",
            code="geometry.naca5.unsupported_profile",
        )
    m = M_LUT[profile_key]
    k1 = K1_LUT[profile_key]

    # Generate x-coordinates with cosine spacing
    x = cosine_spacing(n_points)
    x_upper = x[x <= p]
    x_lower = x[x > p]

    # Camber line (yc) and gradient (dyc_dx)
    yc = np.zeros_like(x)
    dyc_dx = np.zeros_like(x)

    # Forward section (x <= p)
    yc[x <= p] = (k1 / 6.0) * (
        x_upper**3 - 3 * m * x_upper**2 + m**2 * (3 - m) * x_upper
    )
    dyc_dx[x <= p] = (k1 / 6.0) * (3 * x_upper**2 - 6 * m * x_upper + m**2 * (3 - m))

    # Aft section (x > p)
    yc[x > p] = (k1 * m**3 / 6.0) * (1 - x_lower)
    dyc_dx[x > p] = -(k1 * m**3 / 6.0)

    # Thickness distribution (yt) - same as 4-digit series
    a0 = 0.2969
    a1 = -0.1260
    a2 = -0.3516
    a3 = 0.2843
    a4 = -0.1015 if closed_trailing_edge else -0.1036
    yt = (t / 0.2) * (
        a0 * np.sqrt(x) + a1 * x + a2 * x**2 + a3 * x**3 + a4 * x**4
    )

    # Final coordinates
    theta = np.arctan(dyc_dx)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    # Combine and order points (Selig format: TE -> Upper -> LE -> Lower -> TE)
    x_coords = np.concatenate((np.flip(xu), xl[1:]))
    y_coords = np.concatenate((np.flip(yu), yl[1:]))

    return Airfoil(
        name=f"NACA {designation}",
        chord_m=float(chord_m),
        x=tuple(x_coords * chord_m),
        y=tuple(y_coords * chord_m),
        closed_trailing_edge=closed_trailing_edge,
        metadata={
            "generator": "naca5",
            "designation": designation,
            "n_points": str(n_points),
            "closed_trailing_edge": str(closed_trailing_edge),
            "c_l_i": str(c_l_i),
            "p": str(p),
            "t": str(t),
        },
    )
