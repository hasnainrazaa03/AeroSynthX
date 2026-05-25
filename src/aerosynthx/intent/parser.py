"""LLM-backed intent parser with schema-validating retries."""

from __future__ import annotations

from pydantic import ValidationError

from aerosynthx.intent.errors import LLMParseError, SchemaValidationError
from aerosynthx.intent.llm import LLMClient
from aerosynthx.intent.schemas import (
    DesignIntent,
    ParseResult,
    design_intent_json_schema,
)

_SYSTEM_PROMPT = """You convert natural-language airfoil-design requests into a strict JSON object.

You MUST return JSON that validates against the provided schema. Do not invent
units; assume SI for unit-bearing fields. Set provenance tags for every
field you populate:

- "user_provided" when the user stated the value explicitly.
- "inferred" when you chose a default; in that case append an entry to
  the "assumptions" array explaining why.

The operating envelope is strictly enforced downstream: NACA 4-digit airfoils
only, Mach < 0.3, angle of attack within +/-20 degrees, altitude 0-20000 m.
If the request lies outside this envelope, still produce schema-valid JSON
that mirrors the request and let downstream validation reject it; never
silently clamp values."""


class IntentParser:
    """Drive an :class:`LLMClient` to produce a validated :class:`ParseResult`.

    The parser sends a strict system prompt + the user input + the
    :class:`DesignIntent` JSON Schema to the client, then validates the
    response. On validation failure, it re-prompts the client with the
    Pydantic error report appended, up to ``max_retries`` additional
    attempts.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        max_retries: int = 2,
        model_name: str = "unknown",
    ) -> None:
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        self._client = client
        self._max_retries = max_retries
        self._model_name = model_name

    def parse(self, text: str) -> ParseResult:
        """Parse ``text`` into a :class:`ParseResult`.

        Raises:
            SchemaValidationError: When the LLM's final attempt still
                fails Pydantic validation.
            LLMParseError: When the LLM returns a non-dict (caught here
                so callers see a single typed failure).
        """
        if not isinstance(text, str) or not text.strip():
            raise LLMParseError(
                "intent input must be a non-empty string",
                code="intent.llm.empty_input",
            )

        schema = design_intent_json_schema()
        user_prompt = text
        last_error: str | None = None

        for attempt in range(1, self._max_retries + 2):
            prompt = user_prompt
            if last_error is not None:
                prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous response failed schema validation with these errors:\n"
                    f"{last_error}\n"
                    "Return a corrected JSON object."
                )
            try:
                raw = self._client.complete_json(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    schema=schema,
                )
            except Exception as exc:
                raise LLMParseError(
                    f"LLM client raised {type(exc).__name__}: {exc}",
                    code="intent.llm.client_failure",
                ) from exc

            if not isinstance(raw, dict):
                raise LLMParseError(
                    f"LLM client returned {type(raw).__name__}, expected dict",
                    code="intent.llm.bad_payload",
                )

            try:
                intent = DesignIntent.model_validate(raw)
            except ValidationError as exc:
                last_error = str(exc)
                if attempt == self._max_retries + 1:
                    raise SchemaValidationError(
                        f"LLM output failed schema validation after {attempt} attempt(s)",
                        details=last_error,
                    ) from exc
                continue

            return ParseResult(
                intent=intent,
                raw_input=text,
                model=self._model_name,
                attempts=attempt,
            )

        # Unreachable: the loop either returns or raises.
        raise LLMParseError(  # pragma: no cover
            "exhausted retry loop without resolution",
            code="intent.llm.unreachable",
        )
