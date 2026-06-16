"""Deterministic airfoil geometry generation, validation, export, and rendering."""

from __future__ import annotations

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.custom import custom_airfoil
from aerosynthx.geometry.errors import GeometryError
from aerosynthx.geometry.exporters import to_csv, to_selig_dat
from aerosynthx.geometry.naca4 import naca4
from aerosynthx.geometry.naca5 import naca5
from aerosynthx.geometry.validators import validate_airfoil
from aerosynthx.geometry.visualize import render_airfoil_png, render_airfoil_svg
from aerosynthx.geometry.wing import Wing, generate_wing

__all__ = [
    "Airfoil",
    "custom_airfoil",
    "GeometryError",
    "naca4",
    "naca5",
    "render_airfoil_png",
    "render_airfoil_svg",
    "to_csv",
    "to_selig_dat",
    "validate_airfoil",
    "Wing",
    "generate_wing",
]
