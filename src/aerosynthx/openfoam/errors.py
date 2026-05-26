"""Errors raised by ``aerosynthx.openfoam``."""

from __future__ import annotations

from aerosynthx.physics.errors import AeroSynthXError


class OpenFoamError(AeroSynthXError):
    """Base class for errors raised by the OpenFOAM layer."""

    code = "openfoam.error"


class EnvelopeViolationError(OpenFoamError):
    """Raised when an intent falls outside the supported envelope."""

    code = "openfoam.envelope.violation"


class CaseExistsError(OpenFoamError):
    """Raised when the target case directory exists and ``overwrite`` is false."""

    code = "openfoam.case.exists"


class TemplateRenderError(OpenFoamError):
    """Raised when a bundled template is missing or fails to render."""

    code = "openfoam.template.error"
