"""OpenAI Chat-Completions-compatible LLM client.

Works against any endpoint speaking the OpenAI ``/chat/completions``
shape: OpenAI itself, Azure OpenAI, Ollama, vLLM, and LM Studio. JSON
output is requested via ``response_format={"type": "json_object"}`` and
the JSON Schema is embedded in the system prompt for models that honour
it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from aerosynthx.intent.errors import IntentError

_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_TIMEOUT = 30.0


class ProviderError(IntentError):
    """Raised when an LLM provider transport or decode step fails."""

    code = "intent.provider.error"


class Transport(Protocol):
    """The single network seam: POST a JSON body, return the JSON reply."""

    def __call__(
        self, *, url: str, headers: Mapping[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Send ``payload`` to ``url`` and return the decoded JSON body."""
        ...


def _urllib_transport(
    *, url: str, headers: Mapping[str, str], payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # pragma: no cover - exercised via fake transport
        detail = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
        raise ProviderError(
            f"provider returned HTTP {exc.code}: {detail}",
            code="intent.provider.http_error",
        ) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise ProviderError(
            f"provider request failed: {exc.reason}",
            code="intent.provider.unreachable",
        ) from exc
    try:
        decoded: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - malformed upstream
        raise ProviderError(
            "provider returned non-JSON body",
            code="intent.provider.bad_body",
        ) from exc
    return decoded


@dataclass(frozen=True)
class ProviderConfig:
    """Connection settings for an OpenAI-compatible endpoint."""

    model: str = _DEFAULT_MODEL
    base_url: str = _DEFAULT_BASE_URL
    api_key: str | None = None
    timeout: float = _DEFAULT_TIMEOUT
    extra_headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def chat_completions_url(self) -> str:
        """Full URL of the chat-completions endpoint."""
        return f"{self.base_url.rstrip('/')}/chat/completions"


class OpenAICompatibleClient:
    """An :class:`~aerosynthx.intent.llm.LLMClient` backed by HTTP chat."""

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._config = config if config is not None else ProviderConfig()
        self._transport: Transport = transport if transport is not None else _urllib_transport

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Request a JSON object from the model and return it as a dict."""
        cfg = self._config
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        headers.update(cfg.extra_headers)

        schema_text = json.dumps(schema, sort_keys=True)
        payload: dict[str, Any] = {
            "model": cfg.model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{system_prompt}\n\nJSON Schema:\n{schema_text}",
                },
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

        reply = self._transport(
            url=cfg.chat_completions_url,
            headers=headers,
            payload=payload,
            timeout=cfg.timeout,
        )
        return _extract_json_content(reply)


def _extract_json_content(reply: dict[str, Any]) -> dict[str, Any]:
    """Pull the assistant message content out of a chat-completions reply."""
    try:
        choices = reply["choices"]
        content = choices[0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            "provider reply missing choices[0].message.content",
            code="intent.provider.bad_shape",
        ) from exc
    if not isinstance(content, str):
        raise ProviderError(
            f"assistant content was {type(content).__name__}, expected str",
            code="intent.provider.bad_content",
        )
    try:
        parsed: Any = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "assistant content was not valid JSON",
            code="intent.provider.content_not_json",
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderError(
            f"assistant JSON was {type(parsed).__name__}, expected object",
            code="intent.provider.content_not_object",
        )
    return parsed


def build_client_from_env(
    env: Mapping[str, str] | None = None,
) -> OpenAICompatibleClient | None:
    """Construct a client from ``AEROSYNTHX_LLM_*`` variables.

    Returns ``None`` when ``AEROSYNTHX_LLM_PROVIDER`` is unset, signalling
    that the caller should stay in offline mode.

    Raises:
        ProviderError: When the provider name is set but unsupported, or
            a numeric variable cannot be parsed.
    """
    source = env if env is not None else os.environ
    provider = source.get("AEROSYNTHX_LLM_PROVIDER", "").strip().lower()
    if not provider:
        return None
    if provider != "openai":
        raise ProviderError(
            f"unsupported LLM provider {provider!r}; only 'openai' is supported",
            code="intent.provider.unsupported",
        )

    timeout_raw = source.get("AEROSYNTHX_LLM_TIMEOUT", "").strip()
    try:
        timeout = float(timeout_raw) if timeout_raw else _DEFAULT_TIMEOUT
    except ValueError as exc:
        raise ProviderError(
            f"AEROSYNTHX_LLM_TIMEOUT must be numeric, got {timeout_raw!r}",
            code="intent.provider.bad_timeout",
        ) from exc

    config = ProviderConfig(
        model=source.get("AEROSYNTHX_LLM_MODEL", "").strip() or _DEFAULT_MODEL,
        base_url=source.get("AEROSYNTHX_LLM_BASE_URL", "").strip() or _DEFAULT_BASE_URL,
        api_key=source.get("AEROSYNTHX_LLM_API_KEY", "").strip() or None,
        timeout=timeout,
    )
    return OpenAICompatibleClient(config)
