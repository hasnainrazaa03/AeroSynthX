"""Exceptions for the XFOIL integration layer."""

from aerosynthx.physics.errors import AeroSynthXError


class XfoilError(AeroSynthXError):
    """Base class for all XFOIL execution errors."""
    pass


class XfoilNotFoundError(XfoilError):
    """Raised when the xfoil executable is not found on the system PATH."""
    pass


class XfoilConvergenceError(XfoilError):
    """Raised when XFOIL fails to converge for a given flow condition."""
    pass


class XfoilParseError(XfoilError):
    """Raised when XFOIL output cannot be parsed."""
    pass
