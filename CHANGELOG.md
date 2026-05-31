# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See [docs/VERSIONING.md](docs/VERSIONING.md) for the project's release
policy.

## [Unreleased]

### Added
- (nothing yet)

## [1.6.0] - 2026-05-31

### Added
- Phase 13: run cancellation + timeout enforcement, with zero new runtime
  dependencies. The synchronous pipeline now enforces a wall-clock budget
  and a cooperative cancellation hook checked at every stage boundary.
  - New `aerosynthx.workflow.cancellation` module: `CancellationToken`
    (thread-safe one-shot flag), `Deadline` (monotonic budget built from
    an injectable clock), and `RunControl` (combined deadline + token with
    `check()` and a budget-capped `solver_timeout()`).
  - New `RunTimeoutError` (`code="workflow.run.timeout"`) and
    `RunCancelledError` (`code="workflow.run.cancelled"`); on either, the
    in-flight stage fails fast and the run finalises as `failed`.
  - `Pipeline` accepts an injectable `clock`; `Pipeline.run` gains
    `timeout` and `cancel_token` parameters. The opt-in solver stage caps
    its per-command subprocess timeout to the run's remaining budget.
  - `POST /api/v1/runs` accepts an optional `timeout_seconds` (> 0); the
    CLI `run` command gains `--timeout SECONDS`.
  - New `aerosynthx_runs_interrupted_total{reason}` counter
    (`reason ∈ {timeout, cancelled}`).

## [1.5.0] - 2026-05-31

### Added
- Phase 12: automatic retry with exponential backoff for transient LLM
  provider failures (`aerosynthx.intent.providers.openai`), with zero new
  runtime dependencies.
  - New `TransientProviderError` (`code="intent.provider.transient"`)
    classifies retryable failures — HTTP `408/425/429/500/502/503/504`
    and connection errors — carrying `status_code` and a parsed
    `Retry-After` when present.
  - `RetryPolicy` (frozen dataclass) controls `max_attempts`,
    `base_delay`, `max_delay`, `multiplier`, and `jitter`; its `sleep`
    and `rng` callables are injectable so backoff is deterministic in
    tests. `OpenAICompatibleClient` retries transient transport failures
    transparently and re-raises permanent errors immediately.
  - New `aerosynthx_llm_retries_total{outcome}` counter
    (`outcome ∈ {retry, exhausted}`).
  - `build_client_from_env` reads `AEROSYNTHX_LLM_RETRIES` (default 3),
    `AEROSYNTHX_LLM_RETRY_BASE_SECONDS` (default 0.5), and
    `AEROSYNTHX_LLM_RETRY_MAX_SECONDS` (default 8.0); non-numeric values
    raise `ProviderError` (`code="intent.provider.bad_retry"`).

## [1.4.0] - 2026-05-31

### Added
- Phase 11: per-key RBAC scopes plus in-process rate limiting and request
  body-size limits, with zero new runtime dependencies.
  - `Scope` (`read`, `run`) is now attached to each API key. The
    `AEROSYNTHX_API_KEYS` syntax accepts scoped entries
    (`admin:read|run, reader:read, runner:run`); bare keys keep all scopes
    for backward compatibility. `POST /api/v1/runs` requires the `run`
    scope and the read endpoints require `read`; insufficient scope now
    returns `403` with `result="forbidden"` recorded on
    `aerosynthx_auth_attempts_total`.
  - New `aerosynthx.api.ratelimit` module adds a thread-safe token-bucket
    `RateLimiter` (injectable clock) and a `RateLimitMiddleware` that
    guards only the `/api/v1/` data plane. Over-rate requests get `429`
    with a `Retry-After` header; oversized bodies get `413`. Rejections
    are counted on `aerosynthx_rate_limited_total{reason}`
    (`rate_limited`, `body_too_large`). The principal is the presented API
    key, else the client IP.
  - `create_app()` gained `rate_limit`, `rate_window_seconds`, and
    `max_body_bytes` parameters (each falls back to
    `AEROSYNTHX_RATE_LIMIT` / `AEROSYNTHX_RATE_WINDOW_SECONDS` /
    `AEROSYNTHX_MAX_BODY_BYTES`; default body limit 1 MiB, rate limiting
    off unless configured). The `serve` CLI exposes matching
    `--rate-limit`, `--rate-window-seconds`, and `--max-body-bytes` flags.

## [1.3.0] - 2026-05-31

### Added
- Phase 10: opt-in OpenFOAM solver execution and result extraction
  (`aerosynthx.openfoam.runner`), zero new runtime dependencies.
  - `run_case()` runs `blockMesh` then `simpleFoam` in a generated case,
    writing `log.<app>` files and returning a `SolveResult` (ran,
    converged, iterations, final residual, force coefficients, commands).
  - The process boundary is isolated behind an injectable `CommandRunner`
    protocol (`default_command_runner` for real subprocess execution), so
    the residual/coefficient parsers and the run harness are fully
    unit-testable offline.
  - `openfoam_available()` gates execution on `WM_PROJECT_DIR` plus the
    solver applications resolving on `PATH`.
  - `parse_residuals()` and `parse_force_coefficients()` extract
    convergence and Cl/Cd/Cm data from solver logs and coefficient tables.
- Pipeline `solve` stage (opt-in via `Pipeline.run(..., execute=True)` and
  the `command_runner` constructor argument). When OpenFOAM is absent the
  stage is recorded as `skipped` and the run still completes; a solver
  failure marks the run `failed`. Execution always runs fresh, bypassing
  the resume cache, and writes a `solve.json` artifact plus a `solve`
  block in `run.json`.
- `aerosynthx run --execute` CLI flag and `execute` field on the
  `POST /api/v1/runs` request body.
- `aerosynthx_solver_runs_total{status}` metric
  (status ∈ {ok, skipped, failed}).

## [1.2.0] - 2026-05-31

### Added
- Phase 9: opt-in API-key authentication for the HTTP API
  (`aerosynthx.api.security`), zero new runtime dependencies.
  - `ApiKeyStore` holds accepted keys as SHA-256 hashes and verifies in
    constant time (`hmac.compare_digest`); plaintext keys are never
    retained. Built from raw keys or `AEROSYNTHX_API_KEYS`.
  - Data-plane routes (`POST/GET /api/v1/runs`, run detail, file
    listing/download) require `X-API-Key` or `Authorization: Bearer`;
    `/healthz`, `/metrics`, `/api/v1/version`, and the UI stay open.
  - When no keys are configured the API stays in open mode (backward
    compatible).
- `create_app(..., api_keys=...)` and `AEROSYNTHX_API_KEYS` env support
  (read automatically by `aerosynthx serve`).
- `aerosynthx_auth_attempts_total{result}` metric
  (result ∈ {ok, missing, invalid, disabled}).
- `docs/ROADMAP.md`: a living, prioritised feature/improvement checklist.

## [1.1.0] - 2026-05-31

### Added
- Phase 8: opt-in LLM provider adapters (`aerosynthx.intent.providers`),
  zero new runtime dependencies.
  - `OpenAICompatibleClient` speaks the OpenAI `/chat/completions` shape
    (OpenAI, Azure, Ollama, vLLM, LM Studio) over stdlib `urllib`, with
    an injectable `transport` seam for offline testing.
  - `ProviderConfig`, `ProviderError`, and `build_client_from_env()`
    reading `AEROSYNTHX_LLM_*` environment variables (returns `None`
    when unset so the default stays fully offline).
- `Pipeline(..., llm_client=...)`: when configured, the parse stage uses
  the LLM first and transparently falls back to the deterministic
  offline parser on any failure.
- `aerosynthx run --use-llm` CLI flag and an optional `use_llm` field on
  `POST /api/v1/runs`; `create_app(..., llm_client=...)` enables it.
- `aerosynthx_intent_parse_total{mode,status}` metric
  (mode ∈ {offline, llm, fallback}).

### Fixed
- Record `aerosynthx_intent_parse_total{mode="fallback",status="error"}`
  when both the LLM and offline parsers fail (previously unrecorded).
- Guard `_Registry` counter/histogram registration and `reset()` with a
  lock to avoid duplicate metric instances under concurrent first-use.

## [1.0.0] - 2026-05-25

### Added
- Phase 7: HTTP hardening, operability, and release automation.
- `aerosynthx.observability` (zero external dependencies):
  - Structured JSON logging with a `correlation_id` `ContextVar` and an
    idempotent `configure_logging()` initialiser.
  - `bind_correlation_id(...)` context manager.
  - Minimal Prometheus-compatible `Counter` / `Histogram` types and a
    module-level `METRICS` registry plus `render_prometheus()`.
- API: `ObservabilityMiddleware` honours / mints `X-Correlation-Id` on
  every request, exposes `aerosynthx_http_requests_total` and
  `aerosynthx_http_request_duration_seconds`, and serves them at
  `GET /metrics` in Prometheus text format.
- Pipeline: each run is wrapped in `bind_correlation_id(run_id)`, stage
  durations land in `aerosynthx_pipeline_stage_duration_seconds`, and
  final outcomes increment `aerosynthx_pipeline_runs_total`.
- `Dockerfile` (multi-stage slim image, non-root user, healthcheck) and
  `.dockerignore`.
- `Makefile` with `install`, `lint`, `format`, `type`, `test`, `cov`,
  `serve`, `docker`, and `clean` targets.
- `.github/workflows/release.yml` builds wheel + sdist on `v*.*.*` tags
  and uploads them to the corresponding GitHub Release.
- `.github/workflows/security.yml` runs `pip-audit` and `bandit -r src`
  on every push, PR, and weekly schedule (advisory, non-blocking).
- `tests/perf/test_budget.py` enforces a 2.0 s wall-time budget on the
  offline parse-to-case path.

## [0.6.0] - 2026-05-25

### Added
- Phase 6: HTTP API + minimal web UI (`aerosynthx.api`).
- FastAPI app factory `create_app(*, out_root)` exposing:
  - `GET /healthz`, `GET /api/v1/version`
  - `POST /api/v1/runs` (executes the Phase 5 pipeline)
  - `GET /api/v1/runs` (history, newest first)
  - `GET /api/v1/runs/{run_id}` (full run payload)
  - `GET /api/v1/runs/{run_id}/files` and
    `GET /api/v1/runs/{run_id}/files/{path}` (case file browser /
    download) with a path-traversal guard.
  - `GET /` serving a bundled vanilla-JS browser UI for intent input,
    run history, and case file browsing.
- `aerosynthx serve --out <dir> [--host] [--port]` CLI subcommand
  that boots Uvicorn against the FastAPI app.
- Runtime deps: `fastapi>=0.110`, `uvicorn>=0.27`.
- Dev deps: `httpx>=0.27` (for `fastapi.testclient.TestClient`).

## [0.5.0] - 2026-05-25

### Added
- Phase 5: end-to-end workflow orchestrator (`aerosynthx.workflow`).
- `Pipeline` class: staged execution (parse → compute → geometry
  → case → persist) with per-stage timing, SHA-256 output digests,
  and resumable reruns keyed by a SHA-256 hash of the normalised
  intent text.
- SQLite-backed run store via SQLAlchemy 2.0 (`RunRow`, `StageRow`,
  `init_db`, `open_session`, `load_run`) for durable run history.
- `aerosynthx` console entry point (stdlib `argparse`) exposing
  `aerosynthx run --intent ... --out ...` and
  `aerosynthx show <run_id> --out ...` with JSON output.
- Per-run output directory `<out>/runs/<run_id>/` containing the
  generated OpenFOAM `case/` and a `run.json` snapshot of the
  `RunResult` for offline inspection.
- Workflow error hierarchy: `WorkflowError`, `StageError` (with
  `stage` attribute), `RunNotFoundError`.

## [0.4.0] - 2026-05-25

### Added
- Phase 4: OpenFOAM case generation layer (`aerosynthx.openfoam`).
- `derive_flow_state(intent)`: deterministic mapping from
  `DesignIntent` + US Std Atm 1976 to concrete SI flow quantities
  (velocity vector, Mach, density, kinematic viscosity, Reynolds,
  k-omega turbulence initial conditions).
- `build_case(intent, output_dir, *, overwrite=False)`: renders the
  bundled `incompressible_simple_komegaSST` Jinja2 template set into
  a complete case directory with `0/`, `constant/`, `system/`,
  `Allrun`, `Allclean`, and a reproducibility manifest with SHA-256
  digests of every emitted file.
- Airfoil geometry exported to `constant/triSurface/airfoil.dat` for
  downstream meshers.
- `validate_case_structure(case_dir)`: static structural checks
  (required files, balanced braces, required keys per dictionary)
  that never execute OpenFOAM.
- Envelope guard re-validates intent at the OpenFOAM boundary
  (defence in depth).
- Typed errors: `OpenFoamError`, `EnvelopeViolationError`,
  `CaseExistsError`, `TemplateRenderError`.
- Runtime dependency: `jinja2>=3.1`.
- 30 new tests; 201 total at 100% line + branch coverage.

## [0.3.0] - 2026-05-25

### Added
- Phase 3: natural-language intent parsing layer.
- `aerosynthx.intent.errors`: `IntentError` rooted under
  `AeroSynthXError` with stable codes
  (`intent.error`, `intent.schema.invalid`,
  `intent.envelope.violation`, `intent.llm.parse_failed`, etc.).
- `aerosynthx.intent.schemas`: Pydantic v2 models
  (`AirfoilSpec`, `FlowCondition`, `Assumption`,
  `ProvenanceMap`, `DesignIntent`, `ParseResult`) with
  envelope-enforcing validators (NACA 4-digit only, Mach < 0.3,
  |alpha| <= 20 deg, altitude 0-20000 m, exactly one of
  velocity/mach).
- `aerosynthx.intent.llm`: provider-agnostic `LLMClient` Protocol
  + deterministic `StaticLLMClient` for tests. No provider is
  hardcoded in the core.
- `aerosynthx.intent.parser`: `IntentParser` with bounded
  retry-on-validation-failure that feeds Pydantic errors back into
  the LLM prompt.
- `aerosynthx.intent.offline`: deterministic regex-based
  `parse_offline` for tests and zero-network fallback, with
  documented defaults captured as `Assumption` entries and full
  provenance tagging.
- Runtime dependency: `pydantic>=2.7`.
- 56 new tests; 171 total at 100% line and branch coverage.

## [0.2.0] - 2026-05-25

### Added
- Phase 2: deterministic geometry engine.
- `aerosynthx.geometry.errors`: `GeometryError` rooted under
  `AeroSynthXError` with stable `code` strings.
- `aerosynthx.geometry.airfoil`: immutable `Airfoil` dataclass
  (Selig ordering, normalized coordinates, frozen metadata).
- `aerosynthx.geometry.naca4`: NACA 4-digit generator with cosine
  spacing and optional closed trailing edge
  (closed-TE coefficient `-0.1036`).
- `aerosynthx.geometry.validators`: `validate_airfoil` checking
  length, finiteness, x-range with leading-edge wrap tolerance,
  upper/lower monotonicity, TE closure, and minimum thickness.
- `aerosynthx.geometry.exporters`: Selig `.dat` and CSV string
  exporters.
- `aerosynthx.geometry.visualize`: PNG and SVG rendering via
  Matplotlib's `Agg` backend (headless-safe, lazy import).
- Runtime dependency: `matplotlib>=3.8`.
- Mypy override: `ignore_missing_imports` for `matplotlib.*`.
- 52 new tests; 115 total at 100% line and branch coverage.

## [0.1.0] - 2026-05-25

### Added
- Phase 1: deterministic physics core.
- `docs/ARCHITECTURE.md` (v0.1): layered module map, canonical SI unit
  convention, error taxonomy, determinism rules, Phase 1 public surface.
- `aerosynthx.physics.errors`: typed exception hierarchy with stable
  `code` attribute on each subclass (`AeroSynthXError` ->
  `PhysicsError` -> `UnitError` / `DomainError` / `AtmosphereError`).
- `aerosynthx.physics.units`: boundary unit conversion via `pint`
  with explicit dimension labels and offset-unit support (e.g. degC).
- `aerosynthx.physics.atmosphere`: US Standard Atmosphere 1976 over
  0-20 km (troposphere + isothermal lower stratosphere) plus
  Sutherland's law for dynamic viscosity. Immutable `AtmosphereState`
  result.
- `aerosynthx.physics.aero`: pure aerodynamic primitives --
  `speed_of_sound`, `reynolds_number`, `mach_number`,
  `dynamic_pressure`.
- Runtime dependencies: `numpy`, `pint`.
- Coverage gate enforced: 90% line/branch (current: 100% on the
  physics core, 63 tests).

### Changed
- CI runs `pytest` with `--cov-branch` and `fail_under=90`.
- Test ignores broadened to allow physics-domain capital identifiers
  (T, P, R, L).

## [0.0.1] - 2026-05-25

### Added
- Initial repository bootstrap (Phase 0).
- Planning documentation: feasibility analysis, roadmap, risk register,
  engineering / documentation / GitHub workflow docs, versioning policy.
- Phase checklists for Phases 0–7.
- Python project scaffolding (`pyproject.toml`) with `ruff`, `mypy`,
  `pytest`. Empty `aerosynthx` package and smoke test.
- Governance files: `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT`,
  `SECURITY`, `LICENSE` (MIT).
- GitHub assets: CI workflow, issue templates, PR template,
  Dependabot config.
- Pre-commit hooks, `.gitignore`, `.gitattributes`, `.editorconfig`,
  `.env.example`.

[Unreleased]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.6.0...v1.0.0
[0.6.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/hasnainrazaa03/AeroSynthX/releases/tag/v0.0.1
