"""XFOIL integration package for fast aerodynamic analysis."""

from aerosynthx.xfoil.errors import (
    XfoilConvergenceError,
    XfoilError,
    XfoilNotFoundError,
    XfoilParseError,
)
from aerosynthx.xfoil.parser import XfoilResult
from aerosynthx.xfoil.runner import run_xfoil

__all__ = [
    "run_xfoil",
    "XfoilResult",
    "XfoilError",
    "XfoilNotFoundError",
    "XfoilConvergenceError",
    "XfoilParseError",
]
