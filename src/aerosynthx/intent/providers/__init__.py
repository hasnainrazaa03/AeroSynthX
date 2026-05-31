"""Concrete LLM provider adapters.

These are opt-in: nothing here performs a network call unless the user
explicitly configures a provider (via :func:`build_client_from_env` or
by constructing a client directly). The engineering core remains
network-free; this package lives at the edge of the intent layer.

The network boundary is a single injectable ``transport`` callable so
the adapters are fully unit-testable without sockets.
"""

from __future__ import annotations

from aerosynthx.intent.providers.openai import (
    OpenAICompatibleClient,
    ProviderConfig,
    ProviderError,
    RetryPolicy,
    TransientProviderError,
    Transport,
    build_client_from_env,
)

__all__ = [
    "OpenAICompatibleClient",
    "ProviderConfig",
    "ProviderError",
    "RetryPolicy",
    "TransientProviderError",
    "Transport",
    "build_client_from_env",
]
