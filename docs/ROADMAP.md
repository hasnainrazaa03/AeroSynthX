# AeroSynthX — Roadmap

Status: Living document (current release `v1.13.0`).
This roadmap defines phases, milestones, acceptance criteria, and the
dependencies between them. It is the source of truth for sequencing.
For the post-v1.2.0 feature backlog, see
[Forward Backlog & Improvement Checklist](#forward-backlog--improvement-checklist-post-v120).

Every phase ends with: (a) passing tests, (b) updated docs, (c) a tagged
release, (d) an updated `CHANGELOG.md`.

---

## Guiding Principles

1. **Deterministic core before LLM.** Physics, geometry, and templating
   must be correct, tested, and stable before any LLM layer is added.
2. **Narrow vertical slice first.** Get one end-to-end happy path through
   the system before broadening capability.
3. **Refuse out-of-envelope requests** rather than producing plausible-but-
   wrong outputs.
4. **Every phase is independently shippable.** No phase leaves the system
   in a half-working state on `main`.
5. **Docs are part of "done".** A phase is not complete until its docs are
   updated.

---

## Phase Map

| Phase | Theme | Status |
|---|---|---|
| 0 | Repository bootstrap & governance | Shipped (`v0.0.1`) |
| 1 | Architecture spec + deterministic physics core | Shipped (`v0.1.0`) |
| 2 | Geometry engine (NACA 4-digit) + visualization | Shipped (`v0.2.0`) |
| 3 | Intent parsing (LLM → validated schema) | Shipped (`v0.3.0`) |
| 4 | OpenFOAM case-file generation (templated) | Shipped (`v0.4.0`) |
| 5 | Workflow orchestrator + persistence + run history | Shipped (`v0.5.0`) |
| 6 | HTTP API + Web UI | Shipped (`v0.6.0`) |
| 7 | Hardening: observability, packaging, deployment | Shipped (`v1.0.0`) |
| 8 | LLM provider adapters + offline fallback | Shipped (`v1.1.0`) |
| 9 | API-key authentication | Shipped (`v1.2.0`) |
| 10 | OpenFOAM solver execution + result extraction | Shipped (`v1.3.0`) |
| 11 | RBAC scopes + rate limiting + body-size limits | Shipped (`v1.4.0`) |
| 12 | LLM retry with exponential backoff | Shipped (`v1.5.0`) |
| 13 | Run cancellation + timeout enforcement | Shipped (`v1.6.0`) |
| 14 | Run deletion + retention (`DELETE /runs/{id}`) | Shipped (`v1.7.0`) |
| 15 | Concurrency: per-run locking for safe parallel runs | Shipped (`v1.8.0`) |
| 16 | SSE streaming of run stage timeline (`/runs/{id}/events`) | Shipped (`v1.9.0`) |
| 17 | Live pipeline progress events (`on_event`, `run --progress`) | Shipped (`v1.10.0`) |
| 18 | Content-addressed artifact store (de-dup case files) | Shipped (`v1.11.0`) |
| 19 | Automatic retention & cleanup (prune runs + blob GC) | Shipped (`v1.12.0`) |
| 20 | Run-list pagination, filtering & full-text search | Shipped (`v1.13.0`) |
| 20+ | See [Forward Backlog](#forward-backlog--improvement-checklist-post-v120) | Planned |

Each phase has a dedicated checklist file under `docs/phases/`.

---

## Phase 0 — Repository Bootstrap & Governance

Goal: Establish a clean, opinionated repo with no business logic, ready for
phased development.

Acceptance criteria:
- Repository structure laid out with `docs/`, `src/` (empty placeholder),
  `tests/` (empty placeholder), `.github/`.
- Tooling configured: formatter, linter, type checker, test runner,
  pre-commit hooks (configured but not yet enforcing on empty code).
- CI workflow that runs lint + tests on push / PR.
- Governance docs: `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `LICENSE`,
  `SECURITY`, issue & PR templates.
- Versioning + branching strategy documented.
- `CHANGELOG.md` initialized.
- Initial git commit on `main`, tagged `v0.0.1`.

Out of scope: any engineering code, any LLM integration, any OpenFOAM
work.

See: [docs/phases/PHASE_0.md](phases/PHASE_0.md).

---

## Phase 1 — Architecture Spec + Physics Core

Goal: Lock the architecture document and ship a tested deterministic
physics engine.

Deliverables:
- `docs/ARCHITECTURE.md` finalized: module boundaries, data contracts,
  internal SI canonicalization, error model.
- `aerosynthx.physics` package:
  - ISA atmosphere model.
  - Unit normalization layer (built on `pint`).
  - Reynolds number, Mach number, dynamic pressure.
  - Input validation (impossible/contradictory inputs raise typed errors).
- ≥ 90% line coverage on `aerosynthx.physics`.
- Reference tests against published ISA values.

Acceptance criteria:
- All physics functions are pure, typed, and SI-internal.
- `pytest -q` green; coverage threshold enforced in CI.
- No dependency on LLM, OpenFOAM, or networking.
- Tagged `v0.1.0`.

---

## Phase 2 — Geometry Engine

Goal: Deterministic airfoil geometry generation with validation and
visualization.

Deliverables:
- `aerosynthx.geometry`:
  - NACA 4-digit profile generator (mean line + thickness, cosine
    spacing, closed trailing edge option).
  - Coordinate validators (closure, monotonicity, min thickness).
  - Exporters: `.dat` (Selig format), `.csv`.
  - Visualization renderer (PNG/SVG).
- Golden-file tests against reference NACA coordinates.

Acceptance criteria:
- Generated coordinates match reference within a documented tolerance.
- Exporters round-trip cleanly.
- Tagged `v0.2.0`.

---

## Phase 3 — Intent Parsing Layer

Goal: Convert natural-language input into a validated `DesignIntent`
schema, with explicit assumptions and provenance.

Deliverables:
- `aerosynthx.intent`:
  - Pydantic schemas: `DesignIntent`, `Assumption`, `ParseResult`.
  - LLM client abstraction (provider-agnostic interface; no provider
    hardcoded in core).
  - Structured-output parser with schema validation and retry-on-invalid.
  - Provenance tagging: every field marked `user_provided` or `inferred`.
  - Offline deterministic fallback parser for tests (no network).
- Strict rule: LLM never emits engineering values that bypass the physics
  engine. It produces *intent fields*; physics is computed downstream.

Acceptance criteria:
- Schema-validated outputs only; invalid outputs are retried, then fail
  loudly.
- Deterministic offline tests do not call any network.
- Tagged `v0.3.0`.

---

## Phase 4 — OpenFOAM Case Generation

Goal: From a validated `DesignIntent` + geometry, emit an OpenFOAM case
directory.

Deliverables:
- `aerosynthx.openfoam`:
  - Jinja2-based template set targeting one pinned OpenFOAM version.
  - Initial template: 2D incompressible RANS (`simpleFoam`,
    `kOmegaSST`), blockMesh-based domain around the airfoil.
  - Patch naming, BCs, fvSchemes, fvSolution, controlDict.
  - Envelope guard: refuse out-of-envelope requests with a typed error.
  - Case packaging: tar/zip with manifest.
- Smoke test: generated case passes `foamDictionary` parsing (if
  OpenFOAM available in CI) or a structural validator otherwise.

Acceptance criteria:
- Generated case is structurally valid and human-reviewable.
- Envelope violations are rejected with clear messages.
- Tagged `v0.4.0`.

---

## Phase 5 — Workflow Orchestrator + Persistence

Goal: Tie phases 1–4 into a re-runnable, traceable pipeline with stored
history.

Deliverables:
- `aerosynthx.workflow`:
  - Staged pipeline: `parse → validate → compute → geometry → case →
    package → persist`.
  - Per-stage logging, structured events, stage-level reruns.
  - Run manifest with content hashes + library versions.
- Persistence:
  - SQLite-backed run/project store via SQLAlchemy.
  - Filesystem-backed artifact store with content-addressed paths.
- CLI entrypoint: `aerosynthx run --intent "<text>" --out <dir>`.

Acceptance criteria:
- Same intent → identical artifact hashes (modulo timestamped metadata).
- Failed stages are recoverable without re-running upstream successful
  stages.
- Tagged `v0.5.0`.

---

## Phase 6 — HTTP API + Web UI

Goal: Engineering-grade UI over the orchestrator.

Deliverables:
- FastAPI service exposing project + run endpoints.
- Web UI (framework chosen in Phase 1 architecture doc):
  - Intent input.
  - Parsed-parameter inspector with provenance badges.
  - Geometry viewer.
  - File tree of generated case.
  - Run history.
  - Artifact downloads.

Acceptance criteria:
- API documented via OpenAPI.
- UI is usable end-to-end against a local backend.
- Tagged `v0.6.0`.

---

## Phase 7 — Hardening

Goal: Production-readiness.

Deliverables:
- Structured logging (JSON), correlation IDs per run.
- Metrics endpoint (Prometheus-style).
- Containerization (Docker), reproducible builds.
- Release automation (tag → built artifacts).
- Security review pass (dependency scanning, secret scanning, SAST).
- Performance budget for the parse → package path.

Acceptance criteria:
- One-command local bring-up.
- CI publishes signed container images on tag.
- Tagged `v1.0.0`.

---

## Phase 8+ — Extensions (Backlog)

- Additional airfoil families (NACA 5-digit, supercritical references).
- Additional turbulence models and solvers.
- Optional opt-in solver execution worker (containerized OpenFOAM).
- Post-processing: Cp distributions, polars.
- Agentic orchestration layer over the deterministic core.
- Multi-user, RBAC, project sharing.

Items move from backlog to a numbered phase only after explicit planning.

---

## Dependency Graph

```
Phase 0 ─▶ Phase 1 ─▶ Phase 2 ─▶ Phase 4 ─▶ Phase 5 ─▶ Phase 6 ─▶ Phase 7
                 │                 ▲
                 └─▶ Phase 3 ──────┘
```

Phase 3 (intent) depends on Phase 1 (physics contracts) but is independent
of Phase 2 (geometry). Phase 4 depends on both.

---

## Forward Backlog & Improvement Checklist (post-v1.2.0)

A living, prioritised list of features and improvements discovered by
reviewing the codebase as of `v1.2.0`. Tick items as they ship and link
them to a `docs/phases/PHASE_N.md` when picked up.

**Priority key** — **P1** next-up / high value · **P2** opportunistic ·
**P3** long-horizon.

### Security & multi-tenancy

- [x] **P1** Per-key scopes / roles (RBAC): read-only vs. run-create keys
      (Phase 11, `v1.4.0`).
- [x] **P1** Rate limiting + request body-size limits per key/IP
      (Phase 11, `v1.4.0`).
- [ ] **P2** Named keys + audit log (who created which run).
- [ ] **P2** Key rotation: DB-backed key store with `created/expires`.
- [ ] **P2** CORS allow-list configuration for browser clients.
- [ ] **P2** Secret redaction filter for logs (API keys, LLM tokens).
- [ ] **P3** Multi-tenant run isolation (per-user output directories).
- [ ] **P3** OAuth2 / OIDC / mTLS for enterprise deployments.

### LLM intent parsing

- [x] **P1** Retry with exponential backoff on transient provider errors
      (Phase 12, `v1.5.0`).
- [ ] **P2** Response caching keyed by prompt hash.
- [ ] **P2** Token / cost metrics (`aerosynthx_llm_tokens_total`).
- [ ] **P2** Additional providers (Anthropic Messages API adapter).
- [ ] **P2** Strict JSON-schema validation of LLM output before accept.
- [ ] **P3** SSE token streaming surfaced through the API.
- [ ] **P3** Prompt versioning + golden-output regression tests.

### Physics

- [ ] **P2** NACA 5-digit camber line in the aero model.
- [ ] **P2** Moist-air (humidity) corrections to density & viscosity.
- [ ] **P2** Compressibility / real-gas corrections beyond ideal gas.
- [ ] **P2** Reynolds-dependent drag polars (replace flat estimates).
- [ ] **P3** Altitudes above 20 km (mesosphere atmosphere model).
- [ ] **P3** Transonic / supersonic regimes (shock-aware Cd).
- [ ] **P3** Panel-method / XFOIL integration for higher-fidelity Cl/Cd.

### Geometry

- [ ] **P2** NACA 5-digit airfoil family generator.
- [ ] **P2** 3D wing builder (taper, sweep, dihedral, twist).
- [ ] **P3** STL / STEP export of generated surfaces.
- [ ] **P3** Geometry upload endpoint (user-supplied airfoils).

### OpenFOAM execution

- [x] **P1** Actually run solvers (`blockMesh` → `simpleFoam`) when the
      toolchain is present (Phase 10, `v1.3.0`); opt-in via
      `run --execute` / API `execute`. Case generation remains the default.
- [ ] **P2** Mesh generation controls (`snappyHexMesh`, refinement).
- [x] **P2** Residual parsing + convergence detection (Phase 10, `v1.3.0`).
- [x] **P2** Force-coefficient (Cl/Cd/Cm) extraction post-solve
      (Phase 10, `v1.3.0`).
- [ ] **P2** Turbulence-model selection (kOmegaSST, Spalart–Allmaras).
- [ ] **P3** ParaView / VTK export and screenshot generation.

### Workflow & data

- [x] **P1** Concurrency: parallel runs + per-run locking (Phase 15,
  `v1.8.0`; process-local per-`run_id` locking — cross-process locking
  remains future work).
- [x] **P1** Run cancellation + timeout enforcement (Phase 13, `v1.6.0`).
- [x] **P2** Run deletion + artifact retention / cleanup policy (Phase 14,
  `v1.7.0`, basic per-run deletion; Phase 19, `v1.12.0`, automatic
  age/count pruning + unreferenced-blob garbage collection).
- [x] **P2** Content-addressed artifact store de-duplicating case files
  across runs (Phase 18, `v1.11.0`; shared SHA-256 blob store under
  `<out_root>/blobs` with a `GET /store/stats` endpoint — relinking run
  directories to blobs remains future work).
- [ ] **P2** Postgres backend option (SQLite stays the default).
- [ ] **P2** Alembic migrations for schema evolution.
- [ ] **P2** Completion webhooks / callbacks.
- [ ] **P3** Run comparison / diff view (A vs. B intents).
- [ ] **P3** Pluggable stage architecture (custom pipeline stages).

### API & UI

- [x] **P1** SSE / WebSocket streaming of stage progress (Phase 16,
  `v1.9.0`; SSE replay of the persisted stage timeline). Live
  mid-execution progress events landed in Phase 17, `v1.10.0` (the
  `on_event` sink and `run --progress`).
- [x] **P2** Run list pagination, filtering, and full-text search (Phase 20,
  `v1.13.0`; `offset`/`status`/`q` query params + `X-Total-Count` header,
  UI search box and Prev/Next paging).
- [x] **P2** `DELETE /api/v1/runs/{id}` endpoint (Phase 14, `v1.7.0`).
- [ ] **P2** Charts of physics results + downloadable report in the UI.
- [ ] **P2** Generated typed client (OpenAPI → TS/Python SDK).
- [ ] **P3** SPA upgrade (React/Vue) once the vanilla bundle outgrows.
- [ ] **P3** Dark mode + accessibility audit.

### Observability & ops

- [ ] **P2** OpenTelemetry tracing (spans per stage + HTTP).
- [ ] **P2** Ship Grafana dashboards + Prometheus alert rules.
- [ ] **P2** Container signing (cosign) + SBOM (CycloneDX / Syft).
- [ ] **P2** Helm chart / k8s manifests + `docker-compose.yml`.
- [ ] **P3** Sentry (or similar) error reporting integration.
- [ ] **P3** Nightly CI: perf-regression gate + dependency scanning.

### Developer experience

- [ ] **P2** Config-file support (`aerosynthx.toml`) + startup env
      validation with clear error messages.
- [ ] **P2** Shell completions for the CLI.
- [ ] **P3** Examples gallery / tutorial notebooks.

### Suggested next phase

**Phase 20 — run-list pagination, filtering & full-text search** shipped in
`v1.13.0`: `query_runs` powers `offset`/`status`/`q` on `GET /api/v1/runs`
with `X-Total-Count` headers and a searchable, paged UI. The strongest
remaining candidate is **relinking run directories to blobs** (serve files
straight from the content-addressed store via hard-links/symlinks so on-disk
run trees shrink, under *Workflow & data*). Other high-value options are
**charts of physics results + a downloadable report in the UI** and
**OpenTelemetry tracing** (spans per stage + HTTP, under *Observability*).
