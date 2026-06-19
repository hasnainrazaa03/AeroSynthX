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
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from aerosynthx.intent.errors import IntentError
from aerosynthx.observability import METRICS

_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_TIMEOUT = 30.0

_DEFAULT_RETRIES = 3
_DEFAULT_RETRY_BASE_SECONDS = 0.5
_DEFAULT_RETRY_MAX_SECONDS = 8.0

# HTTP statuses worth retrying: request timeout, too-early, rate limited,
# and the transient 5xx family.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

_RETRY_COUNTER = METRICS.counter(
    "aerosynthx_llm_retries_total",
    "LLM provider transport retries, labelled by outcome.",
    label_names=("outcome",),
)


class ProviderError(IntentError):
    """Raised when an LLM provider transport or decode step fails."""

    code = "intent.provider.error"


class TransientProviderError(ProviderError):
    """A retryable provider failure (HTTP 429/5xx or a connection blip)."""

    code = "intent.provider.transient"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.status_code = status_code
        self.retry_after = retry_after


def _is_retryable_status(status: int) -> bool:
    """Return ``True`` when an HTTP status code is worth retrying."""
    return status in _RETRYABLE_STATUS


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
        if _is_retryable_status(exc.code):
            retry_after_raw = exc.headers.get("Retry-After") if exc.headers else None
            raise TransientProviderError(
                f"provider returned HTTP {exc.code}: {detail}",
                code="intent.provider.http_error",
                status_code=exc.code,
                retry_after=_parse_retry_after(retry_after_raw),
            ) from exc
        raise ProviderError(
            f"provider returned HTTP {exc.code}: {detail}",
            code="intent.provider.http_error",
        ) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise TransientProviderError(
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


def _parse_retry_after(raw: str | None) -> float | None:
    """Parse a numeric ``Retry-After`` header value into seconds."""
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class RetryPolicy(BaseModel):
    """Exponential-backoff settings for transient provider failures."""
    model_config = ConfigDict(frozen=True)

    max_attempts: int = _DEFAULT_RETRIES
    base_delay: float = _DEFAULT_RETRY_BASE_SECONDS
    max_delay: float = _DEFAULT_RETRY_MAX_SECONDS
    multiplier: float = 2.0
    jitter: float = 0.1
    sleep: Callable[[float], None] = Field(default=time.sleep, exclude=True)
    rng: Callable[[], float] = Field(default=random.random, exclude=True)

    def delay_for(self, retry_index: int) -> float:
        """Return the backoff delay (seconds) before retry ``retry_index``."""
        capped = min(self.base_delay * (self.multiplier**retry_index), self.max_delay)
        return capped + self.jitter * capped * self.rng()


class ProviderConfig(BaseModel):
    """Connection settings for an OpenAI-compatible endpoint."""
    model_config = ConfigDict(frozen=True)

    model: str = _DEFAULT_MODEL
    base_url: str = _DEFAULT_BASE_URL
    api_key: str | None = None
    timeout: float = _DEFAULT_TIMEOUT
    extra_headers: Mapping[str, str] = Field(default_factory=dict)

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
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._config = config if config is not None else ProviderConfig()
        self._transport: Transport = transport if transport is not None else _urllib_transport
        self._retry = retry_policy if retry_policy is not None else RetryPolicy()

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

        reply = self._call_with_retry(
            url=cfg.chat_completions_url,
            headers=headers,
            payload=payload,
            timeout=cfg.timeout,
        )
        return _extract_json_content(reply)

    def _call_with_retry(
        self, *, url: str, headers: Mapping[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        """Invoke the transport, retrying transient failures with backoff."""
        policy = self._retry
        attempt = 0
        while True:
            try:
                return self._transport(url=url, headers=headers, payload=payload, timeout=timeout)
            except TransientProviderError:
                attempt += 1
                if attempt >= policy.max_attempts:
                    _RETRY_COUNTER.inc(outcome="exhausted")
                    raise
                _RETRY_COUNTER.inc(outcome="retry")
                policy.sleep(policy.delay_for(attempt - 1))


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

    retry_policy = RetryPolicy(
        max_attempts=_env_int(source, "AEROSYNTHX_LLM_RETRIES", _DEFAULT_RETRIES),
        base_delay=_env_float(
            source, "AEROSYNTHX_LLM_RETRY_BASE_SECONDS", _DEFAULT_RETRY_BASE_SECONDS
        ),
        max_delay=_env_float(
            source, "AEROSYNTHX_LLM_RETRY_MAX_SECONDS", _DEFAULT_RETRY_MAX_SECONDS
        ),
    )

    config = ProviderConfig(
        model=source.get("AEROSYNTHX_LLM_MODEL", "").strip() or _DEFAULT_MODEL,
        base_url=source.get("AEROSYNTHX_LLM_BASE_URL", "").strip() or _DEFAULT_BASE_URL,
        api_key=source.get("AEROSYNTHX_LLM_API_KEY", "").strip() or None,
        timeout=timeout,
    )
    return OpenAICompatibleClient(config, retry_policy=retry_policy)


def _env_int(source: Mapping[str, str], name: str, default: int) -> int:
    """Parse an integer env var, raising ``ProviderError`` on bad input."""
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ProviderError(
            f"{name} must be an integer, got {raw!r}",
            code="intent.provider.bad_retry",
        ) from exc


def _env_float(source: Mapping[str, str], name: str, default: float) -> float:
    """Parse a float env var, raising ``ProviderError`` on bad input."""
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ProviderError(
            f"{name} must be numeric, got {raw!r}",
            code="intent.provider.bad_retry",
        ) from exc
