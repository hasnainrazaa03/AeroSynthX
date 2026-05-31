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
from enum import StrEnum

from fastapi import Header, HTTPException, status

from aerosynthx.observability import METRICS

_ENV_VAR = "AEROSYNTHX_API_KEYS"

_AUTH_COUNTER = METRICS.counter(
    "aerosynthx_auth_attempts_total",
    "API-key authentication attempts, labelled by result.",
    label_names=("result",),
)


class Scope(StrEnum):
    """Capabilities a key may be granted."""

    READ = "read"
    RUN = "run"


_ALL_SCOPES: frozenset[Scope] = frozenset(Scope)


def _parse_scopes(raw: str) -> frozenset[Scope]:
    """Parse a ``read|run`` (or space-separated) scope spec, ignoring junk."""
    scopes: set[Scope] = set()
    for token in raw.replace("|", " ").split():
        try:
            scopes.add(Scope(token.strip().lower()))
        except ValueError:
            continue
    return frozenset(scopes)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyStore:
    """Accepted API keys (SHA-256 hashes) mapped to their granted scopes."""

    scopes_by_hash: Mapping[str, frozenset[Scope]] = field(default_factory=dict)

    @property
    def hashes(self) -> frozenset[str]:
        """Return the set of accepted key hashes."""
        return frozenset(self.scopes_by_hash)

    @property
    def enabled(self) -> bool:
        """Return ``True`` when at least one key is configured."""
        return bool(self.scopes_by_hash)

    @classmethod
    def from_keys(
        cls, keys: Iterable[str], *, scopes: Iterable[Scope] | None = None
    ) -> ApiKeyStore:
        """Build a store from raw key strings (blank entries are ignored).

        Every key is granted ``scopes`` (all scopes by default).
        """
        granted = _ALL_SCOPES if scopes is None else frozenset(scopes)
        mapping = {_hash_key(k.strip()): granted for k in keys if k.strip()}
        return cls(scopes_by_hash=mapping)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApiKeyStore:
        """Build a store from ``AEROSYNTHX_API_KEYS`` (comma-separated).

        Each entry is ``key`` (all scopes) or ``key:read|run`` (explicit
        scopes). Blank entries and entries with an empty key are skipped.
        """
        source = os.environ if env is None else env
        mapping: dict[str, frozenset[Scope]] = {}
        for entry in source.get(_ENV_VAR, "").split(","):
            spec = entry.strip()
            if not spec:
                continue
            key_part, sep, scope_part = spec.partition(":")
            key = key_part.strip()
            if not key:
                continue
            scopes = _parse_scopes(scope_part) if sep and scope_part.strip() else _ALL_SCOPES
            mapping[_hash_key(key)] = scopes
        return cls(scopes_by_hash=mapping)

    def verify(self, presented: str | None) -> bool:
        """Constant-time check that ``presented`` is an accepted key."""
        if not presented:
            return False
        candidate = _hash_key(presented)
        accepted = False
        for stored in self.scopes_by_hash:
            # Accumulate (no short-circuit) to keep timing uniform.
            accepted |= hmac.compare_digest(candidate, stored)
        return accepted

    def scopes_for(self, presented: str | None) -> frozenset[Scope]:
        """Return the scopes granted to ``presented`` (empty if unknown)."""
        if not presented:
            return frozenset()
        candidate = _hash_key(presented)
        matched: frozenset[Scope] = frozenset()
        for stored, scopes in self.scopes_by_hash.items():
            if hmac.compare_digest(candidate, stored):
                matched = scopes
        return matched


def make_api_key_dependency(
    store: ApiKeyStore, *, required_scope: Scope | None = None
) -> Callable[[str | None, str | None], None]:
    """Build a FastAPI dependency that enforces ``store``'s API keys.

    The returned callable reads the ``X-API-Key`` header, falling back to
    ``Authorization: Bearer <key>``. It is a no-op when ``store`` is
    disabled (no keys configured). When ``required_scope`` is set, an
    authenticated key lacking that scope is rejected with ``403``.
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
        if required_scope is not None and required_scope not in store.scopes_for(presented):
            _AUTH_COUNTER.inc(result="forbidden")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing required scope: {required_scope.value}",
            )
        _AUTH_COUNTER.inc(result="ok")

    return dependency
