# AeroSynthX — Roadmap

Status: Draft v0.1.
This roadmap defines phases, milestones, acceptance criteria, and the
dependencies between them. It is the source of truth for sequencing.

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
| 0 | Repository bootstrap & governance | In progress |
| 1 | Architecture spec + deterministic physics core | Planned |
| 2 | Geometry engine (NACA 4-digit) + visualization | Planned |
| 3 | Intent parsing (LLM → validated schema) | Planned |
| 4 | OpenFOAM case-file generation (templated) | Planned |
| 5 | Workflow orchestrator + persistence + run history | Planned |
| 6 | HTTP API + Web UI | Planned |
| 7 | Hardening: observability, packaging, deployment | Planned |
| 8+ | Extensions: NACA 5-digit, additional turbulence models, optional solver execution worker, agentic orchestration | Future |

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
