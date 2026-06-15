# Phase 26 — XFOIL Polar Sweeps

Target release: `v1.19.0` (Tentative)
Status: **Shipped**
Goal: Extend the XFOIL integration to support sweeps over a range of angles of attack, generating full aerodynamic polar curves (Cl, Cd, Cm vs. alpha).

---

## 1. Architectural Analysis

This phase enhances the existing XFOIL fast-analysis path. The changes are localized and follow established patterns:

- **Intent Schema**: The `aerosynthx.intent.schemas.FlowCondition` model will be extended to accept an angle of attack range. A validator will ensure that either a single AoA or a sweep range is provided, but not both, maintaining a clear and unambiguous intent.
- **XFOIL Runner**: The `aerosynthx.xfoil.runner` will be updated to generate a different command script for XFOIL, using the `ASEQ` command for sweeps instead of the `ALFA` command for single points. This isolates the change to the XFOIL-specific logic.
- **XFOIL Parser**: The `aerosynthx.xfoil.parser` will be updated to handle multi-row polar files, returning a list of `XfoilResult` objects.
- **Persistence**: The `aerosynthx.workflow.db.XfoilResultRow` will be modified. Instead of storing single float values for `cl`, `cd`, etc., it will have a single `polar_json` text field. This field will store the entire list of polar results as a JSON array, which is a flexible and efficient way to persist variable-length structured data in SQLite.
- **Workflow/API**: The `RunResult` will be updated to hold a `list[XfoilResult]`. The existing API endpoints will automatically return the full polar data without needing signature changes, demonstrating the strength of the current architecture.

---

## 2. Goals & Constraints

- **Goal**: Allow users to generate full polar curves by specifying a start angle, end angle, and increment.
- **Goal**: Provide a richer dataset for aerodynamic analysis and design trade-offs.
- **Constraint**: The existing single-point XFOIL analysis must continue to work as before.
- **Constraint**: The changes must not affect the OpenFOAM workflow path.
- **Constraint**: The solution must handle cases where XFOIL converges for some angles of attack in a sweep but not others.

---

## 3. Implementation Plan

1.  **`aerosynthx.intent.schemas.py`**:
    *   Add `alpha_start_deg: float | None`, `alpha_end_deg: float | None`, and `alpha_increment_deg: float | None` to the `FlowCondition` model.
    *   Add a `@model_validator` to ensure that either `angle_of_attack_deg` is set (for single-point) or the three sweep parameters are set, but not both.
2.  **`aerosynthx.xfoil.runner.py`**:
    *   Update `run_xfoil` to check for the new sweep parameters in the `FlowCondition`.
    *   If a sweep is requested, generate an XFOIL script with the `ASEQ` command (e.g., `ASEQ {start} {end} {incr}`).
3.  **`aerosynthx.xfoil.parser.py`**:
    *   Modify `parse_polar_file` to loop through all data rows in the polar file and return a `list[XfoilResult]`.
    *   If no data rows are found, it should return an empty list.
4.  **`aerosynthx.workflow.db.py`**:
    *   Modify `XfoilResultRow` to remove the `alpha_deg`, `cl`, `cd`, and `cm` columns.
    *   Add a new `polar_json: Mapped[str] = mapped_column(String)` column.
5.  **`aerosynthx.workflow.pipeline.py`**:
    *   Update `RunResult` to hold `xfoil_results: list[XfoilResult] | None = None` (plural).
    *   Update the `_xfoil_stage` to store the list of results.
    *   Update the `_persist` method to serialize the list of `XfoilResult` objects into the `polar_json` field of the `XfoilResultRow`.
    *   Update `_row_to_result` to deserialize the JSON from `polar_json` back into a list of `XfoilResult` objects.

---

## 4. Acceptance Criteria

- [x] `FlowCondition` schema is updated with sweep parameters and validation.
- [x] `run_xfoil` generates an `ASEQ` script when a sweep is requested.
- [x] `parse_polar_file` correctly parses multi-row polar files.
- [x] The `XfoilResultRow` in the database correctly stores the full polar as JSON.
- [x] A CLI run with sweep parameters (e.g., `--alpha-start 0 --alpha-end 5 --alpha-incr 1`) successfully executes and persists a multi-point result.
- [x] The API accepts and processes sweep parameters correctly.
- [x] Single-point XFOIL analysis and all OpenFOAM workflows remain unaffected.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   Test the new validator on the `FlowCondition` model to ensure it correctly handles valid and invalid combinations of single-point and sweep AoA parameters.
    *   Update the `test_runner.py` mock tests to assert that the correct `ASEQ` command is generated when sweep parameters are provided.
    *   Update `test_parser.py` to test the parsing of multi-row polar files.
- **Integration Tests**:
    *   Extend `test_xfoil_integration.py` with a new skippable test that runs a real XFOIL sweep for a NACA 0012 airfoil and asserts that the returned list of results has the correct length and contains plausible aerodynamic coefficients.
- **Workflow/API Tests**:
    *   Extend `test_pipeline.py` and `test_app.py` to include end-to-end tests for the sweep functionality, verifying that the final `RunResult` contains a list of polar data points.

---

## 6. Risks & Limitations

- **Partial Convergence**: XFOIL may fail to converge for some points in a sweep (e.g., at high angles of attack near stall). The current plan is to have the parser return only the successfully converged points. The `RunResult` will therefore contain a partial polar. This is acceptable for a first implementation, but future versions could provide more detailed information about which points failed.
- **Database Migration**: This change modifies a database table (`xfoil_results`). Since the project does not yet have a formal migration system like Alembic, this is a breaking change for existing databases. For the current phase, this is acceptable as the project is still in rapid development. A future phase should address database migrations.
- **Performance**: Storing the full polar as a JSON blob is efficient for reads and writes, but it makes it impossible to query the coefficient data directly in SQL. This is an acceptable trade-off for now.

---

## 7. Future Extensibility

- **Richer Results**: The parser could be extended to extract more data from the XFOIL output, such as transition points (`Top_Xtr`, `Bot_Xtr`).
- **Other Sweeps**: The same pattern can be used to implement sweeps over Reynolds number or Mach number.
- **Advanced Error Reporting**: The system could be updated to report exactly which points in a sweep failed to converge and why.
