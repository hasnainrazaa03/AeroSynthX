"""Tests for the LLM-backed intent parser and its retry loop."""

from __future__ import annotations

from typing import Any

import pytest

from aerosynthx.intent import (
    IntentParser,
    LLMParseError,
    SchemaValidationError,
    StaticLLMClient,
)


def _good_payload() -> dict[str, Any]:
    return {
        "airfoil": {"family": "naca4", "designation": "2412", "chord_m": 1.0},
        "flow": {
            "altitude_m": None,
            "velocity_m_s": 50.0,
            "mach": None,
            "angle_of_attack_deg": 3.0,
            "reynolds_target": None,
        },
        "assumptions": [],
        "provenance": {
            "fields": {
                "airfoil.family": "inferred",
                "airfoil.designation": "user_provided",
                "airfoil.chord_m": "user_provided",
                "flow.velocity_m_s": "user_provided",
                "flow.angle_of_attack_deg": "user_provided",
                "flow.altitude_m": "inferred",
            }
        },
        "notes": None,
    }


def _bad_payload() -> dict[str, Any]:
    payload = _good_payload()
    # Two violations: bogus chord + non-positive velocity.
    payload["airfoil"]["chord_m"] = -1.0
    payload["flow"]["velocity_m_s"] = -10.0
    return payload


# ----------------------------------------------------------- happy path


def test_parser_returns_validated_result_on_first_try() -> None:
    client = StaticLLMClient([_good_payload()])
    parser = IntentParser(client, max_retries=2, model_name="test-model")
    result = parser.parse("NACA 2412 at 50 m/s.")
    assert result.attempts == 1
    assert result.model == "test-model"
    assert result.intent.airfoil.designation == "2412"
    assert len(client.calls) == 1


def test_parser_succeeds_after_retry() -> None:
    client = StaticLLMClient([_bad_payload(), _good_payload()])
    parser = IntentParser(client, max_retries=2)
    result = parser.parse("anything")
    assert result.attempts == 2
    assert len(client.calls) == 2
    # The retry prompt must include the prior error report.
    _, retry_prompt = client.calls[1]
    assert "failed schema validation" in retry_prompt


def test_parser_raises_after_exhausting_retries() -> None:
    client = StaticLLMClient([_bad_payload(), _bad_payload(), _bad_payload()])
    parser = IntentParser(client, max_retries=2)
    with pytest.raises(SchemaValidationError) as ei:
        parser.parse("anything")
    assert "after 3 attempt(s)" in str(ei.value)
    assert ei.value.details  # carries Pydantic error report
    assert len(client.calls) == 3


def test_parser_default_retries() -> None:
    parser = IntentParser(StaticLLMClient([_good_payload()]))
    result = parser.parse("foo")
    assert result.attempts == 1


# ------------------------------------------------------------ bad input


def test_parser_rejects_empty_input() -> None:
    parser = IntentParser(StaticLLMClient([_good_payload()]))
    with pytest.raises(LLMParseError) as ei:
        parser.parse("   ")
    assert ei.value.code == "intent.llm.empty_input"


def test_parser_rejects_non_string_input() -> None:
    parser = IntentParser(StaticLLMClient([_good_payload()]))
    with pytest.raises(LLMParseError):
        parser.parse(None)  # type: ignore[arg-type]


def test_parser_rejects_non_dict_response() -> None:
    class BadClient:
        def complete_json(self, **_: Any) -> Any:
            return "not a dict"

    parser = IntentParser(BadClient())
    with pytest.raises(LLMParseError) as ei:
        parser.parse("foo")
    assert ei.value.code == "intent.llm.bad_payload"


def test_parser_wraps_client_exceptions() -> None:
    class ExplodingClient:
        def complete_json(self, **_: Any) -> Any:
            raise RuntimeError("transport down")

    parser = IntentParser(ExplodingClient())
    with pytest.raises(LLMParseError) as ei:
        parser.parse("foo")
    assert ei.value.code == "intent.llm.client_failure"
    assert "transport down" in str(ei.value)


def test_negative_retries_rejected() -> None:
    with pytest.raises(ValueError):
        IntentParser(StaticLLMClient([_good_payload()]), max_retries=-1)


def test_static_client_records_calls_and_schema_is_passed() -> None:
    client = StaticLLMClient([_good_payload()])
    parser = IntentParser(client)
    parser.parse("NACA 2412 at 50 m/s")
    assert len(client.calls) == 1
    system, user = client.calls[0]
    assert "schema" in system.lower() or "json" in system.lower()
    assert "NACA 2412" in user
