# Phase 23 — NACA 5-Digit Airfoil Support

Target release: `v1.16.0` (Tentative)
Status: **Shipped**
Goal: Expand the geometry engine and intent schema to support the generation, validation, and simulation of NACA 5-digit series airfoils, building on the existing NACA 4-digit infrastructure.

---

## Acceptance Criteria

- [x] `aerosynthx.intent.schemas.AirfoilSpec` updated to accept `"naca5"` as a valid `family`.
- [x] A Pydantic validator is added to `AirfoilSpec` to ensure the `designation` string is 5 digits for the `naca5` family.
- [x] A new `aerosynthx.geometry.naca5` module is created, containing the generation logic for NACA 5-digit airfoils.
- [x] The `naca5` generator implements the standard piecewise camber line equations and shared thickness distribution formula.
- [x] The public function `aerosynthx.geometry.naca5()` returns a validated `Airfoil` dataclass, consistent with the existing `naca4` generator.
- [x] The OpenFOAM envelope guard is updated to accept `DesignIntent` objects with `naca5` airfoils.
- [x] Golden-file tests are added, comparing generated coordinates for canonical NACA 5-digit airfoils (e.g., 23012, 23015, 23112) against a trusted reference source.
- [x] An end-to-end workflow test successfully generates an OpenFOAM case for a NACA 5-digit airfoil.
- [x] All existing tests continue to pass, ensuring full backwards compatibility.
- [x] Coverage ≥ 90% line / ≥ 85% branch on `aerosynthx.geometry.naca5`, and project-wide coverage is maintained.
- [x] All quality gates green (`ruff`, `mypy`, `pytest`).
- [x] `CHANGELOG.md` updated with the new feature.
- [x] `docs/ROADMAP.md` updated to reflect the completion of this feature.

---

## Design & Implementation Details

### Schema
- The `family` field in `AirfoilSpec` will be changed to `Literal["naca4", "naca5"]`.
- A `@model_validator` will be added to `AirfoilSpec` to enforce that the `designation` length (4 or 5) matches the `family`.

### Geometry
- A new module, `aerosynthx.geometry.naca5`, will be created to house the generation logic.
- The implementation will follow the mathematical definitions from a standard aerodynamics text (e.g., Abbott & von Doenhoff, *Theory of Wing Sections*), paying close attention to the piecewise nature of the camber line equations.
- The module will expose a single public function, `naca5()`, which takes a designation string and other parameters (`n_points`, `chord_m`, etc.) and returns an `Airfoil` object.

### Testing
- A new test file, `tests/geometry/test_naca5.py`, will be created.
- It will contain precise, byte-for-byte comparisons against reference coordinate files checked into the repository.
- It will also test for correct error handling on invalid designation strings.
- Existing integration test files for `intent` and `workflow` will be updated to include cases for the `naca5` family.

### Out of Scope
- NACA 6-series or other airfoil families.
- User-supplied airfoil coordinates (this is a separate, future feature).
- 3D geometry. This phase is strictly limited to the 2D geometry engine.
