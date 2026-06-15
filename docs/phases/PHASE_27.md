# Phase 27 — Parametric Studies & Comparative Aerodynamic Analysis

Target release: `v1.20.0` (Tentative)
Status: **In progress**
Goal: Enable users to define and execute parametric studies, such as Reynolds number sweeps and multi-airfoil comparisons, and receive a structured, comparative analysis of the results.

---

## 1. Architectural Analysis

This phase introduces a new "meta-analysis" capability that orchestrates multiple single runs. The architecture will be extended as follows:

- **New `Study` Abstraction**: A "Study" will be a new top-level concept. A study will be defined by a set of base parameters and a list of variables to sweep over (e.g., a list of Reynolds numbers or a list of airfoil designations). This is a more powerful and flexible approach than adding more sweep types to the `DesignIntent`.
- **New `aerosynthx.study` Package**: A new package will be created to encapsulate all study-related logic, keeping it separate from the single-run pipeline.
  - `study.schemas`: Will define the `StudySpec` (the user's input) and the `StudyResult` (the aggregated output).
  - `study.runner`: Will contain a `StudyRunner` that takes a `StudySpec`, generates a list of `DesignIntent` objects, and executes them by calling the existing `Pipeline.run()` for each one.
- **Workflow Integration**: The `StudyRunner` will act as an orchestrator *above* the `Pipeline`. This maintains the clean separation of concerns, where the `Pipeline` is an expert at executing one run, and the `StudyRunner` is an expert at managing a batch of runs.
- **Persistence**: A new `studies` table will be added to the database to store the study definition and its overall status. The existing `runs` table will be modified to include a `study_id` foreign key, linking each run to its parent study.
- **API**: A new set of RESTful endpoints under `/api/v1/studies` will be created for creating, fetching, and managing studies and their results.
- **Reporting**: A new `render_study_report` function will generate a comparative HTML report, including tables and charts that plot the performance of all runs in the study against each other.

This design respects the existing architecture by adding a new orchestration layer rather than complicating the existing one.

---

## 2. Goals & Constraints

- **Goal**: Support Reynolds number sweeps for a single airfoil.
- **Goal**: Support comparing multiple different airfoils under the same flow conditions.
- **Goal**: Produce a single, comparative report for each study.
- **Constraint**: All study runs will be executed using the `xfoil` analysis mode. OpenFOAM studies are out of scope for this phase due to the high computational cost.
- **Constraint**: The existing single-run API and CLI must remain unchanged and fully functional.
- **Constraint**: The implementation must handle partial failures (e.g., if one run in a study fails, the others should still complete).

---

## 3. Implementation Plan

1.  **`aerosynthx.study.schemas`**:
    *   Create `StudySpec` with fields like `study_name`, `base_intent`, and a `variables` field to define the sweep (e.g., `{"reynolds_target": [1e6, 2e6, 3e6]}` or `{"airfoil": [{"family": "naca4", "designation": "0012"}, {"family": "naca5", "designation": "23012"}]}`).
    *   Create `StudyResult` to hold the study metadata and a list of the individual `RunResult` objects.
2.  **`aerosynthx.workflow.db`**:
    *   Add a `studies` table with `id`, `name`, `spec_json`, `status`, etc.
    *   Add a `study_id` column to the `runs` table with a foreign key relationship to the `studies` table.
3.  **`aerosynthx.study.runner`**:
    *   Create a `StudyRunner` class that takes a `StudySpec`.
    *   The `run()` method will:
        *   Create a `StudyRow` in the database.
        *   Generate the list of `DesignIntent` objects from the `StudySpec`.
        *   Loop through the intents, calling `pipeline.run()` for each one with `analysis_mode="xfoil"`.
        *   Update the `StudyRow` status upon completion.
4.  **`aerosynthx.study.report`**:
    *   Create a `render_study_report` function that takes a `StudyResult`.
    *   It will generate an HTML report with comparative plots (e.g., Cl vs. Alpha for all airfoils on one chart).
5.  **API (`aerosynthx.api.app`)**:
    *   Add a `POST /api/v1/studies` endpoint to create and run a new study.
    *   Add a `GET /api/v1/studies/{study_id}` endpoint to fetch the results of a completed study.
    *   Add a `GET /api/v1/studies/{study_id}/report` endpoint to get the comparative HTML report.
6.  **CLI (`aerosynthx.workflow.cli`)**:
    *   Add a new `aerosynthx study run` command that takes a JSON file or string as the `StudySpec`.

---

## 4. Acceptance Criteria

- [ ] A new `aerosynthx.study` package is created.
- [ ] The database schema is updated with `studies` table and `study_id` foreign key.
- [ ] A study with a Reynolds number sweep can be successfully executed.
- [ ] A study comparing multiple different airfoils can be successfully executed.
- [ ] The results of all individual runs within a study are correctly linked to the parent study in the database.
- [ ] The API provides endpoints for creating and retrieving studies.
- [ ] The CLI provides a `study run` command.
- [ ] A comparative HTML report can be generated for a completed study.
- [ ] All existing tests for single-run workflows pass without modification.

---

## 5. Testing Strategy

- **Unit Tests**:
    *   Test the `StudySpec` schema validation.
    *   Test the `StudyRunner`'s intent generation logic in isolation.
    *   Test the `render_study_report` function with mock `StudyResult` data.
- **Integration Tests**:
    *   Write integration tests for the new `/api/v1/studies` endpoints. These tests will use a mocked `Pipeline.run()` to avoid executing long-running processes.
    *   Write a CLI integration test for the `aerosynthx study run` command.
- **End-to-End Tests**:
    *   Add a skippable end-to-end test that defines a simple study (e.g., two airfoils at one AoA) and runs it against a real `xfoil` binary, verifying that the final database state and report are correct.

---

## 6. Risks & Limitations

- **Database Migrations**: This change modifies the `runs` table. As with the previous phase, this is a breaking change for existing databases. A proper migration system (like Alembic) is becoming increasingly necessary.
- **Long-Running Processes**: Studies can consist of many individual runs and may take a significant amount of time to complete. The current synchronous API endpoint for creating a study will block until the entire study is finished. For this phase, this is acceptable, but a future implementation should move to an asynchronous task queue model.
- **Error Handling**: If one run in a batch of 20 fails, the user needs clear feedback on what succeeded and what failed. The `StudyResult` and report must clearly present partial results.

---

## 7. Future Extensibility

- **Asynchronous Execution**: The `StudyRunner` could be refactored to use a task queue (like Celery) to execute runs in the background, allowing the API to return immediately with a study ID.
- **OpenFOAM Studies**: Once the platform supports asynchronous execution and is deployed in a scalable environment, the `analysis_mode` constraint could be lifted to allow for high-fidelity OpenFOAM-based studies.
- **Advanced Plotting**: The reporting can be enhanced with more advanced data visualizations, such as L/D ratio plots, Cm vs. Cl, and more.
