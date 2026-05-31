# Phase 9 — API-Key Authentication (`v1.2.0`)

## Goal

Add **opt-in** API-key authentication to the HTTP API so deployments can
gate the data-plane endpoints. Keys are hashed at rest (SHA-256) and
compared in constant time. When no keys are configured the API runs in
*open* mode — fully backward compatible with every existing client and
test — emitting a one-time warning so the operator knows auth is off.

This closes the long-standing **P1 "Authentication / API keys"** item
carried from Phases 6 and 7.

## In scope

1. `aerosynthx.api.security` module (zero new runtime deps):
   - `ApiKeyStore` — immutable set of accepted keys stored as SHA-256
     hashes. Built from raw keys (`from_keys`) or the environment
     (`from_env`). `enabled` is `True` only when ≥1 key is configured.
   - Constant-time verification via `hmac.compare_digest`; plaintext
     keys are never retained.
   - `make_api_key_dependency(store)` — a FastAPI dependency that reads
     `X-API-Key` (or `Authorization: Bearer <key>`), returning `401`
     with `WWW-Authenticate: Bearer` on missing/invalid keys, and a
     no-op when the store is disabled.
2. `create_app(*, out_root, llm_client=None, api_keys=None)`: when
   `api_keys` is omitted the store is built from the environment. The
   dependency guards the data-plane routes (`POST /api/v1/runs`,
   `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, file listing/download).
   Liveness (`/healthz`), scrape (`/metrics`), `/api/v1/version`, and the
   static UI stay open.
3. CLI: `aerosynthx serve` reads keys from `AEROSYNTHX_API_KEYS` (via the
   factory default), so no new flags are required.
4. Metrics: `aerosynthx_auth_attempts_total{result}` counter
   (result ∈ {ok, missing, invalid, disabled}).

## Out of scope (future)

- User accounts, login, sessions, or JWT.
- RBAC / per-key scopes / permissions.
- Key rotation tooling or DB-backed key persistence.
- OAuth / OIDC / mTLS.

## Public surface

```python
from aerosynthx.api import ApiKeyStore, create_app

app = create_app(out_root=Path("work"), api_keys=["s3cret-key"])
```

## Environment variables

| Variable               | Meaning                                            |
| ---------------------- | -------------------------------------------------- |
| `AEROSYNTHX_API_KEYS`  | Comma-separated accepted keys. Unset = auth off.   |

## Definition of done

- 100% line + branch coverage on new code.
- `ruff check`, `ruff format --check`, `mypy`, full `pytest` green.
- Version bumped to `1.2.0`, CHANGELOG updated, tagged `v1.2.0`, pushed.
