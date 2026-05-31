from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from aerosynthx.intent import parse_offline
from aerosynthx.intent.providers import (
    OpenAICompatibleClient,
    ProviderConfig,
    ProviderError,
    RetryPolicy,
    TransientProviderError,
    build_client_from_env,
)
from aerosynthx.intent.providers import openai as openai_mod
from aerosynthx.intent.providers.openai import _extract_json_content, _urllib_transport


def _valid_intent_dict() -> dict[str, Any]:
    result = parse_offline("NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m.")
    return result.intent.model_dump(mode="json")


def _chat_reply(content: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_config_url_strips_trailing_slash() -> None:
    cfg = ProviderConfig(base_url="https://example.com/v1/")
    assert cfg.chat_completions_url == "https://example.com/v1/chat/completions"


def test_client_round_trips_through_transport() -> None:
    captured: dict[str, Any] = {}
    intent = _valid_intent_dict()

    def fake_transport(
        *, url: str, headers: Mapping[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return _chat_reply(intent)

    client = OpenAICompatibleClient(
        ProviderConfig(api_key="sk-test", extra_headers={"X-Org": "acme"}),
        transport=fake_transport,
    )
    out = client.complete_json(system_prompt="sys", user_prompt="hi", schema={"type": "object"})
    assert out == intent
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["X-Org"] == "acme"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["url"].endswith("/chat/completions")
    assert captured["timeout"] == 30.0


def test_client_without_api_key_omits_auth_header() -> None:
    def fake_transport(**kwargs: Any) -> dict[str, Any]:
        assert "Authorization" not in kwargs["headers"]
        return _chat_reply(_valid_intent_dict())

    client = OpenAICompatibleClient(transport=fake_transport)
    client.complete_json(system_prompt="s", user_prompt="u", schema={})


def test_extract_rejects_missing_choices() -> None:
    with pytest.raises(ProviderError) as exc:
        _extract_json_content({"nope": True})
    assert exc.value.code == "intent.provider.bad_shape"


def test_extract_rejects_non_string_content() -> None:
    with pytest.raises(ProviderError) as exc:
        _extract_json_content({"choices": [{"message": {"content": 123}}]})
    assert exc.value.code == "intent.provider.bad_content"


def test_extract_rejects_non_json_content() -> None:
    with pytest.raises(ProviderError) as exc:
        _extract_json_content({"choices": [{"message": {"content": "not json"}}]})
    assert exc.value.code == "intent.provider.content_not_json"


def test_extract_rejects_non_object_json() -> None:
    with pytest.raises(ProviderError) as exc:
        _extract_json_content({"choices": [{"message": {"content": "[1, 2, 3]"}}]})
    assert exc.value.code == "intent.provider.content_not_object"


def test_build_client_returns_none_when_unset() -> None:
    assert build_client_from_env({}) is None


def test_build_client_rejects_unknown_provider() -> None:
    with pytest.raises(ProviderError) as exc:
        build_client_from_env({"AEROSYNTHX_LLM_PROVIDER": "anthropic"})
    assert exc.value.code == "intent.provider.unsupported"


def test_build_client_rejects_bad_timeout() -> None:
    with pytest.raises(ProviderError) as exc:
        build_client_from_env(
            {"AEROSYNTHX_LLM_PROVIDER": "openai", "AEROSYNTHX_LLM_TIMEOUT": "soon"}
        )
    assert exc.value.code == "intent.provider.bad_timeout"


def test_build_client_uses_defaults() -> None:
    client = build_client_from_env({"AEROSYNTHX_LLM_PROVIDER": "OpenAI"})
    assert isinstance(client, OpenAICompatibleClient)
    cfg = client._config
    assert cfg.model == "gpt-4o-mini"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.api_key is None
    assert cfg.timeout == 30.0


def test_build_client_reads_all_overrides() -> None:
    client = build_client_from_env(
        {
            "AEROSYNTHX_LLM_PROVIDER": "openai",
            "AEROSYNTHX_LLM_MODEL": "llama3",
            "AEROSYNTHX_LLM_BASE_URL": "http://localhost:11434/v1",
            "AEROSYNTHX_LLM_API_KEY": "local-key",
            "AEROSYNTHX_LLM_TIMEOUT": "12.5",
        }
    )
    assert isinstance(client, OpenAICompatibleClient)
    cfg = client._config
    assert cfg.model == "llama3"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.api_key == "local-key"
    assert cfg.timeout == 12.5


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_urllib_transport_posts_and_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        captured["full_url"] = request.full_url
        captured["data"] = request.data
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return _FakeResponse(json.dumps({"ok": True}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = _urllib_transport(
        url="https://example.com/v1/chat/completions",
        headers={"Authorization": "Bearer x"},
        payload={"model": "m"},
        timeout=7.0,
    )
    assert out == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["timeout"] == 7.0
    assert json.loads(captured["data"]) == {"model": "m"}


def test_default_client_uses_urllib_transport() -> None:
    client = OpenAICompatibleClient()
    assert client._transport is openai_mod._urllib_transport


# --- Phase 12: retry with exponential backoff ---------------------------------


def test_is_retryable_status_classifies_codes() -> None:
    for code in (408, 425, 429, 500, 502, 503, 504):
        assert openai_mod._is_retryable_status(code)
    for code in (200, 400, 401, 403, 404, 422):
        assert not openai_mod._is_retryable_status(code)


def test_parse_retry_after_handles_values() -> None:
    assert openai_mod._parse_retry_after(None) is None
    assert openai_mod._parse_retry_after("2.5") == 2.5
    assert openai_mod._parse_retry_after("not-a-number") is None


def test_delay_for_grows_caps_and_jitters() -> None:
    policy = RetryPolicy(
        base_delay=1.0, max_delay=10.0, multiplier=2.0, jitter=0.0, rng=lambda: 0.5
    )
    assert policy.delay_for(0) == 1.0
    assert policy.delay_for(1) == 2.0
    assert policy.delay_for(2) == 4.0
    # Capped at max_delay.
    assert policy.delay_for(10) == 10.0


def test_delay_for_applies_jitter() -> None:
    policy = RetryPolicy(
        base_delay=2.0, max_delay=10.0, multiplier=2.0, jitter=0.5, rng=lambda: 1.0
    )
    # capped=2.0, jitter term = 0.5 * 2.0 * 1.0 = 1.0 -> 3.0
    assert policy.delay_for(0) == 3.0


def _transient() -> TransientProviderError:
    return TransientProviderError("boom", status_code=503)


def test_retry_then_succeed() -> None:
    intent = _valid_intent_dict()
    calls = {"n": 0}
    slept: list[float] = []

    def flaky_transport(**_: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _transient()
        return _chat_reply(intent)

    policy = RetryPolicy(max_attempts=3, base_delay=1.0, jitter=0.0, sleep=slept.append)
    client = OpenAICompatibleClient(transport=flaky_transport, retry_policy=policy)
    out = client.complete_json(system_prompt="s", user_prompt="u", schema={})
    assert out == intent
    assert calls["n"] == 3
    # Two backoff sleeps: delay_for(0)=1.0, delay_for(1)=2.0.
    assert slept == [1.0, 2.0]


def test_retry_exhausts_and_raises() -> None:
    slept: list[float] = []

    def always_transient(**_: Any) -> dict[str, Any]:
        raise _transient()

    policy = RetryPolicy(max_attempts=2, base_delay=1.0, jitter=0.0, sleep=slept.append)
    client = OpenAICompatibleClient(transport=always_transient, retry_policy=policy)
    with pytest.raises(TransientProviderError):
        client.complete_json(system_prompt="s", user_prompt="u", schema={})
    # One retry sleep before giving up on the second attempt.
    assert slept == [1.0]


def test_permanent_error_is_not_retried() -> None:
    calls = {"n": 0}

    def permanent(**_: Any) -> dict[str, Any]:
        calls["n"] += 1
        raise ProviderError("nope", code="intent.provider.http_error")

    policy = RetryPolicy(max_attempts=5, sleep=lambda _: None)
    client = OpenAICompatibleClient(transport=permanent, retry_policy=policy)
    with pytest.raises(ProviderError):
        client.complete_json(system_prompt="s", user_prompt="u", schema={})
    assert calls["n"] == 1


def test_build_client_reads_retry_overrides() -> None:
    client = build_client_from_env(
        {
            "AEROSYNTHX_LLM_PROVIDER": "openai",
            "AEROSYNTHX_LLM_RETRIES": "5",
            "AEROSYNTHX_LLM_RETRY_BASE_SECONDS": "0.25",
            "AEROSYNTHX_LLM_RETRY_MAX_SECONDS": "16",
        }
    )
    assert isinstance(client, OpenAICompatibleClient)
    assert client._retry.max_attempts == 5
    assert client._retry.base_delay == 0.25
    assert client._retry.max_delay == 16.0


def test_build_client_uses_default_retry_policy() -> None:
    client = build_client_from_env({"AEROSYNTHX_LLM_PROVIDER": "openai"})
    assert isinstance(client, OpenAICompatibleClient)
    assert client._retry.max_attempts == 3
    assert client._retry.base_delay == 0.5
    assert client._retry.max_delay == 8.0


def test_build_client_rejects_bad_retries() -> None:
    with pytest.raises(ProviderError) as exc:
        build_client_from_env(
            {"AEROSYNTHX_LLM_PROVIDER": "openai", "AEROSYNTHX_LLM_RETRIES": "lots"}
        )
    assert exc.value.code == "intent.provider.bad_retry"


def test_build_client_rejects_bad_retry_base() -> None:
    with pytest.raises(ProviderError) as exc:
        build_client_from_env(
            {
                "AEROSYNTHX_LLM_PROVIDER": "openai",
                "AEROSYNTHX_LLM_RETRY_BASE_SECONDS": "soon",
            }
        )
    assert exc.value.code == "intent.provider.bad_retry"


def test_transient_error_carries_metadata() -> None:
    err = TransientProviderError("x", status_code=429, retry_after=3.0)
    assert err.status_code == 429
    assert err.retry_after == 3.0
    assert err.code == "intent.provider.transient"
