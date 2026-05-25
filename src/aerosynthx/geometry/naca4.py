"""NACA 4-digit airfoil generator.

References:
- Abbott & von Doenhoff, *Theory of Wing Sections*, sections 6.4--6.6.
- Jacobs, Ward, Pinkerton, NACA Report 460, 1933.

The 4-digit designation is ``MPXX``:

- ``M`` -- maximum camber as percent of chord (0--9).
- ``P`` -- chordwise location of maximum camber in tenths (0--9).
- ``XX`` -- maximum thickness as percent of chord (00--99).

Coordinates are produced with cosine spacing for higher resolution near
the leading and trailing edges, and ordered Selig-style:

    TE -> upper -> LE -> lower -> TE
"""

from __future__ import annotations

import math
import re
from types import MappingProxyType

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.errors import GeometryError

_DESIGNATION_RE = re.compile(r"^(?:NACA[-_ ]?)?(\d{4})$", re.IGNORECASE)

# Thickness distribution coefficients (NACA 4-digit).
_A0 = 0.2969
_A1 = -0.1260
_A2 = -0.3516
_A3 = 0.2843
# Open trailing edge:
_A4_OPEN = -0.1015
# Closed trailing edge (modified last coefficient):
_A4_CLOSED = -0.1036


def _parse_designation(designation: str) -> tuple[int, int, int, str]:
    match = _DESIGNATION_RE.match(designation.strip())
    if not match:
        raise GeometryError(
            f"invalid NACA 4-digit designation {designation!r}; expected e.g. 'NACA2412'",
            code="geometry.naca4.bad_designation",
        )
    digits = match.group(1)
    m = int(digits[0])  # max camber (%)
    p = int(digits[1])  # camber position (tenths)
    t = int(digits[2:4])  # max thickness (%)
    if m > 0 and p == 0:
        raise GeometryError(
            "non-zero camber requires a non-zero camber position (NACA M>0 with P=0 is invalid)",
            code="geometry.naca4.bad_designation",
        )
    if t == 0:
        raise GeometryError(
            "zero thickness is not a valid airfoil",
            code="geometry.naca4.bad_designation",
        )
    return m, p, t, f"NACA{digits}"


def _thickness(x: float, t: float, *, closed: bool) -> float:
    """Half-thickness ``y_t(x)`` for a unit-chord NACA 4-digit section."""
    a4 = _A4_CLOSED if closed else _A4_OPEN
    return 5.0 * t * (_A0 * math.sqrt(x) + _A1 * x + _A2 * x * x + _A3 * x**3 + a4 * x**4)


def _camber(x: float, m: float, p: float) -> tuple[float, float]:
    """Mean camber line ``y_c(x)`` and slope ``dy_c/dx``."""
    if m == 0.0:
        return 0.0, 0.0
    if x <= p:
        y_c = (m / (p * p)) * (2.0 * p * x - x * x)
        dy = (2.0 * m / (p * p)) * (p - x)
    else:
        one_minus_p2 = (1.0 - p) ** 2
        y_c = (m / one_minus_p2) * ((1.0 - 2.0 * p) + 2.0 * p * x - x * x)
        dy = (2.0 * m / one_minus_p2) * (p - x)
    return y_c, dy


def naca4(
    designation: str,
    *,
    n_per_side: int = 100,
    chord_m: float = 1.0,
    closed_trailing_edge: bool = True,
) -> Airfoil:
    """Generate a NACA 4-digit airfoil.

    Args:
        designation: 4-digit code, optionally prefixed by ``NACA``
            (e.g. ``"2412"``, ``"NACA0012"``).
        n_per_side: Number of cosine-spaced points per surface
            (upper or lower). Must be ``>= 10``. The output contains
            ``2 * n_per_side - 1`` points (the leading edge is shared).
        chord_m: Chord length in meters. Carried as metadata only;
            coordinates remain normalized to a unit chord.
        closed_trailing_edge: If ``True`` (default), use the closed-TE
            thickness coefficient so the surfaces meet at ``x=1``.

    Returns:
        An :class:`Airfoil` with Selig-ordered coordinates.

    Raises:
        GeometryError: For invalid designations or parameters.
    """
    if n_per_side < 10:
        raise GeometryError(
            f"n_per_side must be >= 10, got {n_per_side}",
            code="geometry.naca4.bad_resolution",
        )
    if not math.isfinite(chord_m) or chord_m <= 0.0:
        raise GeometryError(
            f"chord_m must be positive and finite, got {chord_m!r}",
            code="geometry.naca4.bad_chord",
        )

    m_int, p_int, t_int, name = _parse_designation(designation)
    m = m_int / 100.0
    p = p_int / 10.0
    t = t_int / 100.0

    # Cosine-spaced x in [0, 1], dense near LE and TE.
    betas = [math.pi * i / (n_per_side - 1) for i in range(n_per_side)]
    xs = [0.5 * (1.0 - math.cos(b)) for b in betas]

    upper_x: list[float] = []
    upper_y: list[float] = []
    lower_x: list[float] = []
    lower_y: list[float] = []

    for x in xs:
        yt = _thickness(x, t, closed=closed_trailing_edge)
        yc, dyc = _camber(x, m, p)
        theta = math.atan(dyc)
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)
        upper_x.append(x - yt * sin_t)
        upper_y.append(yc + yt * cos_t)
        lower_x.append(x + yt * sin_t)
        lower_y.append(yc - yt * cos_t)

    # Selig ordering: TE -> upper -> LE -> lower -> TE.
    # ``upper`` runs LE->TE; reverse it. Then append ``lower`` from LE+1 to TE
    # to avoid duplicating the leading edge point.
    x_out = list(reversed(upper_x)) + lower_x[1:]
    y_out = list(reversed(upper_y)) + lower_y[1:]

    metadata = MappingProxyType(
        {
            "family": "naca4",
            "designation": name,
            "M_pct": str(m_int),
            "P_tenths": str(p_int),
            "T_pct": str(t_int),
            "n_per_side": str(n_per_side),
            "closed_trailing_edge": str(closed_trailing_edge),
            "chord_m": repr(chord_m),
        }
    )

    return Airfoil(
        name=name,
        chord_m=float(chord_m),
        x=tuple(x_out),
        y=tuple(y_out),
        closed_trailing_edge=closed_trailing_edge,
        metadata=metadata,
    )
