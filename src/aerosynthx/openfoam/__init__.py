"""OpenFOAM case generation for AeroSynthX (see ``docs/phases/PHASE_4.md``).

Public API:

- :class:`FlowState` / :func:`derive_flow_state` -- map a validated
  :class:`~aerosynthx.intent.schemas.DesignIntent` to concrete SI flow
  quantities.
- :class:`CaseManifest` / :func:`build_case` -- render the bundled
  Jinja2 templates into a complete case directory.
- :func:`validate_case_structure` -- static structural checks on a
  generated case (no OpenFOAM execution).
- :class:`OpenFoamError` and subclasses -- typed errors.
"""

from __future__ import annotations

from aerosynthx.openfoam.case import (
    TEMPLATE_NAME_2D,
    TEMPLATE_VERSION,
    CaseManifest,
    build_case,
    expected_case_files,
)
from aerosynthx.openfoam.errors import (
    CaseExistsError,
    EnvelopeViolationError,
    OpenFoamError,
    TemplateRenderError,
)
from aerosynthx.openfoam.flow_state import FlowState, derive_flow_state
from aerosynthx.openfoam.runner import (
    CommandResult,
    CommandRunner,
    OpenFoamNotAvailableError,
    SolveResult,
    SolverExecutionError,
    default_command_runner,
    openfoam_available,
    parse_force_coefficients,
    parse_residuals,
    run_case,
)
from aerosynthx.openfoam.validators import validate_case_structure

__all__ = [
    "TEMPLATE_NAME_2D",
    "TEMPLATE_VERSION",
    "CaseExistsError",
    "CaseManifest",
    "CommandResult",
    "CommandRunner",
    "EnvelopeViolationError",
    "FlowState",
    "OpenFoamError",
    "OpenFoamNotAvailableError",
    "SolveResult",
    "SolverExecutionError",
    "TemplateRenderError",
    "build_case",
    "default_command_runner",
    "derive_flow_state",
    "expected_case_files",
    "openfoam_available",
    "parse_force_coefficients",
    "parse_residuals",
    "run_case",
    "validate_case_structure",
]
