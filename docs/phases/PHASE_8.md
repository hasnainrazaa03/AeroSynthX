# Phase 8 — LLM Provider Adapters (`v1.1.0`)

## Goal

Make the long-promised "natural-language prose → validated `DesignIntent`"
path real by adding **opt-in** LLM provider adapters behind the existing
`LLMClient` protocol, while keeping the deterministic offline parser as
the default. No network calls happen unless the user explicitly opts in.

## In scope

1. `aerosynthx.intent.providers` package (zero new runtime deps):
   - `ProviderConfig` dataclass (provider, model, base_url, api_key,
     timeout, max_retries).
   - `OpenAICompatibleClient` implementing `LLMClient` — talks to any
     OpenAI Chat-Completions-compatible endpoint (OpenAI, Azure,
     Ollama, vLLM, LM Studio) using stdlib `urllib.request`. An
     injectable `transport` callable isolates the network boundary so
     the client is fully unit-testable offline.
   - `build_client_from_env(env=None)` factory: returns a configured
     `LLMClient` when `AEROSYNTHX_LLM_PROVIDER` is set, else `None`.
   - `ProviderError` for transport/decoding failures (subclass of
     `IntentError`).
2. Pipeline integration: `Pipeline(..., llm_client=None)`. When a client
   is supplied, the parse stage tries the LLM first and **falls back to
   the offline parser** on any `IntentError`, recording which mode won.
3. CLI: `aerosynthx run --use-llm`. Builds a client from the environment;
   if none is configured, prints a clear message and uses offline mode.
4. API: `POST /api/v1/runs` accepts an optional `use_llm` flag; the app
   is built with an optional `llm_client` factory.
5. Metrics: `aerosynthx_intent_parse_total{mode,status}` counter
   (mode ∈ {llm, offline, fallback}).

## Out of scope (future)

- Streaming / token-by-token responses.
- Function-calling / tool-use beyond JSON mode.
- Provider-specific auth flows (OAuth, AWS SigV4); only bearer-token /
  api-key header auth is supported.
- Caching of LLM responses.

## Public surface

```python
from aerosynthx.intent.providers import (
    ProviderConfig,
    ProviderError,
    OpenAICompatibleClient,
    build_client_from_env,
)
```

## Environment variables

| Variable                      | Meaning                                   |
| ----------------------------- | ----------------------------------------- |
| `AEROSYNTHX_LLM_PROVIDER`     | `openai` (only value today). Unset = off. |
| `AEROSYNTHX_LLM_MODEL`        | Model id (default `gpt-4o-mini`).         |
| `AEROSYNTHX_LLM_BASE_URL`     | Endpoint base (default OpenAI public).    |
| `AEROSYNTHX_LLM_API_KEY`      | Bearer token; omitted for local servers.  |
| `AEROSYNTHX_LLM_TIMEOUT`      | Per-request timeout seconds (default 30). |

## Definition of done

- 100% line + branch coverage on new code (network mocked via transport).
- `ruff check`, `ruff format --check`, `mypy`, full `pytest` green.
- Version bumped to `1.1.0`, CHANGELOG updated, tagged `v1.1.0`, pushed.
