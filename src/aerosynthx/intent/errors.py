"""Errors raised by ``aerosynthx.intent``."""

from __future__ import annotations

from aerosynthx.physics.errors import AeroSynthXError


class IntentError(AeroSynthXError):
    """Base class for errors raised by the intent package."""

    code = "intent.error"


class SchemaValidationError(IntentError):
    """Raised when LLM (or offline) output fails Pydantic validation.

    Carries the Pydantic error report as ``details`` for diagnostics
    and (in the parser's retry loop) for feeding back into the LLM.
    """

    code = "intent.schema.invalid"

    def __init__(self, message: str, *, details: str, code: str | None = None) -> None:
        super().__init__(message, code=code)
        self.details = details


class EnvelopeError(IntentError):
    """Raised when a request lies outside the operating envelope."""

    code = "intent.envelope.violation"


class LLMParseError(IntentError):
    """Raised when an LLM client returns something we cannot use.

    Examples: non-JSON output, malformed structure, or repeated
    schema-validation failures after exhausting retries.
    """

    code = "intent.llm.parse_failed"
