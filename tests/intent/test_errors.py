"""Tests for the intent error hierarchy."""

from __future__ import annotations

from aerosynthx.intent.errors import (
    EnvelopeError,
    IntentError,
    LLMParseError,
    SchemaValidationError,
)
from aerosynthx.physics.errors import AeroSynthXError


def test_hierarchy() -> None:
    assert issubclass(IntentError, AeroSynthXError)
    assert issubclass(SchemaValidationError, IntentError)
    assert issubclass(EnvelopeError, IntentError)
    assert issubclass(LLMParseError, IntentError)


def test_default_codes() -> None:
    assert IntentError("x").code == "intent.error"
    assert EnvelopeError("x").code == "intent.envelope.violation"
    assert LLMParseError("x").code == "intent.llm.parse_failed"


def test_schema_validation_error_carries_details() -> None:
    exc = SchemaValidationError("nope", details="field x required")
    assert exc.code == "intent.schema.invalid"
    assert exc.details == "field x required"
    assert "[intent.schema.invalid]" in str(exc)


def test_code_override_preserved() -> None:
    exc = LLMParseError("boom", code="intent.llm.empty_input")
    assert exc.code == "intent.llm.empty_input"
