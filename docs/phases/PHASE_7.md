# Phase 7 — Hardening

Target release: `v1.0.0`.
Status: In progress.

## Goal

Take AeroSynthX from "feature complete (Phases 1-6)" to "operable":
predictable observability, container packaging, automated releases,
and a measured performance budget on the hot path.

## In-scope deliverables

1. **Structured logging** (`aerosynthx.observability.logging`)
   - JSON line formatter.
   - `correlation_id` `ContextVar` automatically included in every record.
   - `configure_logging(*, json: bool, level: int)` entry point.
2. **Metrics** (`aerosynthx.observability.metrics`)
   - Zero-dependency in-process registry (`Counter`, `Histogram`).
   - Prometheus text-exposition formatter.
   - Wired into the API and the workflow pipeline.
3. **HTTP middleware** in `aerosynthx.api`
   - Honour incoming `X-Correlation-Id` or mint a UUID4.
   - Echo it back in response headers.
   - Record request count / latency histogram per method+route.
   - Expose `GET /metrics` (Prometheus text format).
4. **Pipeline integration**
   - Each `Pipeline.run` binds `correlation_id = run_id` for the
     duration of the call.
   - One `pipeline.stage.duration_ms` histogram, labelled by stage.
5. **Container image**
   - `Dockerfile` (multi-stage, slim, non-root) running
     `aerosynthx serve --out /var/lib/aerosynthx`.
   - `.dockerignore`.
6. **One-command bring-up**
   - `Makefile` targets: `install`, `lint`, `format`, `type`, `test`,
     `cov`, `serve`, `docker`, `clean`.
7. **Release automation**
   - `.github/workflows/release.yml`: on `v*.*.*` tag, build wheel +
     sdist via `python -m build` and attach to the GitHub release.
8. **Security scanning** in CI
   - `pip-audit` (advisory) + `bandit` (advisory) job, non-blocking.
9. **Performance budget test**
   - `tests/perf/test_budget.py` asserts the offline
     `parse → case` path completes in &lt; 1.5 s on the CI runner.

## Out of scope (explicit)

- Signed container images / SBOM attestations (future).
- Authentication, RBAC, multi-tenant (no user model planned).
- LLM provider plug-ins (Phase 8 candidate).
- WebSocket progress streaming (stages are sub-second offline).

## Public surface (additive)

```python
from aerosynthx.observability import (
    configure_logging, correlation_id_var, bind_correlation_id,
    Counter, Histogram, METRICS, render_prometheus,
)
```

## Done when

- [x] `aerosynthx.observability` package landed.
- [x] API middleware + `/metrics` endpoint.
- [x] Pipeline emits structured stage logs + histogram.
- [x] `Dockerfile` and `Makefile` present.
- [x] `release.yml` + `security.yml` workflows present.
- [x] Perf budget test green on dev machine.
- [x] All gates green (`ruff`, `ruff format --check`, `mypy`, `pytest` 100%).
- [x] Version bumped to `1.0.0`, tag pushed.
