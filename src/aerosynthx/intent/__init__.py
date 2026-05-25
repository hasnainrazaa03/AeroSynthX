"""Natural-language intent parsing.

See ``docs/phases/PHASE_3.md`` for the full surface description. The
package provides:

- Strict Pydantic schemas (:class:`DesignIntent` and friends).
- A provider-agnostic :class:`LLMClient` protocol and a deterministic
  :class:`StaticLLMClient` for tests.
- :class:`IntentParser`, which drives an LLM client and retries on
  schema-validation failures.
- :func:`parse_offline`, a deterministic regex-based parser used in
  tests and as a no-network fallback.
"""

from __future__ import annotations

from aerosynthx.intent.errors import (
    EnvelopeError,
    IntentError,
    LLMParseError,
    SchemaValidationError,
)
from aerosynthx.intent.llm import LLMClient, StaticLLMClient
from aerosynthx.intent.offline import OFFLINE_MODEL_NAME, parse_offline
from aerosynthx.intent.parser import IntentParser
from aerosynthx.intent.schemas import (
    AirfoilSpec,
    Assumption,
    DesignIntent,
    FlowCondition,
    ParseResult,
    ProvenanceMap,
    design_intent_json_schema,
)

__all__ = [
    "OFFLINE_MODEL_NAME",
    "AirfoilSpec",
    "Assumption",
    "DesignIntent",
    "EnvelopeError",
    "FlowCondition",
    "IntentError",
    "IntentParser",
    "LLMClient",
    "LLMParseError",
    "ParseResult",
    "ProvenanceMap",
    "SchemaValidationError",
    "StaticLLMClient",
    "design_intent_json_schema",
    "parse_offline",
]
