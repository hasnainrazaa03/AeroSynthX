# Phase 28 — Optimization & Design Exploration

Target release: `v1.21.0` (Tentative)
Status: **Shipped**
Goal: Introduce an optimization layer that can perform design-space exploration to find optimal aerodynamic solutions based on user-defined objectives and constraints.

---

## 1. Architectural Analysis

This phase adds a new top-level orchestration capability. The architecture will be extended in a layered manner, building directly on the `study` package from Phase 27.

- **New `aerosynthx.optimizer` Package**: A new package will be created to contain all optimization logic.
  - `optimizer.schemas`: Will define the `OptimizationSpec` (defining design variables, constraints, and objectives like "maximize Cl/Cd") and `OptimizationResult`.
  - `optimizer.engine`: Will contain the search algorithm. For this initial phase, a deterministic **grid search** will be implemented. This algorithm exhaustively evaluates every combination of the provided design variables, which guarantees finding the global optimum for the given discrete space and aligns perfectly with the project's "deterministic core" philosophy.
  - `optimizer.runner`: An `OptimizationRunner` will be the main orchestrator. It will take an `OptimizationSpec`, use the `engine` to generate a `StudySpec`, and then execute it using the existing `StudyRunner`. This promotes code reuse and maintains a clean dependency hierarchy: `Optimizer -> Study -> Pipeline`.
- **Workflow Integration**: The `OptimizationRunner` will be the highest-level orchestrator. By using the `StudyRunner` as a library, we avoid modifying the core `Pipeline` and ensure that the optimization process is a clean composition of existing, tested components.
- **Persistence**: A new `optimizations` table will be added to the database to store the optimization specification and its final results (e.g., the best-performing run ID). The underlying study and all its individual runs will be persisted via the existing database schema, providing full traceability.
- **API & Reporting**: New endpoints under `/api/v1/optimizations` will be added for creating and retrieving optimization jobs. A new `render_optimization_report` function will be created to summarize the results and highlight the optimal candidate.

---

## 2. Goals & Constraints

- **Goal**: Enable users to define a design space (e.g., multiple airfoils, a range of Reynolds numbers) and an objective (e.g., "maximize Cl/Cd").
- **Goal**: Automatically execute analyses for all points in the design space and identify the best-performing candidate.
- **Goal**: Provide a clear report summarizing the optimization process and its outcome.
- **Constraint**: The optimization must be deterministic. Given the same `OptimizationSpec`, the same candidate(s) must be identified as optimal every time.
- **Constraint**: For this phase, optimization will be limited to the `xfoil` analysis mode to ensure timely results.
- **Constraint**: The design variables will be limited to discrete values provided by the user (e.g., a list of airfoils or a list of Reynolds numbers). Continuous optimization is out of scope.

---

## 3. Implementation Plan

1.  **`aerosynthx.optimizer.schemas`**:
    *   Create `OptimizationSpec` with fields for `objective` (e.g., `maximize_cl_cd`), `design_space` (a dictionary similar to the study's `variables`), and a `base_intent`.
    *   Create `OptimizationResult` to store the `study_id` and the `best_run_id`.
2.  **`aerosynthx.workflow.db`**:
    *   Add an `optimizations` table to store the `id`, `spec_json`, `status`, and `result_json`.
3.  **`aerosynthx.optimizer.engine`**:
    *   Create a `GridSearchEngine` that takes the `design_space` and generates a `StudySpec`.
4.  **`aerosynthx.optimizer.runner`**:
    *   Create an `OptimizationRunner` that:
        *   Creates an `OptimizationRow` in the database.
        *   Uses the `GridSearchEngine` to create a `StudySpec`.
        *   Executes the study using the `StudyRunner`.
        *   Analyzes the `StudyResult` to find the run that best meets the objective.
        *   Persists the `OptimizationResult` to the database.
5.  **`aerosynthx.optimizer.report`**:
    *   Create a `render_optimization_report` function that presents the results, highlighting the best candidate.
6.  **API & CLI**:
    *   Add `/api/v1/optimizations` endpoints.
    *   Add an `aerosynthx optimize` CLI command.

---

## 4. Acceptance Criteria

- [x] A new `aerosynthx.optimizer` package is created.
- [x] The database is updated with an `optimizations` table.
- [x] An optimization job with the objective "maximize Cl/Cd" can be successfully executed over a defined design space.
- [x] The optimizer correctly identifies and records the best-performing run from the study.
- [x] The API and CLI provide interfaces for creating and retrieving optimization results.
- [x] A comparative report summarizing the optimization is generated.
- [x] All existing tests for single runs and studies pass without modification.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   Test the `OptimizationSpec` schema validation.
    *   Test the `GridSearchEngine` to ensure it correctly generates a `StudySpec` from an `OptimizationSpec`.
    *   Test the `OptimizationRunner`'s logic for analyzing results and finding the optimum, using a mocked `StudyResult`.
- **Integration Tests**:
    *   Add integration tests for the new `/api/v1/optimizations` endpoints and the `aerosynthx optimize` CLI command, mocking the underlying `StudyRunner` to keep the tests fast.
- **End-to-End Tests**:
    *   Add a skippable end-to-end test that runs a simple, real optimization study against XFOIL, verifying the final result.

---

## 6. Risks & Limitations

- **Combinatorial Explosion**: Grid search is exhaustive and can lead to a very large number of runs if the user defines a large design space. The documentation must clearly warn about this. For this phase, we will not implement any limits, but a future version could add a hard cap on the number of runs.
- **Synchronous API**: As with the `study` endpoint, the API for creating an optimization will be synchronous and will block until all underlying runs are complete. This is acceptable for now but will need to be addressed for larger problems.
- **Limited Objectives**: This phase will only implement a few simple objectives (e.g., max L/D). The engine should be designed to be easily extensible with new objective functions in the future.

---

## 7. Future Extensibility

- **Advanced Algorithms**: The `optimizer.engine` can be extended with more sophisticated, non-exhaustive search algorithms like Bayesian optimization or genetic algorithms for exploring continuous design spaces.
- **Multi-Objective Optimization**: The `OptimizationSpec` can be extended to support multiple competing objectives (e.g., maximize Cl and minimize Cm).
- **Constraints**: The spec could be updated to support constraints (e.g., "maximize Cl/Cd, but only for candidates where Cl > 0.8").
