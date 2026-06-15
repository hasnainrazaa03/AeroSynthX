# Phase 24 — User-Supplied Airfoil Support

Target release: `v1.17.0` (Tentative)
Status: **Shipped**
Goal: Allow users to specify custom airfoils by providing a list of 2D coordinates, expanding the platform beyond built-in NACA generators while preserving determinism and strict validation.

---

## Architectural Alignment

This feature fits cleanly into the existing layered architecture:
- **Intent**: The `AirfoilSpec` schema will be extended to accept a `custom` family and an optional `coordinates` field.
- **Geometry**: A new generator `custom_airfoil()` will validate the user-supplied points, scale them by the chord length, and return a standard `Airfoil` dataclass. This ensures the rest of the system remains ignorant of where the points came from.
- **OpenFOAM**: The envelope guard will be relaxed to permit `custom` families. The templating engine already operates entirely on the `Airfoil` coordinate array and requires no changes.

## Acceptance Criteria

- [x] `aerosynthx.intent.schemas.AirfoilSpec` accepts `family="custom"`.
- [x] `AirfoilSpec` accepts an optional `coordinates` field (list of `[x, y]` pairs).
- [x] A Pydantic validator ensures `coordinates` are provided exactly when `family == "custom"`.
- [x] A new `aerosynthx.geometry.custom.custom_airfoil()` generator is created.
- [x] `custom_airfoil()` validates that the provided normalized coordinates are in Selig order (TE -> Upper -> LE -> Lower -> TE) and scales them by `chord_m`.
- [x] The OpenFOAM envelope guard in `aerosynthx.openfoam.case.py` is updated to allow `custom` airfoils.
- [x] Unit tests for the updated schema.
- [x] Unit tests for `custom_airfoil()` including invalid coordinate structures.
- [x] End-to-end workflow test verifying a custom airfoil intent generates an OpenFOAM case.
- [x] Backwards compatibility is preserved (existing NACA tests pass).
- [x] Coverage ≥ 90% line / ≥ 85% branch for new modules.

---

## Design & Implementation Details

### Schema Updates
The `AirfoilSpec` model will be updated. Instead of breaking backward compatibility by converting it into a discriminated union, we will add a `coordinates: list[tuple[float, float]] | None = None` field and enforce its presence via a `@model_validator`.

### Geometry Engine
A new module `src/aerosynthx/geometry/custom.py` will handle custom profiles.
Since user coordinates might not exactly close at `[1, 0]`, the generator should rely on the existing `validate_airfoil()` logic to ensure the shape is physically sensible before wrapping it in an `Airfoil` dataclass.

### API/Workflow impacts
None. Because the intent is passed as JSON, users can simply send the coordinates in the JSON payload of the API request.

### Test Strategy
- **Unit**: Verify `AirfoilSpec` correctly rejects NACA inputs with coordinates, and custom inputs without coordinates.
- **Unit**: Verify `custom_airfoil` correctly scales coordinates and rejects non-normalized inputs (e.g., $X \notin [0, 1]$).
- **Integration**: A full pipeline test passing custom coordinates (e.g., a hand-coded triangle or a loaded `.dat` file) through the OpenFOAM generator.

### Risks and Edge Cases
- **Coordinate Sorting**: Users might provide points in random order or clockwise. We must enforce the Selig convention (counter-clockwise starting from TE) to avoid inverted normals in OpenFOAM. We will strictly validate this rather than trying to auto-sort, adhering to the "refuse out-of-envelope requests" principle.
- **Normalization**: User points must be normalized (chord = 1). The `custom_airfoil` function must enforce that $X_{min} \approx 0$ and $X_{max} \approx 1$.
