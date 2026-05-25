"""Validators for :class:`Airfoil` coordinate arrays."""

from __future__ import annotations

import math

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.errors import GeometryError


def validate_airfoil(
    af: Airfoil,
    *,
    closure_tol: float = 1e-6,
    monotonic_tol: float = 1e-3,
    le_wrap_tol: float = 0.05,
    min_thickness_frac: float = 1e-4,
) -> None:
    """Validate a Selig-ordered airfoil for downstream meshing.

    Checks:

    1. ``x`` and ``y`` have equal length and contain finite values.
    2. ``x`` lies in ``[-le_wrap_tol, 1 + closure_tol]`` (the lower
       bound accommodates the leading-edge wraparound that cambered
       NACA profiles exhibit, where the upper surface dips slightly
       past ``x = 0``).
    3. The trailing edge endpoints coincide within ``closure_tol``
       (skipped if ``closed_trailing_edge`` is ``False``).
    4. ``x`` is monotonically non-increasing on the upper surface
       (TE to LE) and monotonically non-decreasing on the lower
       surface (LE to TE), with violations smaller than
       ``monotonic_tol`` tolerated (these arise from numerical noise
       and the LE wraparound).
    5. The maximum thickness exceeds ``min_thickness_frac`` of the
       chord.

    Args:
        af: Airfoil to validate.
        closure_tol: Maximum allowed TE gap (in normalized units).
        monotonic_tol: Tolerance for upper/lower surface monotonicity
            (in normalized units).
        le_wrap_tol: How far the upper surface may dip below ``x = 0``
            near the leading edge (in normalized units).
        min_thickness_frac: Required minimum peak thickness as a
            fraction of the unit chord.

    Raises:
        GeometryError: If any check fails. The ``code`` attribute names
            the failing check.
    """
    n = len(af.x)
    if n != len(af.y):
        raise GeometryError(
            f"x/y length mismatch: {n} vs {len(af.y)}",
            code="geometry.validate.length_mismatch",
        )
    if n < 5:
        raise GeometryError(
            f"airfoil must have at least 5 points, got {n}",
            code="geometry.validate.too_few_points",
        )
    for i, (xi, yi) in enumerate(zip(af.x, af.y, strict=True)):
        if not (math.isfinite(xi) and math.isfinite(yi)):
            raise GeometryError(
                f"non-finite coordinate at index {i}: ({xi!r}, {yi!r})",
                code="geometry.validate.non_finite",
            )
        if xi < -le_wrap_tol or xi > 1.0 + closure_tol:
            raise GeometryError(
                f"x[{i}]={xi!r} outside [{-le_wrap_tol}, {1.0 + closure_tol}]",
                code="geometry.validate.x_out_of_range",
            )

    # Locate leading edge (minimum x).
    le_idx = min(range(n), key=lambda i: af.x[i])
    if le_idx == 0 or le_idx == n - 1:
        raise GeometryError(
            f"leading edge must be an interior point, found at index {le_idx}",
            code="geometry.validate.bad_ordering",
        )

    # Upper surface: indices 0..le_idx, x non-increasing.
    for i in range(le_idx):
        if af.x[i + 1] > af.x[i] + monotonic_tol:
            raise GeometryError(
                f"upper surface not monotonic at index {i}: "
                f"x[{i}]={af.x[i]!r} -> x[{i + 1}]={af.x[i + 1]!r}",
                code="geometry.validate.non_monotonic_upper",
            )
    # Lower surface: indices le_idx..n-1, x non-decreasing.
    for i in range(le_idx, n - 1):
        if af.x[i + 1] < af.x[i] - monotonic_tol:
            raise GeometryError(
                f"lower surface not monotonic at index {i}: "
                f"x[{i}]={af.x[i]!r} -> x[{i + 1}]={af.x[i + 1]!r}",
                code="geometry.validate.non_monotonic_lower",
            )

    # Trailing edge closure (only when claimed closed).
    if af.closed_trailing_edge:
        dx = af.x[0] - af.x[-1]
        dy = af.y[0] - af.y[-1]
        gap = math.hypot(dx, dy)
        if gap > closure_tol:
            raise GeometryError(
                f"trailing edge gap {gap!r} exceeds tolerance {closure_tol!r}",
                code="geometry.validate.te_not_closed",
            )

    # Peak thickness check: compare upper vs lower at matching x bins.
    # Use the upper surface (indices 0..le_idx, x descending) and lower
    # surface (le_idx..n-1, x ascending). Resample lower at upper xs by
    # linear interpolation.
    lower_xs = af.x[le_idx:]
    lower_ys = af.y[le_idx:]
    max_thickness = 0.0
    for i in range(le_idx + 1):
        xu = af.x[i]
        yu = af.y[i]
        # Find bracketing lower segment.
        # ``lower_xs`` is ascending in [0, 1].
        if xu <= lower_xs[0]:
            yl = lower_ys[0]
        elif xu >= lower_xs[-1]:
            yl = lower_ys[-1]
        else:
            # Linear search is fine for typical n ~ 200; geometry is one-shot.
            j = 0
            while j + 1 < len(lower_xs) and lower_xs[j + 1] < xu:
                j += 1
            x0, x1 = lower_xs[j], lower_xs[j + 1]
            y0, y1 = lower_ys[j], lower_ys[j + 1]
            frac = (xu - x0) / (x1 - x0) if x1 != x0 else 0.0
            yl = y0 + frac * (y1 - y0)
        thickness = yu - yl
        if thickness > max_thickness:
            max_thickness = thickness

    if max_thickness < min_thickness_frac:
        raise GeometryError(
            f"peak thickness {max_thickness!r} below minimum fraction {min_thickness_frac!r}",
            code="geometry.validate.too_thin",
        )
