# Phase 12 — LLM retry with exponential backoff (v1.5.0)

## Goal

Harden the most failure-prone boundary in the system — the external LLM
provider call — by adding automatic **retry with exponential backoff** for
transient errors. Every API/CLI run that uses a configured provider passes
through this single network seam, so transient blips (HTTP 429/5xx, dropped
connections) should be ridden out transparently rather than failing a run.

Keeps the project discipline: **zero new runtime dependencies**, the I/O
boundary isolated behind injectable callables (`Transport`, plus injectable
`sleep`/`rng` so backoff is fully deterministic under test), and 100%
line + branch coverage.

This is the highest-leverage remaining **P1** under *LLM intent parsing*:
> Retry with exponential backoff on transient provider errors.

## In scope (`aerosynthx.intent.providers.openai`)

### Transient-error classification
- New `TransientProviderError(ProviderError)` (`code =
  "intent.provider.transient"`) carrying optional `status_code` and
  `retry_after` (seconds) for diagnostics.
- `_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}` and a pure
  `_is_retryable_status(status) -> bool` helper (directly unit-tested).
- `_urllib_transport` classifies `HTTPError` with a retryable status (and
  `URLError` connection failures) as `TransientProviderError`, honouring a
  `Retry-After` header when present. (The real-socket branch stays
  `# pragma: no cover`; classification logic is covered via the helper.)

### Retry policy
- `RetryPolicy` (frozen dataclass):
  - `max_attempts` (default 3, total tries including the first),
  - `base_delay` (0.5 s), `max_delay` (8.0 s), `multiplier` (2.0),
  - `jitter` (0.1 fractional), `sleep` (`time.sleep`), `rng`
    (`random.random`) — the last two injectable for determinism.
  - `delay_for(retry_index) -> float` = `min(base * multiplier**index,
    max_delay)` plus `jitter * capped * rng()`.
- `OpenAICompatibleClient` gains a `retry_policy: RetryPolicy | None`
  constructor arg (default `RetryPolicy()`). `complete_json` routes its
  transport call through `_call_with_retry`, which:
  - returns on success,
  - on `TransientProviderError` retries up to `max_attempts`, sleeping
    `delay_for(retry_index)` between tries,
  - re-raises once attempts are exhausted,
  - lets non-transient `ProviderError` propagate immediately (no retry).

### Metric
- `aerosynthx_llm_retries_total{outcome}` counter, `outcome ∈ {retry,
  exhausted}` (incremented on each retry and once on give-up).

### Configuration (`build_client_from_env`)
- `AEROSYNTHX_LLM_RETRIES` (int, default 3),
  `AEROSYNTHX_LLM_RETRY_BASE_SECONDS` (float, default 0.5),
  `AEROSYNTHX_LLM_RETRY_MAX_SECONDS` (float, default 8.0).
- Non-numeric values raise `ProviderError`
  (`code="intent.provider.bad_retry"`), matching the existing
  bad-timeout behaviour.

## Out of scope (future phases)
- Response caching keyed by prompt hash (separate P2).
- Token/cost metrics, additional providers, SSE streaming.
- Retry of schema-validation failures (already handled in the parser's
  feedback loop) — this phase only retries *transport-level* transients.

## Definition of done
- New module logic with injectable `sleep`/`rng`; deterministic tests for
  backoff growth, capping, jitter, retry-then-succeed, exhaustion, and
  no-retry-on-permanent-error.
- Env parsing covered (defaults, overrides, bad values).
- All gates green; 100% line + branch coverage maintained.
- Ship as `v1.5.0` (CHANGELOG + ROADMAP + tag), authored as hasnainrazaa03.
