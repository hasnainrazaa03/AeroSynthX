"""Errors raised by ``aerosynthx.geometry``."""

from __future__ import annotations

from aerosynthx.physics.errors import AeroSynthXError


class GeometryError(AeroSynthXError):
    """Base class for errors raised by the geometry package."""

    code = "geometry.error"
