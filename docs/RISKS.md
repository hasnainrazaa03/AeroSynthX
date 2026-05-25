# AeroSynthX — Risk Register

Living document. Risks are reviewed at the end of each phase.

Risk levels: **L** (low) / **M** (medium) / **H** (high).
Status: **Open** / **Mitigated** / **Accepted** / **Closed**.

| ID | Risk | Level | Status | Mitigation |
|---|---|---|---|---|
| R1 | Generated OpenFOAM cases run but produce nonphysical results | H | Open | Lock initial operating envelope (2D, low-Mach, single solver/turbulence model). Validate templates against a known reference case before release. |
| R2 | LLM hallucinates engineering numerics | H | Open | LLM produces *intent fields only*; all physics is computed by deterministic engine. Schema validation + retry-on-invalid + provenance tagging (`user_provided` vs `inferred`). |
| R3 | Unit / convention drift across modules | M | Open | Single canonical SI representation internally. `pint`-based ingestion at boundaries. Type-checked unit-bearing quantities at module edges. |
| R4 | OpenFOAM version fragmentation (.org vs .com, version drift) | M | Open | Each template set declares its target OpenFOAM version. Refuse to emit for unsupported versions. |
| R5 | Geometry edge cases (reflex camber, thin TE) | M | Open | Output validators: closure tolerance, monotonicity, minimum thickness. Golden-file tests against reference coordinates. |
| R6 | Reproducibility loss across runs | M | Open | Deterministic algorithms, content-hashed artifact IDs, run manifest captures library versions and inputs. |
| R7 | Scope creep beyond the operating envelope | H | Open | Explicit phase gates. "Out of scope" section in roadmap. PRs that broaden envelope require an architecture-doc update. |
| R8 | LLM provider lock-in | M | Open | Provider-agnostic client interface in `aerosynthx.intent`. No provider SDK leaks into core. |
| R9 | Secrets leakage (API keys in repo/logs) | M | Open | `.env`-based config, never committed. Pre-commit secret scanning. Structured logging redacts known-secret fields. |
| R10 | CI runtime balloons as solver-adjacent tests appear | L | Open | Keep solver-execution tests opt-in / nightly. Unit tests stay fast. |
| R11 | Visualization library churn (matplotlib/plotly API drift) | L | Open | Pin majors. Renderer kept behind a thin adapter. |
| R12 | Persistence schema migrations | M | Open | Use Alembic from Phase 5 onward. No schema changes without a migration. |
| R13 | Single-developer bus factor | M | Accepted (initial) | Documentation-first development; every phase produces docs sufficient for a new contributor to onboard. |

New risks are appended with the next free `R<N>` ID and reviewed at phase
gates. Closed risks are retained for history.
