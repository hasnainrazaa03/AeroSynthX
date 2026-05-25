"""Tests for :func:`validate_airfoil`."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from aerosynthx.geometry import Airfoil, naca4, validate_airfoil
from aerosynthx.geometry.errors import GeometryError


def _af_replace(af: Airfoil, **kwargs: object) -> Airfoil:
    return replace(af, **kwargs)  # type: ignore[arg-type]


def test_valid_naca_passes() -> None:
    af = naca4("2412", n_per_side=100)
    validate_airfoil(af)


def test_length_mismatch() -> None:
    af = naca4("0012", n_per_side=40)
    bad = _af_replace(af, x=af.x[:-1])
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.length_mismatch"


def test_too_few_points() -> None:
    af = Airfoil(
        name="X",
        chord_m=1.0,
        x=(1.0, 0.5, 0.0, 0.5),
        y=(0.0, 0.05, 0.0, -0.05),
        closed_trailing_edge=False,
        metadata=MappingProxyType({}),
    )
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(af)
    assert ei.value.code == "geometry.validate.too_few_points"


def test_non_finite_rejected() -> None:
    af = naca4("0012", n_per_side=40)
    bad_y = list(af.y)
    bad_y[3] = float("nan")
    bad = _af_replace(af, y=tuple(bad_y))
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.non_finite"


def test_x_out_of_range_rejected() -> None:
    af = naca4("0012", n_per_side=40)
    bad_x = list(af.x)
    bad_x[2] = 1.5
    bad = _af_replace(af, x=tuple(bad_x))
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.x_out_of_range"


def test_le_must_be_interior() -> None:
    # Construct an airfoil where the minimum x is at index 0.
    af = Airfoil(
        name="X",
        chord_m=1.0,
        x=(0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25),
        y=(0.0, 0.05, 0.05, 0.04, 0.0, -0.04, -0.05, -0.05),
        closed_trailing_edge=False,
        metadata=MappingProxyType({}),
    )
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(af)
    assert ei.value.code == "geometry.validate.bad_ordering"


def test_non_monotonic_upper_rejected() -> None:
    af = naca4("0012", n_per_side=40)
    bad_x = list(af.x)
    # Inject a forward jump on the upper surface (descending) that
    # exceeds the monotonicity tolerance but stays within [0, 1].
    bad_x[3] = min(bad_x[2] + 0.05, 0.999)
    bad = _af_replace(af, x=tuple(bad_x))
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.non_monotonic_upper"


def test_non_monotonic_lower_rejected() -> None:
    af = naca4("0012", n_per_side=40)
    n = af.n_points
    bad_x = list(af.x)
    # Inject a backward jump on the lower surface.
    bad_x[n - 3] = max(bad_x[n - 4] - 0.05, 0.001)
    bad = _af_replace(af, x=tuple(bad_x))
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.non_monotonic_lower"


def test_open_te_skips_closure_check() -> None:
    af = naca4("0012", n_per_side=40, closed_trailing_edge=False)
    # Even though endpoints don't coincide, validation passes for open TE.
    validate_airfoil(af)


def test_te_not_closed_when_claimed_closed() -> None:
    af = naca4("0012", n_per_side=40, closed_trailing_edge=True)
    bad_y = list(af.y)
    bad_y[-1] = af.y[0] - 0.01
    bad = _af_replace(af, y=tuple(bad_y))
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(bad)
    assert ei.value.code == "geometry.validate.te_not_closed"


def test_too_thin_rejected() -> None:
    # Build a degenerate "airfoil" of two nearly-collinear surfaces.
    af = Airfoil(
        name="flat",
        chord_m=1.0,
        x=(1.0, 0.75, 0.5, 0.25, 0.0, 0.25, 0.5, 0.75, 1.0),
        y=(0.0, 1e-7, 1e-7, 1e-7, 0.0, -1e-7, -1e-7, -1e-7, 0.0),
        closed_trailing_edge=True,
        metadata=MappingProxyType({}),
    )
    with pytest.raises(GeometryError) as ei:
        validate_airfoil(af, min_thickness_frac=1e-4)
    assert ei.value.code == "geometry.validate.too_thin"


def test_lower_extrapolation_branches_thickness() -> None:
    # Custom airfoil where some upper xs lie outside the lower surface's
    # x-extent, exercising both extrapolation branches in the thickness
    # computation. Upper extends to x=1.05 (slightly past lower's max),
    # and starts at x=0.99 (slightly past lower's min from above).
    af = Airfoil(
        name="X",
        chord_m=1.0,
        x=(0.99, 0.6, 0.3, 0.0, 0.3, 0.6, 1.05),
        y=(0.001, 0.05, 0.06, 0.0, -0.06, -0.05, -0.001),
        closed_trailing_edge=False,
        metadata=MappingProxyType({}),
    )
    # Allow x slightly outside [0,1] via a looser closure tol.
    validate_airfoil(af, closure_tol=0.1, min_thickness_frac=1e-3)
