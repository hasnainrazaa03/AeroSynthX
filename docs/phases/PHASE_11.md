# Phase 11 — RBAC scopes + rate limiting + body-size limits (v1.4.0)

## Goal

Harden the HTTP control plane built in Phase 9 (API-key auth) with two
high-value **P1** security features from the roadmap, keeping the
zero-new-runtime-dependency, fully-offline-testable discipline:

1. **Per-key scopes (RBAC)** — a key may be granted `read` and/or `run`
   scopes. Read-only keys can list/inspect runs and download artifacts but
   cannot create runs.
2. **Rate limiting + request body-size limits** — an in-process token
   bucket throttles requests per principal (API key, else client IP), and
   oversized request bodies are rejected before handling.

## In scope

### RBAC (`aerosynthx.api.security`)
- `Scope(StrEnum)` with `READ = "read"` and `RUN = "run"`.
- `ApiKeyStore` evolves to map each key hash → granted scope set.
  - `hashes` property and `verify()` are retained (backward compatible).
  - `from_keys(keys, *, scopes=None)` grants **all** scopes by default
    (so `create_app(api_keys=[...])` and existing callers are unchanged).
  - `from_env()` parses a scoped syntax: entries are comma-separated;
    within an entry, `key:read|run` assigns scopes (separators `|` or
    space). A bare `key` (no `:`) grants all scopes (backward compatible).
  - `scopes_for(presented)` returns the matched key's scope set.
- `make_api_key_dependency(store, *, required_scope=None)` adds a scope
  check: an authenticated key lacking the required scope yields **403**
  (`aerosynthx_auth_attempts_total{result="forbidden"}`).
- Routes: `POST /api/v1/runs` requires `RUN`; all data-plane `GET`s
  require `READ`. Meta/UI endpoints stay open.

### Rate limiting + body-size (`aerosynthx.api.ratelimit`, new module)
- `TokenBucket` + thread-safe `RateLimiter(capacity, window_seconds,
  clock=...)` with an injectable monotonic clock for deterministic tests.
- `RateLimitMiddleware` enforces, **only on `/api/v1/` paths**:
  - `Content-Length` over `max_body_bytes` → **413**.
  - bucket exhausted → **429** with a `Retry-After` header.
  - principal = `X-API-Key` / `Bearer` token when present, else client IP.
- `aerosynthx_rate_limited_total{reason}` metric
  (reason ∈ {rate_limited, body_too_large}).
- Env config (read by `create_app` when args are omitted):
  - `AEROSYNTHX_RATE_LIMIT` (requests per window; `0`/unset = disabled).
  - `AEROSYNTHX_RATE_WINDOW_SECONDS` (default `60`).
  - `AEROSYNTHX_MAX_BODY_BYTES` (default `1048576` = 1 MiB; `0` = disabled).

### Wiring
- `create_app(..., rate_limit=None, rate_window_seconds=None,
  max_body_bytes=None)` — `None` means "read from env".
- CLI `serve` gains `--rate-limit`, `--rate-window-seconds`,
  `--max-body-bytes` (all optional; default to env/None).
- Middleware order: `ObservabilityMiddleware` stays outermost so 429/413
  responses still receive a correlation id and are counted.

## Out of scope (future phases)
- DB-backed named keys, key rotation, audit log (P2).
- Distributed/shared rate limiting (Redis) — in-process only here.
- CORS allow-list, secret redaction (separate P2 items).

## Acceptance
- 100% line + branch coverage maintained; `ruff`, `mypy`, `pytest` green.
- Existing auth tests unchanged in behaviour (all-scope keys).
- New tests: scope parsing + 403 path; token-bucket allow/deny/refill;
  principal resolution; 429 and 413 via the app; env parsing.
- Ship as `v1.4.0` with CHANGELOG + ROADMAP updates.
