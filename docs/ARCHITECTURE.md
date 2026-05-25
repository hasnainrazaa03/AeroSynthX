# AeroSynthX — Architecture (v0.1)

Status: **Accepted for Phase 1.**
Document type: Explanation.

This document defines module boundaries, data contracts, the internal
unit convention, error handling, and the determinism rules that govern
the engineering core. It is the source of truth for how the system is
structured. Changes that conflict with this document require an ADR.

---

## 1. Architectural Goals

1. **Deterministic engineering core.** Given the same validated inputs,
   physics and geometry produce byte-identical outputs.
2. **LLM at the edges, not the center.** Natural-language interpretation
   is the only LLM responsibility. Engineering math, geometry, and
   simulation file generation never depend on LLM output values.
3. **Strict layering.** Inner layers do not import outer layers. The
   physics core has no knowledge of the LLM, the orchestrator, the API,
   or the UI.
4. **Failure is typed.** Every failure mode has a named exception with a
   stable code, mapped to a structured response at the boundary.
5. **Units are canonical internally.** SI base units everywhere inside
   the core. Conversion happens only at boundaries.

---

## 2. Layered Module Map

```
┌─────────────────────────────────────────────────────────┐
│ UI (Phase 6)                                            │
├─────────────────────────────────────────────────────────┤
│ HTTP API (Phase 6)                                      │
├─────────────────────────────────────────────────────────┤
│ Workflow Orchestrator (Phase 5)                         │
│   parse → validate → compute → geometry → case → pkg   │
├──────────────┬─────────────┬─────────────┬──────────────┤
│ Intent       │ Geometry    │ OpenFOAM    │ Persistence  │
│ (Phase 3)    │ (Phase 2)   │ (Phase 4)   │ (Phase 5)    │
├──────────────┴─────────────┴─────────────┴──────────────┤
│ Physics Core (Phase 1) — atmosphere, units, aero        │
└─────────────────────────────────────────────────────────┘
```

Import rules (enforced by convention now, by tooling later):

- `physics` depends on nothing inside `aerosynthx` except stdlib +
  `numpy` + `pint`.
- `geometry` depends on `physics` (only for unit types) + `numpy`.
- `intent` depends on `physics` (validation) and Pydantic; the LLM
  client is provider-agnostic.
- `openfoam` depends on `physics`, `geometry`, and `intent` schemas.
- `workflow` depends on all the above.
- `api` / `ui` depend on `workflow` only.
- **No upward imports.** `physics` never imports `intent` or higher.

---

## 3. Canonical Units (Internal SI)

All values inside the core are stored as plain floats in SI base units.
This is the contract:

| Quantity            | Internal unit |
|---------------------|---------------|
| Length              | meter (`m`)   |
| Mass                | kilogram (`kg`) |
| Time                | second (`s`)  |
| Temperature         | kelvin (`K`)  |
| Pressure            | pascal (`Pa`) |
| Velocity            | meter/second (`m/s`) |
| Dynamic viscosity   | pascal·second (`Pa·s`) |
| Kinematic viscosity | meter²/second (`m²/s`) |
| Density             | kilogram/meter³ (`kg/m³`) |
| Angle               | radian (`rad`) |
| Reynolds number     | dimensionless |
| Mach number         | dimensionless |

Conversion from arbitrary units happens at one well-defined entry point:
`aerosynthx.physics.units.to_si(value, unit_str)`. The boundary parses
the unit string via `pint`, converts to SI, and returns a `float`. After
this point the core sees floats only.

Rationale: keeping unit-bearing objects in the core makes every function
signature noisy and bleeds `pint` into every test. Doing the conversion
once at the boundary keeps the inner functions simple and fast.

---

## 4. Data Contracts (Phase 1 surface)

Phase 1 introduces only physics primitives — no Pydantic schemas yet
(those land in Phase 3). The public surface of `aerosynthx.physics` is a
small set of pure functions and one immutable result dataclass for
atmosphere queries.

```python
# Pure functions
to_si(value: float, unit: str, *, dimension: str | None = None) -> float
isa_atmosphere(altitude_m: float) -> AtmosphereState
reynolds_number(velocity_m_s: float, length_m: float,
                kinematic_viscosity_m2_s: float) -> float
mach_number(velocity_m_s: float, speed_of_sound_m_s: float) -> float
dynamic_pressure(density_kg_m3: float, velocity_m_s: float) -> float
speed_of_sound(temperature_k: float, gamma: float = 1.4,
               gas_constant_j_kg_k: float = 287.05287) -> float

# Immutable result
@dataclass(frozen=True, slots=True)
class AtmosphereState:
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float
    dynamic_viscosity_pa_s: float
    kinematic_viscosity_m2_s: float
```

All functions are pure: no I/O, no globals, no randomness.

---

## 5. Error Model

Each package defines a base exception. All raised errors derive from it.
Boundary code (workflow / API) catches the package base and maps to a
structured response with a stable `code` and human message.

```
AeroSynthXError                 # root
├── PhysicsError                # aerosynthx.physics
│   ├── UnitError               # bad unit string or dimension mismatch
│   ├── DomainError             # out-of-domain numeric input
│   └── AtmosphereError         # altitude out of supported range
├── GeometryError               # aerosynthx.geometry  (Phase 2)
├── IntentError                 # aerosynthx.intent    (Phase 3)
├── EnvelopeError               # out-of-envelope request (Phase 4)
└── OpenFOAMError               # aerosynthx.openfoam  (Phase 4)
```

Rules:

- Never raise bare `Exception`, `ValueError`, or `TypeError` from public
  functions. Convert to a typed package error with context.
- Every typed error carries a short, stable `code` string (e.g.
  `physics.unit.invalid`). Codes are part of the public contract; they
  do not change without a MAJOR bump.
- Error messages name the offending input and the expected shape.

---

## 6. Determinism Rules

- Engineering functions accept only primitive numerics. No file paths,
  no clocks, no environment lookups.
- NumPy is used for array math. Where reductions could be
  order-dependent (e.g. parallel sums), we stick to single-threaded
  deterministic implementations.
- No `random` calls in `physics` or `geometry`.
- Floating-point: standard IEEE-754 double precision. Documented
  tolerance for any test that compares against a reference.

---

## 7. Standard Atmosphere

We implement the **U.S. Standard Atmosphere 1976** (ISA-equivalent up to
the lower stratosphere) using closed-form formulas. Phase 1 supports the
troposphere and lower stratosphere bands:

| Layer | Altitude range (geopotential) | Lapse rate |
|---|---|---|
| Troposphere | 0 – 11 000 m | −6.5 K/km |
| Tropopause / lower stratosphere | 11 000 – 20 000 m | 0 K/km (isothermal) |

Constants (from US Standard Atmosphere 1976):

- `T0 = 288.15 K`, `P0 = 101 325 Pa`, `g0 = 9.80665 m/s²`.
- `R = 287.05287 J/(kg·K)` (specific gas constant for dry air).
- `gamma = 1.4`.

Dynamic viscosity uses **Sutherland's law** for air with
`C1 = 1.458e-6 kg/(m·s·K^0.5)`, `S = 110.4 K`.

Altitudes outside `[0, 20 000] m` raise `AtmosphereError` with code
`physics.atmosphere.out_of_range`. Higher altitudes are out of the v0.1
envelope.

---

## 8. Dependencies (Phase 1)

Runtime dependencies introduced in Phase 1:

- `numpy` — array math, vectorized atmosphere queries.
- `pint` — unit parsing at the boundary only.

These are the only runtime dependencies until Phase 2.

---

## 9. Test Strategy (Phase 1)

- Unit tests for every public function.
- Reference tests for ISA against tabulated values at
  0, 1000, 5000, 11 000, 15 000, 20 000 m. Tolerance documented.
- Property tests for unit round-trips and for Re/Ma sign + monotonicity
  invariants.
- Coverage gate enforced in CI: `aerosynthx.physics` ≥ 90% line, ≥ 85%
  branch.

---

## 10. Open Questions Deferred to Later Phases

- Choice of LLM provider abstraction interface — Phase 3 (ADR).
- Templating engine choice for OpenFOAM — Phase 4 (likely Jinja2, ADR).
- DB engine and migration tooling — Phase 5 (likely SQLAlchemy +
  Alembic, ADR).
- Web framework for UI — Phase 6 (ADR).

Until those ADRs are written, no module may take a dependency on a
specific choice in those areas.
