# AeroSynthX — Feasibility Analysis

Status: Draft v0.1 — produced before implementation begins.
Owner: Platform Engineering.
Last updated: Phase 0 kickoff.

---

## 1. Purpose

This document evaluates whether AeroSynthX — an AI-assisted aerodynamic
design and CFD orchestration platform — can be built as a production-grade
system using the proposed scope. It identifies which components are
straightforward, which are non-trivial, and which carry meaningful technical
risk. It also bounds the *initial* feasible scope so that Phase 1 work is
realistic.

This is not a marketing document. It is an engineering reality check.

---

## 2. Problem Restatement

AeroSynthX must convert natural-language aerodynamic intent into:

1. A validated, structured aerodynamic specification.
2. Deterministic derived physics quantities (Re, Ma, etc.).
3. Deterministic airfoil geometry (initially NACA family).
4. OpenFOAM-ready case files (mesh + solver + BCs from templates).
5. A packaged, reproducible artifact set with full provenance.

The LLM is restricted to **interpretation and orchestration assistance**.
All engineering values must come from deterministic code paths that are
independently testable.

---

## 3. Component-Level Feasibility

| Component | Feasibility | Notes |
|---|---|---|
| Intent parsing (LLM → structured schema) | High | Solved pattern: JSON-schema / structured output + Pydantic validation. Risk is in *hallucinated numerics*, mitigated by forbidding the LLM from producing engineering values directly. |
| Unit normalization & dimensional analysis | High | `pint` is mature. Deterministic. |
| Standard atmosphere model (ISA) | High | Closed-form, well-documented. Trivial to test against published tables. |
| Reynolds / Mach computation | High | Pure functions. Fully testable. |
| NACA 4-digit / 5-digit geometry | High | Closed-form equations. Reference datasets exist. |
| Airfoil visualization | High | Matplotlib / Plotly. Pure rendering. |
| OpenFOAM case generation from templates | Medium | Templating itself is easy (Jinja2). The risk is producing cases that *actually run* — mesh quality, boundary patch naming, solver/scheme compatibility. Mitigation: ship a small, validated set of templates and explicitly mark anything else as experimental. |
| Mesh generation (blockMesh / snappyHexMesh) | Medium-High risk | snappyHexMesh is sensitive to STL quality and feature edges. Initial scope should stay with 2D-ish blockMesh around an extruded airfoil. |
| Running OpenFOAM solver inside platform | Medium-High risk | Heavy dependency, long runtimes, environment management. Initial scope should *generate cases only*; execution is out-of-scope for early phases or runs via an opt-in containerized worker. |
| Workflow orchestration | High | Plain DAG / staged pipeline is sufficient initially. No Airflow/Temporal needed early. |
| Persistence (runs, artifacts, metadata) | High | SQLite → Postgres path. Filesystem for artifacts initially, S3-compatible later. |
| Web UI | High | Standard SPA. Engineering polish takes time, not novelty. |
| Multi-user / auth | Deferred | Single-user local-first first; auth added later. |
| LLM-driven autonomous agent loops | Deferred | Out of initial scope. The orchestrator is deterministic; agentic loops are a future phase only after the deterministic path is solid. |

---

## 4. Technical Risks (Ranked)

R1. **CFD case validity** — Generating files is easy; generating files that
produce a *physically meaningful* solution is hard. Mitigation: restrict
initial templates to a small validated envelope (2D airfoil, incompressible
or low-Mach), document the envelope, and refuse out-of-envelope requests.

R2. **LLM numeric hallucination** — Even with structured output, models will
invent values for missing fields. Mitigation: schema forbids unsourced
numerics; missing values are surfaced as explicit `assumptions[]` with
provenance `inferred` vs `user_provided`, and all engineering math runs on
the deterministic pipeline regardless of LLM output.

R3. **Unit and convention drift** — m/s vs knots, chord in m vs mm, deg vs
rad, sea-level vs altitude. Mitigation: single canonical SI internal
representation; `pint`-based ingestion at the boundary; never mix units in
the core.

R4. **OpenFOAM environment fragility** — Versions differ (.org vs .com,
v2312 vs v11). Mitigation: pin a target OpenFOAM version per template set;
templates declare the version they target; refuse to emit for unsupported
versions.

R5. **Geometry edge cases** — Reflex cambers, very thin sections, trailing
edge closure. Mitigation: validation rules on output coordinates
(monotonicity, closure tolerance, min thickness) before emission.

R6. **Reproducibility** — Same intent must produce the same artifacts.
Mitigation: deterministic seeds where applicable, content-hashed artifact
IDs, full run manifest including library versions.

R7. **Scope creep** — "Aerodynamic design platform" is unbounded.
Mitigation: hard phase gates and an explicit "out of scope (for now)" list
in the roadmap.

R8. **Performance of LLM round-trips in UI** — Streaming + cached
classifications mitigate this; not a blocker.

---

## 5. Initial Feasible Envelope (v0.1 target)

The first end-to-end vertical slice will deliberately be narrow:

- Flow regime: incompressible, low subsonic (Ma < 0.3).
- Geometry: NACA 4-digit airfoils only.
- Domain: 2D (extruded one cell in span for OpenFOAM).
- Mesh: blockMesh-based C-grid or O-grid template.
- Solver: `simpleFoam` (steady, incompressible, RANS).
- Turbulence: a single well-tested model (e.g., `kOmegaSST`) with sane
  defaults.
- Execution: case files generated and packaged; solver execution is
  out-of-scope for v0.1.

Anything outside this envelope must be explicitly rejected with a clear
message in v0.1.

---

## 6. Out of Scope (initially)

- Transonic / supersonic regimes.
- 3D wings, full aircraft, multi-body.
- Optimization loops, adjoint methods, shape morphing.
- Live solver execution and result post-processing in-platform.
- Autonomous multi-agent design loops.
- Multi-tenant SaaS, billing, organizations.

These remain on the long-term roadmap but are explicitly excluded from
early phases.

---

## 7. Conclusion

The platform is feasible **if scope is held**. The deterministic engineering
core (physics + geometry + templating) is well-trodden ground. The LLM
layer is feasible with strict structured-output discipline. The principal
risks are CFD case validity and scope discipline — both managed through
phasing, validated templates, and an explicit operating envelope.

Recommendation: proceed with Phase 0 (repository, tooling, governance) and
Phase 1 (deterministic physics core), deferring all LLM and OpenFOAM work
until the deterministic foundation is testable and stable.
