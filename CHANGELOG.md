# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See [docs/VERSIONING.md](docs/VERSIONING.md) for the project's release
policy.

## [Unreleased]

### Added
- (nothing yet)

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

[Unreleased]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/hasnainrazaa03/AeroSynthX/releases/tag/v0.0.1
