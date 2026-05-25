# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See [docs/VERSIONING.md](docs/VERSIONING.md) for the project's release
policy.

## [Unreleased]

### Added
- (nothing yet)

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

[Unreleased]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hasnainrazaa03/AeroSynthX/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/hasnainrazaa03/AeroSynthX/releases/tag/v0.0.1
