"""In-process rate limiting and request body-size limits.

Zero external dependencies: a thread-safe token-bucket throttles requests
per principal (API key when present, else client IP) and a body-size guard
rejects oversized payloads before they are handled. Both are enforced by a
single middleware applied only to the ``/api/v1/`` data plane.

The bucket's clock is injectable so behaviour is deterministic under test.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from aerosynthx.observability import METRICS

_RATE_ENV = "AEROSYNTHX_RATE_LIMIT"
_WINDOW_ENV = "AEROSYNTHX_RATE_WINDOW_SECONDS"
_BODY_ENV = "AEROSYNTHX_MAX_BODY_BYTES"

_DEFAULT_WINDOW_SECONDS = 60.0
_DEFAULT_MAX_BODY_BYTES = 1_048_576  # 1 MiB

_RATE_COUNTER = METRICS.counter(
    "aerosynthx_rate_limited_total",
    "Requests rejected by the rate/body-size guard, labelled by reason.",
    label_names=("reason",),
)


@dataclass
class _Bucket:
    tokens: float
    updated: float


@dataclass
class RateLimiter:
    """A thread-safe token-bucket limiter keyed by an arbitrary principal."""

    capacity: float
    window_seconds: float
    clock: Callable[[], float] = time.monotonic
    _buckets: dict[str, _Bucket] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def _refill_per_sec(self) -> float:
        return self.capacity / self.window_seconds

    def allow(self, principal: str) -> tuple[bool, float]:
        """Consume one token for ``principal``.

        Returns ``(allowed, retry_after_seconds)``. ``retry_after`` is
        ``0.0`` when allowed.
        """
        now = self.clock()
        with self._lock:
            bucket = self._buckets.get(principal)
            if bucket is None:
                bucket = _Bucket(tokens=self.capacity, updated=now)
                self._buckets[principal] = bucket
            else:
                elapsed = now - bucket.updated
                bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self._refill_per_sec)
                bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            retry_after = (1.0 - bucket.tokens) / self._refill_per_sec
            return False, retry_after


def principal_for(request: Request) -> str:
    """Derive a stable rate-limit principal for ``request``.

    Prefers the presented API key (``X-API-Key`` or ``Bearer`` token);
    otherwise falls back to the client IP, or ``"anonymous"`` when even
    that is unavailable.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key}"
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return f"key:{token}"
    client = request.client
    host = client.host if client is not None else "anonymous"
    return f"ip:{host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce body-size and rate limits on the ``/api/v1/`` data plane."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RateLimiter | None,
        max_body_bytes: int,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Reject oversized or throttled API requests; otherwise pass through."""
        if request.url.path.startswith("/api/v1/"):
            if self._max_body_bytes > 0:
                content_length = request.headers.get("content-length")
                if (
                    content_length is not None
                    and content_length.isdigit()
                    and int(content_length) > self._max_body_bytes
                ):
                    _RATE_COUNTER.inc(reason="body_too_large")
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "request body too large"},
                    )
            if self._limiter is not None:
                allowed, retry_after = self._limiter.allow(principal_for(request))
                if not allowed:
                    _RATE_COUNTER.inc(reason="rate_limited")
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "rate limit exceeded"},
                        headers={"Retry-After": str(int(retry_after) + 1)},
                    )
        response: Response = await call_next(request)
        return response


def _int_from_env(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_from_env(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RateLimitSettings:
    """Resolved rate-limit configuration."""

    capacity: int
    window_seconds: float
    max_body_bytes: int

    @classmethod
    def resolve(
        cls,
        *,
        rate_limit: int | None,
        rate_window_seconds: float | None,
        max_body_bytes: int | None,
        env: Mapping[str, str] | None = None,
    ) -> RateLimitSettings:
        """Combine explicit arguments with environment fallbacks.

        Any argument left as ``None`` is read from the environment
        (``AEROSYNTHX_RATE_LIMIT`` / ``_RATE_WINDOW_SECONDS`` /
        ``_MAX_BODY_BYTES``).
        """
        source = os.environ if env is None else env
        capacity = rate_limit if rate_limit is not None else _int_from_env(source, _RATE_ENV, 0)
        window = (
            rate_window_seconds
            if rate_window_seconds is not None
            else _float_from_env(source, _WINDOW_ENV, _DEFAULT_WINDOW_SECONDS)
        )
        body = (
            max_body_bytes
            if max_body_bytes is not None
            else _int_from_env(source, _BODY_ENV, _DEFAULT_MAX_BODY_BYTES)
        )
        return cls(capacity=capacity, window_seconds=window, max_body_bytes=body)

    def build_limiter(self) -> RateLimiter | None:
        """Return a :class:`RateLimiter` when enabled, else ``None``."""
        if self.capacity <= 0:
            return None
        return RateLimiter(capacity=float(self.capacity), window_seconds=self.window_seconds)
