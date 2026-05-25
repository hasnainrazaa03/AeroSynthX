"""Tests for the Selig ``.dat`` and CSV exporters."""

from __future__ import annotations

from aerosynthx.geometry import naca4, to_csv, to_selig_dat


def _parse_selig(text: str) -> tuple[str, list[tuple[float, float]]]:
    lines = text.strip().splitlines()
    name = lines[0]
    pts: list[tuple[float, float]] = []
    for line in lines[1:]:
        parts = line.split()
        assert len(parts) == 2, f"unexpected line: {line!r}"
        pts.append((float(parts[0]), float(parts[1])))
    return name, pts


def _parse_csv(text: str) -> list[tuple[float, float]]:
    rows = text.strip().splitlines()
    assert rows[0] == "x,y"
    out: list[tuple[float, float]] = []
    for row in rows[1:]:
        xs, ys = row.split(",")
        out.append((float(xs), float(ys)))
    return out


def test_selig_dat_round_trip() -> None:
    af = naca4("2412", n_per_side=80)
    text = to_selig_dat(af)
    name, pts = _parse_selig(text)
    assert name == "NACA2412"
    assert len(pts) == af.n_points
    for (xi, yi), x_orig, y_orig in zip(pts, af.x, af.y, strict=True):
        assert abs(xi - x_orig) < 1e-7
        assert abs(yi - y_orig) < 1e-7


def test_csv_round_trip() -> None:
    af = naca4("0012", n_per_side=60)
    text = to_csv(af)
    pts = _parse_csv(text)
    assert len(pts) == af.n_points
    for (xi, yi), x_orig, y_orig in zip(pts, af.x, af.y, strict=True):
        assert abs(xi - x_orig) < 1e-9
        assert abs(yi - y_orig) < 1e-9


def test_selig_dat_starts_with_name_line() -> None:
    af = naca4("4412", n_per_side=40)
    text = to_selig_dat(af)
    assert text.splitlines()[0] == "NACA4412"


def test_csv_has_header() -> None:
    af = naca4("0012", n_per_side=20)
    text = to_csv(af)
    assert text.splitlines()[0] == "x,y"
