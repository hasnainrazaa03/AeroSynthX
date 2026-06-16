# Phase 29 — 3D Wing Builder

Target release: `v1.22.0` (Tentative)
Status: **Shipped**
Goal: Extend the geometry engine from 2D airfoil analysis to 3D wing generation, supporting realistic parametric wing definitions and creating a foundation for future 3D CFD workflows.

---

## 1. Architectural Analysis

This phase represents a major extension of the geometry engine's capabilities. The implementation will be carefully layered to build upon existing, validated components.

- **New `WingSpec` Schema**: A new Pydantic model, `WingSpec`, will be created in `aerosynthx.intent.schemas`. This schema will define the high-level parametric definition of a wing (e.g., span, sweep, taper, dihedral, twist). It will contain nested `AirfoilSpec` objects for the root and tip airfoils, reusing the existing airfoil definition schema. The `DesignIntent` will be updated to accept either an `AirfoilSpec` (for 2D workflows) or a `WingSpec` (for 3D workflows), with a validator to ensure mutual exclusivity.
- **New `aerosynthx.geometry.wing` Module**: All new 3D generation logic will be encapsulated in this new module.
  - A `generate_wing` function will be the primary entry point, taking a `WingSpec` as input.
  - This function will first call the existing 2D airfoil generators (`naca4`, `naca5`, `custom_airfoil`) to produce the root and tip airfoil sections.
  - It will then perform a linear interpolation of these sections along the span, applying the specified sweep, dihedral, and twist transformations at each station.
  - The output will be a new `Wing` dataclass, containing the 3D coordinates of the wing surface, section profiles, and other metadata.
- **Workflow & Persistence**: The primary goal of this phase is the generation and validation of the geometry itself. The `Pipeline` will be updated to include a new `wing_geometry` stage that is conditionally executed. The generated `Wing` object will be saved as a JSON artifact for the run. Full integration with a 3D CFD solver (like OpenFOAM with `snappyHexMesh`) is out of scope for this phase but is the natural next step.
- **API & Reporting**: The API will be updated to accept the `WingSpec`. A new endpoint will be added to allow retrieval of the generated 3D wing geometry data, enabling visualization in external tools like ParaView or Blender.

---

## 2. Goals & Constraints

- **Goal**: Define a wing using standard aerodynamic parameters (span, chord, sweep, dihedral, twist).
- **Goal**: Use any existing 2D airfoil type (NACA 4/5, custom) as the root and tip sections.
- **Goal**: Generate a deterministic, 3D point cloud representation of the wing surface.
- **Constraint**: This phase is focused on geometry generation only. No 3D CFD analysis will be performed.
- **Constraint**: Only simple, untapered, unswept wings will be supported in the initial implementation within this phase, with the other parameters to follow.
- **Constraint**: All existing 2D workflows must remain completely unaffected.

---

## 3. Implementation Plan

1.  **`aerosynthx.intent.schemas`**:
    *   Create a `WingSpec` model with fields for `span`, `root_chord`, `tip_chord`, `sweep_deg`, `dihedral_deg`, `twist_deg`, and nested `root_airfoil: AirfoilSpec` and `tip_airfoil: AirfoilSpec`.
    *   Update `DesignIntent` to include `wing_spec: WingSpec | None = None`.
    *   Add a validator to `DesignIntent` to ensure that either `airfoil_spec` or `wing_spec` is provided, but not both.
2.  **`aerosynthx.geometry.wing`**:
    *   Create a `Wing` dataclass to hold the 3D coordinates (`x`, `y`, `z` arrays) and metadata.
    *   Implement the `generate_wing` function. It will:
        *   Generate the 2D coordinates for the root and tip airfoils.
        *   Create a series of spanwise stations.
        *   At each station, interpolate between the root and tip sections to create the local airfoil shape.
        *   Apply sweep, dihedral, and twist transformations to the coordinates of each section.
        *   Combine the transformed sections into a single 3D point cloud.
3.  **`aerosynthx.workflow.pipeline`**:
    *   Add a new `wing_geometry` stage to the `StageName` enum.
    *   In the `Pipeline.run` method, add logic to conditionally run the `wing_geometry` stage if a `WingSpec` is present in the intent.
    *   The `wing_geometry` stage will call `generate_wing` and save the resulting `Wing` object as a JSON artifact.
4.  **API & CLI**:
    *   The API will automatically support the new `WingSpec` through the existing `create_run` endpoint.
    *   A new endpoint, `GET /api/v1/runs/{run_id}/wing`, will be added to retrieve the generated wing geometry data.
    *   The CLI will support running 3D geometry generation by passing an intent that includes a `wing_spec`.

---

## 4. Acceptance Criteria

- [x] A `WingSpec` schema is added to the intent layer.
- [x] The `DesignIntent` is updated to be either 2D or 3D.
- [x] A `generate_wing` function is implemented that can create a 3D wing from a `WingSpec`.
- [x] The generated wing geometry is deterministic and correct for a simple (untapered, unswept) case.
- [x] The pipeline is updated to include a `wing_geometry` stage that saves the 3D geometry as an artifact.
- [x] A new API endpoint is added to retrieve the generated 3D wing data.
- [x] All existing 2D tests pass without modification.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   Test the `WingSpec` and `DesignIntent` validation logic.
    *   Write extensive unit tests for the `generate_wing` function. Start with a simple case (e.g., a rectangular wing with a NACA 0012 profile) and verify the generated coordinates against a known-good "golden" file.
    *   Add tests for sweep, taper, and dihedral, verifying the transformations at key stations (root, mid-span, tip).
- **Integration Tests**:
    *   Add a test to `test_pipeline.py` that executes a full run with a `WingSpec`, verifying that the `wing_geometry` stage runs and produces an artifact.
    *   Add a test to `test_app.py` for the new `GET /api/v1/runs/{run_id}/wing` endpoint.

---

## 6. Risks & Limitations

- **Geometric Complexity**: 3D geometry transformations can be complex and prone to errors, especially when combining sweep, dihedral, and twist. The implementation must be carefully validated.
- **Visualization**: The platform itself will not have a built-in 3D renderer. Users will need to use external tools like ParaView, Blender, or a custom script with Matplotlib 3D to visualize the generated wing, which could be a usability hurdle.
- **Downstream Consumption**: This phase only generates the geometry. It does not prepare it for CFD. The output format will need to be carefully considered to ensure it can be used by meshing tools in a future phase (e.g., by ensuring the point cloud is structured and can be easily converted to a surface mesh format like STL).

---

## 7. Future Extensibility

- **Advanced Geometry**: The `WingSpec` can be extended to support more complex features like multiple taper sections, gull wings, or winglets.
- **3D CFD Workflow**: This is the most important next step. A new phase will be required to take the generated `Wing` object and use it to create a full 3D CFD case for OpenFOAM, likely using `snappyHexMesh`.
- **Structural Analysis**: With a defined 3D geometry, the platform could be extended to perform basic structural analysis, such as calculating wing weight or estimating bending moments.
