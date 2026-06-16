# Phase 30 — 3D Mesh Generation for CFD

Target release: `v1.23.0` (Tentative)
Status: **In progress**
Goal: Integrate an automated 3D meshing workflow using OpenFOAM's `snappyHexMesh` to generate a body-fitted mesh around the 3D wing geometry created in Phase 29.

---

## 1. Architectural Analysis

This phase bridges the gap between 3D geometry generation and high-fidelity CFD analysis. The implementation will extend the existing OpenFOAM workflow to handle 3D cases.

- **New `aerosynthx.meshing` Package**: A new package will be created to handle all meshing-specific logic.
  - `meshing.stl_exporter.py`: Will contain a function to convert the `Wing` object into an STL file format, which is the standard input for `snappyHexMesh`.
  - `meshing.snappy.py`: Will contain logic to generate a valid `snappyHexMeshDict` based on the wing's geometry and predefined refinement levels.
- **Workflow Integration**: A new `MESH` stage will be added to the `StageName` enum and inserted into the pipeline for 3D workflows, following the `wing_geometry` stage. The `Pipeline._execute_run` method will be updated to:
  1.  Generate the 3D wing geometry.
  2.  Export the geometry to an STL file within the OpenFOAM case directory.
  3.  Generate the `snappyHexMeshDict`.
  4.  Update the `Allrun` script to execute `snappyHexMesh`.
- **OpenFOAM Case Modification**: The `aerosynthx.openfoam.case.py` module will be updated to differentiate between 2D and 3D case generation. When a `WingSpec` is provided, it will use a different set of templates suitable for a 3D `snappyHexMesh` workflow (e.g., a simple background mesh `blockMeshDict` and the generated `snappyHexMeshDict`).
- **API & Intent**: For this phase, no changes to the `DesignIntent` are required. The presence of a `wing_spec` will be the sole trigger for the 3D meshing workflow. Meshing parameters (like refinement levels) will be hardcoded to sensible defaults to begin with, but a `meshing_settings` schema is a clear future extension.

This plan maintains the architectural integrity by encapsulating meshing logic in its own module and conditionally activating it within the existing workflow orchestrator.

---

## 2. Goals & Constraints

- **Goal**: Automatically generate a valid `snappyHexMeshDict` for a generated 3D wing.
- **Goal**: Export the 3D wing geometry to a standard STL file.
- **Goal**: Update the OpenFOAM case structure and scripts to support a 3D meshing workflow.
- **Constraint**: This phase only *generates* the meshing configuration. It does not *execute* `snappyHexMesh` or the 3D solver. Solver execution for 3D cases is a separate, future phase.
- **Constraint**: The meshing parameters will be based on sensible defaults, not user-configurable, to limit initial complexity.
- **Constraint**: All existing 2D workflows (both OpenFOAM and XFOIL) must remain entirely unaffected.

---

## 3. Implementation Plan

1.  **`aerosynthx.meshing.stl_exporter`**:
    *   Create a `export_wing_to_stl(wing: Wing) -> str` function that takes a `Wing` object and returns a string containing the STL file content. This will involve creating triangular facets from the wing's point cloud.
2.  **`aerosynthx.meshing.snappy`**:
    *   Create a `generate_snappy_dict(wing: Wing) -> dict` function that generates the dictionary structure for `snappyHexMeshDict`, including refinement regions around the wing.
3.  **`aerosynthx.openfoam.case`**:
    *   In `build_case`, add a condition to check if `intent.wing` is present.
    *   If it is, use a new set of 3D-specific Jinja2 templates.
    *   The `_write_airfoil` function will be replaced by a new `_write_wing_stl` function for 3D cases.
    *   A new `_write_snappy_dict` function will be added.
4.  **`aerosynthx.workflow.pipeline`**:
    *   Add a `MESH` stage to the `StageName` enum.
    *   In `_execute_run`, if a `wing_spec` is present, the `case` stage will now perform the 3D case generation, including the STL export and `snappyHexMeshDict` generation. The new `MESH` stage will be recorded to reflect this.
5.  **API**: No direct API changes are needed, but the `GET /api/v1/runs/{run_id}/files` endpoint will now serve the generated STL and `snappyHexMeshDict` files for 3D runs.

---

## 4. Acceptance Criteria

- [ ] A new `aerosynthx.meshing` package is created with `stl_exporter` and `snappy` modules.
- [ ] The `generate_wing` function's output can be successfully converted to a valid STL file.
- [ ] A valid `snappyHexMeshDict` is generated for a simple wing.
- [ ] The `build_case` function correctly generates a 3D OpenFOAM case structure when a `WingSpec` is provided.
- [ ] The `Allrun` script for a 3D case includes the `snappyHexMesh` command.
- [ ] All existing 2D workflows pass their tests without regression.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   Test the `export_wing_to_stl` function to ensure it produces a syntactically correct STL string.
    *   Test the `generate_snappy_dict` function to verify that the generated dictionary contains the correct keys and physically plausible values for a given wing.
- **Integration Tests**:
    *   Update `tests/workflow/test_pipeline.py` with a test that runs a 3D wing intent and asserts that the correct files (`wing.stl`, `snappyHexMeshDict`) are created in the output case directory.
- **Golden File Tests**:
    *   A "golden" `snappyHexMeshDict` file for a simple reference wing will be created and used to validate the output of the dictionary generator.

---

## 6. Risks & Limitations

- **STL Generation Complexity**: Correctly generating a watertight, properly oriented STL mesh from a point cloud is non-trivial. The initial implementation may have issues with complex wing shapes (high twist, sharp edges).
- **`snappyHexMesh` Tuning**: `snappyHexMesh` is notoriously difficult to configure. The default parameters chosen for this phase may not produce a high-quality mesh for all wing geometries. This is an expected limitation; fine-tuning will be part of future work.
- **No Execution**: This phase does not run the mesher or solver. The generated case is only validated structurally. The actual success of the mesh generation is not guaranteed until a future execution phase.

---

## 7. Future Extensibility

- **User-Defined Meshing Parameters**: The `DesignIntent` can be extended with a `meshing_settings` object to allow users to control refinement levels, boundary layer settings, and other `snappyHexMesh` parameters.
- **3D Solver Execution**: The next logical phase will be to add a `solve_3d` stage that executes `snappyHexMesh` and then runs a 3D solver like `simpleFoam`.
- **Other Meshers**: The `meshing` package could be extended to support other meshers, such as `cfMesh` or external tools.
