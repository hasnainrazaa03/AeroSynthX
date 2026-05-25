"""Deterministic airfoil geometry generation, validation, export, and rendering.

Public API (see ``docs/phases/PHASE_2.md``):

- :class:`Airfoil` -- immutable result of a geometry generation.
- :func:`naca4` -- NACA 4-digit generator with cosine spacing.
- :func:`validate_airfoil` -- coordinate validator.
- :func:`to_selig_dat` / :func:`to_csv` -- string exporters.
- :func:`render_airfoil_png` / :func:`render_airfoil_svg` -- writers
  using Matplotlib's Agg backend (no display required).
- :class:`GeometryError` -- typed errors raised by this package.

All numeric inputs are SI; ``chord_m`` is informational and does not
affect the normalized airfoil coordinates (which are dimensionless,
0--1 in ``x``).
"""

from __future__ import annotations

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.errors import GeometryError
from aerosynthx.geometry.exporters import to_csv, to_selig_dat
from aerosynthx.geometry.naca4 import naca4
from aerosynthx.geometry.validators import validate_airfoil
from aerosynthx.geometry.visualize import render_airfoil_png, render_airfoil_svg

__all__ = [
    "Airfoil",
    "GeometryError",
    "naca4",
    "render_airfoil_png",
    "render_airfoil_svg",
    "to_csv",
    "to_selig_dat",
    "validate_airfoil",
]
