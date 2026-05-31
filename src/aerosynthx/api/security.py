"""API-key authentication for the AeroSynthX HTTP API.

Zero external dependencies: accepted keys are hashed with SHA-256 at rest
and compared in constant time via :func:`hmac.compare_digest`. When no
keys are configured the API runs in *open* mode (backward compatible),
and the dependency becomes a no-op.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from fastapi import Header, HTTPException, status

from aerosynthx.observability import METRICS

_ENV_VAR = "AEROSYNTHX_API_KEYS"

_AUTH_COUNTER = METRICS.counter(
    "aerosynthx_auth_attempts_total",
    "API-key authentication attempts, labelled by result.",
    label_names=("result",),
)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyStore:
    """An immutable set of accepted API keys, stored as SHA-256 hashes."""

    hashes: frozenset[str] = field(default_factory=frozenset)

    @property
    def enabled(self) -> bool:
        """Return ``True`` when at least one key is configured."""
        return bool(self.hashes)

    @classmethod
    def from_keys(cls, keys: Iterable[str]) -> ApiKeyStore:
        """Build a store from raw key strings (blank entries are ignored)."""
        return cls(hashes=frozenset(_hash_key(k.strip()) for k in keys if k.strip()))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApiKeyStore:
        """Build a store from ``AEROSYNTHX_API_KEYS`` (comma-separated)."""
        source = os.environ if env is None else env
        return cls.from_keys(source.get(_ENV_VAR, "").split(","))

    def verify(self, presented: str | None) -> bool:
        """Constant-time check that ``presented`` is an accepted key."""
        if not presented:
            return False
        candidate = _hash_key(presented)
        accepted = False
        for stored in self.hashes:
            # Accumulate (no short-circuit) to keep timing uniform.
            accepted |= hmac.compare_digest(candidate, stored)
        return accepted


def make_api_key_dependency(store: ApiKeyStore) -> Callable[[str | None, str | None], None]:
    """Build a FastAPI dependency that enforces ``store``'s API keys.

    The returned callable reads the ``X-API-Key`` header, falling back to
    ``Authorization: Bearer <key>``. It is a no-op when ``store`` is
    disabled (no keys configured).
    """

    def dependency(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ) -> None:
        if not store.enabled:
            _AUTH_COUNTER.inc(result="disabled")
            return
        presented = x_api_key
        if presented is None and authorization is not None:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token:
                presented = token
        if presented is None:
            _AUTH_COUNTER.inc(result="missing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not store.verify(presented):
            _AUTH_COUNTER.inc(result="invalid")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        _AUTH_COUNTER.inc(result="ok")

    return dependency
