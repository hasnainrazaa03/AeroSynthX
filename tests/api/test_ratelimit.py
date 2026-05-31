from __future__ import annotations

from dataclasses import dataclass

from aerosynthx.api.ratelimit import (
    RateLimiter,
    RateLimitSettings,
    principal_for,
)


@dataclass
class _Clock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_allows_up_to_capacity() -> None:
    clock = _Clock()
    limiter = RateLimiter(capacity=2, window_seconds=10.0, clock=clock)
    assert limiter.allow("k")[0] is True
    assert limiter.allow("k")[0] is True
    allowed, retry_after = limiter.allow("k")
    assert allowed is False
    assert retry_after > 0.0


def test_rate_limiter_refills_over_time() -> None:
    clock = _Clock()
    limiter = RateLimiter(capacity=1, window_seconds=10.0, clock=clock)
    assert limiter.allow("k")[0] is True
    assert limiter.allow("k")[0] is False
    # One full window restores capacity.
    clock.now = 10.0
    assert limiter.allow("k")[0] is True


def test_rate_limiter_isolates_principals() -> None:
    clock = _Clock()
    limiter = RateLimiter(capacity=1, window_seconds=10.0, clock=clock)
    assert limiter.allow("a")[0] is True
    assert limiter.allow("b")[0] is True
    assert limiter.allow("a")[0] is False


class _FakeRequest:
    def __init__(self, headers: dict[str, str], client_host: str | None = "1.2.3.4") -> None:
        self.headers = headers
        self.client = None if client_host is None else type("C", (), {"host": client_host})()


def test_principal_prefers_api_key() -> None:
    req = _FakeRequest({"X-API-Key": "abc"})
    assert principal_for(req) == "key:abc"  # type: ignore[arg-type]


def test_principal_uses_bearer_token() -> None:
    req = _FakeRequest({"Authorization": "Bearer tok"})
    assert principal_for(req) == "key:tok"  # type: ignore[arg-type]


def test_principal_ignores_non_bearer_and_uses_ip() -> None:
    req = _FakeRequest({"Authorization": "Basic xyz"})
    assert principal_for(req) == "ip:1.2.3.4"  # type: ignore[arg-type]


def test_principal_falls_back_to_ip() -> None:
    req = _FakeRequest({})
    assert principal_for(req) == "ip:1.2.3.4"  # type: ignore[arg-type]


def test_principal_anonymous_without_client() -> None:
    req = _FakeRequest({}, client_host=None)
    assert principal_for(req) == "ip:anonymous"  # type: ignore[arg-type]


def test_settings_resolve_uses_explicit_args() -> None:
    s = RateLimitSettings.resolve(
        rate_limit=5, rate_window_seconds=30.0, max_body_bytes=100, env={}
    )
    assert s == RateLimitSettings(capacity=5, window_seconds=30.0, max_body_bytes=100)


def test_settings_resolve_reads_env() -> None:
    env = {
        "AEROSYNTHX_RATE_LIMIT": "7",
        "AEROSYNTHX_RATE_WINDOW_SECONDS": "15",
        "AEROSYNTHX_MAX_BODY_BYTES": "200",
    }
    s = RateLimitSettings.resolve(
        rate_limit=None, rate_window_seconds=None, max_body_bytes=None, env=env
    )
    assert s == RateLimitSettings(capacity=7, window_seconds=15.0, max_body_bytes=200)


def test_settings_resolve_defaults_and_ignores_bad_env() -> None:
    env = {
        "AEROSYNTHX_RATE_LIMIT": "not-int",
        "AEROSYNTHX_RATE_WINDOW_SECONDS": "nope",
        "AEROSYNTHX_MAX_BODY_BYTES": "bad",
    }
    s = RateLimitSettings.resolve(
        rate_limit=None, rate_window_seconds=None, max_body_bytes=None, env=env
    )
    assert s == RateLimitSettings(capacity=0, window_seconds=60.0, max_body_bytes=1_048_576)


def test_build_limiter_disabled_when_capacity_non_positive() -> None:
    assert RateLimitSettings(0, 60.0, 1024).build_limiter() is None


def test_build_limiter_enabled() -> None:
    limiter = RateLimitSettings(3, 60.0, 1024).build_limiter()
    assert isinstance(limiter, RateLimiter)
    assert limiter.capacity == 3.0
