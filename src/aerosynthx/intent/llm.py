"""Provider-agnostic LLM client interface.

The core ships only an abstract :class:`LLMClient` ``Protocol``; concrete
providers (OpenAI, Anthropic, Azure, etc.) are wired in higher layers
(planned Phase 6/7). For tests and offline development, a deterministic
:class:`StaticLLMClient` returns pre-canned JSON responses.

This separation enforces the architectural rule that the engineering
core has no network dependencies.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """A minimal JSON-completion interface for intent parsing.

    Implementations MUST return a Python ``dict`` parsed from the
    model's JSON output. Network/transport errors are the
    implementation's responsibility to translate into appropriate
    exceptions; the parser only consumes the returned dict.
    """

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON object satisfying ``schema``."""
        ...


class StaticLLMClient:
    """A deterministic ``LLMClient`` that replays a queue of responses.

    Useful for testing the parser's retry loop without any network or
    nondeterminism. The client raises :class:`StopIteration` if it is
    called more times than it has queued responses; callers should
    queue enough entries for ``max_retries + 1`` parser attempts.

    Attributes:
        responses: Iterable of dicts to return on successive calls.
        calls: List of ``(system_prompt, user_prompt)`` tuples recorded
            for inspection.
    """

    def __init__(self, responses: Iterable[dict[str, Any]]) -> None:
        self._responses = iter(list(responses))
        self.calls: list[tuple[str, str]] = []

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the next queued response, recording the call."""
        self.calls.append((system_prompt, user_prompt))
        return next(self._responses)
