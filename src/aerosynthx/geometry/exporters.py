"""Airfoil exporters: Selig ``.dat`` and CSV."""

from __future__ import annotations

import io

from aerosynthx.geometry.airfoil import Airfoil


def to_selig_dat(af: Airfoil) -> str:
    """Render an airfoil as a Selig-format ``.dat`` string.

    The first line is the airfoil name (per the UIUC/Selig convention);
    subsequent lines contain ``x y`` pairs separated by spaces, with
    fixed precision sufficient for reproducible CFD case generation.
    """
    buf = io.StringIO()
    buf.write(f"{af.name}\n")
    for xi, yi in zip(af.x, af.y, strict=True):
        buf.write(f"{xi:>12.8f}  {yi:>12.8f}\n")
    return buf.getvalue()


def to_csv(af: Airfoil) -> str:
    """Render an airfoil as a 2-column CSV string with header ``x,y``."""
    buf = io.StringIO()
    buf.write("x,y\n")
    for xi, yi in zip(af.x, af.y, strict=True):
        buf.write(f"{xi:.10f},{yi:.10f}\n")
    return buf.getvalue()
