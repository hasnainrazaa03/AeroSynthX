# Phase 1 — Architecture Spec + Deterministic Physics Core

Target release: `v0.1.0`.
Status: **In progress.**
Goal: Lock the architecture document and ship a tested, deterministic
physics engine. No LLM, no OpenFOAM, no I/O.

---

## Acceptance Criteria

- [x] `docs/ARCHITECTURE.md` finalized for v0.1.
- [x] `src/aerosynthx/physics/` package implemented:
  - [x] `errors` — typed exception hierarchy.
  - [x] `units` — boundary unit conversion via `pint`.
  - [x] `atmosphere` — US Standard Atmosphere 1976 (0–20 km) + Sutherland.
  - [x] `aero` — Reynolds, Mach, dynamic pressure, speed of sound.
- [x] Unit tests for every public function.
- [x] Reference tests against tabulated ISA values within documented
      tolerance.
- [x] Coverage ≥ 90% line / ≥ 85% branch for `aerosynthx.physics`,
      enforced in CI.
- [x] Quality gates green (`ruff check`, `ruff format --check`, `mypy`,
      `pytest -q`).
- [x] `CHANGELOG.md` updated.
- [x] Tagged `v0.1.0`.

---

## Task Checklist

### Architecture
- [x] Layered module map.
- [x] Canonical SI unit table.
- [x] Phase 1 public surface (function signatures).
- [x] Error taxonomy + code namespace rules.
- [x] Determinism rules.
- [x] Phase 1 test strategy.

### `aerosynthx.physics.errors`
- [x] `AeroSynthXError` root.
- [x] `PhysicsError`, `UnitError`, `DomainError`, `AtmosphereError`.
- [x] Stable `code` attribute on every error.

### `aerosynthx.physics.units`
- [x] `to_si(value, unit, *, dimension=None)` using `pint`.
- [x] Reject empty strings, unknown units, and dimension mismatches.
- [x] Single shared `UnitRegistry` instance.

### `aerosynthx.physics.atmosphere`
- [x] `AtmosphereState` immutable dataclass.
- [x] `isa_atmosphere(altitude_m)` — troposphere + tropopause/lower
      stratosphere (0–20 km).
- [x] Sutherland's law for dynamic viscosity.
- [x] Out-of-range altitudes raise `AtmosphereError`.

### `aerosynthx.physics.aero`
- [x] `speed_of_sound(temperature_k, gamma=1.4, R=287.05287)`.
- [x] `reynolds_number(v, L, nu)`.
- [x] `mach_number(v, a)`.
- [x] `dynamic_pressure(rho, v)`.
- [x] Domain checks on every input.

### Tests
- [x] `test_errors.py` — codes are stable, hierarchy correct.
- [x] `test_units.py` — happy path, dimension mismatch, bad unit.
- [x] `test_atmosphere.py` — reference values at 0, 1k, 5k, 11k, 15k,
      20k m; out-of-range rejected.
- [x] `test_aero.py` — formulae match hand calcs; domain checks fire.

### Tooling
- [x] Add `numpy`, `pint` to runtime deps.
- [x] CI `--cov-fail-under=90` enforced.

### Release
- [x] `CHANGELOG.md` `[0.1.0]` section dated.
- [x] Tag `v0.1.0`.
- [x] Push tag.

---

## Out of Scope

- LLM, geometry, OpenFOAM, persistence, API, UI.
- Altitudes above 20 km (deferred).
- Humidity, compressibility corrections beyond ideal gas (deferred).
