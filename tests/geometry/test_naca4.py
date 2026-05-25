"""Tests for the NACA 4-digit generator.

The thickness/camber formulae are pinned by Abbott & von Doenhoff,
*Theory of Wing Sections*. Reference checks here:

- NACA 0012 (symmetric, 12% thick) -- exact symmetry about the chord.
- NACA 2412 -- max camber 2% at x/c=0.4, max thickness 12%.
- Trailing edge closure with the closed-TE coefficient.
"""

from __future__ import annotations

import math

import pytest

from aerosynthx.geometry import naca4, validate_airfoil
from aerosynthx.geometry.errors import GeometryError

REL_TOL = 1e-9
ABS_TOL = 1e-10


# ---------------------------------------------------------------- shape


def test_naca0012_is_symmetric() -> None:
    af = naca4("0012", n_per_side=151)
    assert af.name == "NACA0012"
    assert af.n_points == 2 * 151 - 1
    # Selig ordering: index 0 = TE upper, index n-1 = TE lower.
    n = af.n_points
    le_idx = n // 2
    # LE point is at x=0, y=0 for a symmetric profile.
    assert af.x[le_idx] == pytest.approx(0.0, abs=ABS_TOL)
    assert af.y[le_idx] == pytest.approx(0.0, abs=ABS_TOL)
    # y(upper, i) == -y(lower, n-1-i) for symmetric airfoil.
    for i in range(le_idx):
        mirror = n - 1 - i
        assert af.x[i] == pytest.approx(af.x[mirror], abs=ABS_TOL)
        assert af.y[i] == pytest.approx(-af.y[mirror], abs=ABS_TOL)


def test_naca0012_max_thickness_is_12_percent() -> None:
    af = naca4("0012", n_per_side=400)
    half = af.n_points // 2
    upper_y = af.y[:half]
    lower_y = af.y[half:]
    # Symmetric: peak thickness = 2 * max(upper_y).
    peak = max(upper_y) - min(lower_y)
    assert peak == pytest.approx(0.12, abs=2e-3)


def test_closed_te_endpoints_coincide() -> None:
    af = naca4("2412", n_per_side=120, closed_trailing_edge=True)
    assert af.closed_trailing_edge is True
    assert math.isclose(af.x[0], 1.0, abs_tol=ABS_TOL)
    assert math.isclose(af.x[-1], 1.0, abs_tol=ABS_TOL)
    assert math.isclose(af.y[0], af.y[-1], abs_tol=ABS_TOL)


def test_open_te_has_finite_gap() -> None:
    af = naca4("0012", n_per_side=120, closed_trailing_edge=False)
    assert af.closed_trailing_edge is False
    # Symmetric, open TE: y at x=1 ~ 0.00126 per Abbott table.
    gap = af.y[0] - af.y[-1]
    assert gap > 1e-3


# --------------------------------------------------------------- camber


def test_naca2412_max_camber_value_and_location() -> None:
    af = naca4("2412", n_per_side=601)
    # On the camber line at x=p=0.4 we expect y_c = m = 0.02. We pick the
    # mid-thickness y at x ~= 0.4 by averaging upper and lower.
    target_x = 0.4
    half = af.n_points // 2
    upper_x = af.x[: half + 1]  # includes LE
    upper_y = af.y[: half + 1]
    lower_x = af.x[half:]
    lower_y = af.y[half:]

    # Find indices bracketing target on each surface.
    def interp(
        xs: tuple[float, ...] | list[float],
        ys: tuple[float, ...] | list[float],
        xt: float,
        ascending: bool,
    ) -> float:
        seq = list(zip(xs, ys, strict=True))
        if not ascending:
            seq = list(reversed(seq))
        for i in range(len(seq) - 1):
            x0, y0 = seq[i]
            x1, y1 = seq[i + 1]
            if x0 <= xt <= x1:
                frac = (xt - x0) / (x1 - x0)
                return y0 + frac * (y1 - y0)
        raise AssertionError("target x not bracketed")

    yu = interp(list(upper_x), list(upper_y), target_x, ascending=False)
    yl = interp(list(lower_x), list(lower_y), target_x, ascending=True)
    camber_at_p = 0.5 * (yu + yl)
    assert camber_at_p == pytest.approx(0.02, abs=1e-4)


def test_naca2412_passes_validator() -> None:
    af = naca4("2412", n_per_side=200)
    validate_airfoil(af)  # must not raise


def test_naca4412_passes_validator() -> None:
    af = naca4("4412", n_per_side=200)
    validate_airfoil(af)


# ---------------------------------------------------------- designation


@pytest.mark.parametrize(
    "designation,expected_name",
    [
        ("2412", "NACA2412"),
        ("naca2412", "NACA2412"),
        ("NACA-0012", "NACA0012"),
        ("naca_4412", "NACA4412"),
        ("  0024  ", "NACA0024"),
    ],
)
def test_designation_parsing_accepts_known_forms(designation: str, expected_name: str) -> None:
    af = naca4(designation, n_per_side=40)
    assert af.name == expected_name


@pytest.mark.parametrize(
    "bad",
    ["", "NACA", "12345", "abcd", "NACA12A4", "12 34", "NACA-23012"],
)
def test_designation_parsing_rejects_bad_input(bad: str) -> None:
    with pytest.raises(GeometryError) as ei:
        naca4(bad, n_per_side=40)
    assert ei.value.code == "geometry.naca4.bad_designation"


def test_camber_with_zero_position_is_rejected() -> None:
    # NACA 2012: M=2, P=0 -> invalid (camber without a location).
    with pytest.raises(GeometryError) as ei:
        naca4("2012", n_per_side=40)
    assert ei.value.code == "geometry.naca4.bad_designation"


def test_zero_thickness_is_rejected() -> None:
    with pytest.raises(GeometryError) as ei:
        naca4("0000", n_per_side=40)
    assert ei.value.code == "geometry.naca4.bad_designation"


# ----------------------------------------------------------- parameters


def test_too_few_points_rejected() -> None:
    with pytest.raises(GeometryError) as ei:
        naca4("0012", n_per_side=5)
    assert ei.value.code == "geometry.naca4.bad_resolution"


@pytest.mark.parametrize("bad_chord", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_chord_rejected(bad_chord: float) -> None:
    with pytest.raises(GeometryError) as ei:
        naca4("0012", n_per_side=40, chord_m=bad_chord)
    assert ei.value.code == "geometry.naca4.bad_chord"


def test_metadata_captures_inputs() -> None:
    af = naca4("2412", n_per_side=60, chord_m=0.5, closed_trailing_edge=False)
    md = af.metadata
    assert md["family"] == "naca4"
    assert md["designation"] == "NACA2412"
    assert md["M_pct"] == "2"
    assert md["P_tenths"] == "4"
    assert md["T_pct"] == "12"
    assert md["n_per_side"] == "60"
    assert md["closed_trailing_edge"] == "False"
    # MappingProxyType is read-only.
    with pytest.raises(TypeError):
        md["family"] = "x"  # type: ignore[index]


def test_airfoil_is_immutable() -> None:
    af = naca4("0012", n_per_side=40)
    with pytest.raises(AttributeError):
        af.name = "X"  # type: ignore[misc]


def test_airfoil_freezes_plain_dict_metadata() -> None:
    from aerosynthx.geometry import Airfoil

    af = Airfoil(
        name="X",
        chord_m=1.0,
        x=(1.0, 0.0, 1.0),
        y=(0.0, 0.0, 0.0),
        closed_trailing_edge=False,
        metadata={"k": "v"},  # plain dict -> must be frozen to MappingProxyType
    )
    with pytest.raises(TypeError):
        af.metadata["k"] = "z"  # type: ignore[index]


def test_chord_m_is_metadata_only_not_scaling() -> None:
    af_unit = naca4("0012", n_per_side=80, chord_m=1.0)
    af_half = naca4("0012", n_per_side=80, chord_m=0.5)
    # Coordinates are normalized; only chord_m differs.
    assert af_unit.x == af_half.x
    assert af_unit.y == af_half.y
    assert af_unit.chord_m == 1.0
    assert af_half.chord_m == 0.5
