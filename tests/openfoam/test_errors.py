"""Tests for ``aerosynthx.openfoam.errors``."""

from __future__ import annotations

import pytest

from aerosynthx.openfoam.errors import (
    CaseExistsError,
    EnvelopeViolationError,
    OpenFoamError,
    TemplateRenderError,
)
from aerosynthx.physics.errors import AeroSynthXError


@pytest.mark.parametrize(
    ("exc_cls", "expected_code"),
    [
        (OpenFoamError, "openfoam.error"),
        (EnvelopeViolationError, "openfoam.envelope.violation"),
        (CaseExistsError, "openfoam.case.exists"),
        (TemplateRenderError, "openfoam.template.error"),
    ],
)
def test_default_codes(exc_cls: type[OpenFoamError], expected_code: str) -> None:
    err = exc_cls("boom")
    assert err.code == expected_code
    assert isinstance(err, AeroSynthXError)
    assert "boom" in str(err)


def test_code_override() -> None:
    err = EnvelopeViolationError("x", code="openfoam.envelope.custom")
    assert err.code == "openfoam.envelope.custom"
