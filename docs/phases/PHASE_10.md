# Phase 10 — OpenFOAM Solver Execution (`v1.3.0`)

## Goal

Turn a generated case directory into **actual solver output** by adding an
**opt-in** execution harness that shells out to `blockMesh` and
`simpleFoam`, captures their logs, and parses convergence residuals and
(when present) force coefficients (Cl/Cd/Cm). Execution only happens when
the operator opts in *and* an OpenFOAM toolchain is detected; the default
behaviour (case generation only) is unchanged.

The process boundary is isolated behind an injectable `CommandRunner`
callable so the entire harness — including residual/coefficient parsing —
is unit-testable without OpenFOAM installed.

This closes the **P1 "Actually run solvers"** item from the roadmap.

## In scope

1. `aerosynthx.openfoam.runner` (zero new runtime deps):
   - `openfoam_available(env=None)` — `True` when `WM_PROJECT_DIR` is set
     and the solver apps resolve on `PATH`.
   - `CommandRunner` protocol + `CommandResult`; `default_command_runner`
     wraps `subprocess.run` (the only un-unit-tested line, by design).
   - `run_case(case_dir, *, runner, timeout=...)` — runs `blockMesh` then
     `simpleFoam`, writes `log.<app>`, and returns a `SolveResult`.
   - `parse_residuals(text)` and `parse_force_coefficients(text)` pure
     functions.
   - `SolveResult` (ran, converged, iterations, final_residual,
     coefficients, commands).
   - `OpenFoamNotAvailableError`, `SolverExecutionError`.
2. Pipeline: `Pipeline(..., command_runner=None)` and a new **opt-in**
   `solve` stage. `run(..., execute=False)`. When `execute=True`:
   - toolchain present → run the solver, attach `SolveResult`;
   - toolchain absent → stage recorded as **skipped** (run still
     completes);
   - solver failure → stage **failed** (run fails, like any other stage).
   `execute=True` always runs fresh (bypasses resume).
3. CLI: `aerosynthx run --execute`.
4. API: `POST /api/v1/runs` accepts an optional `execute` flag.
5. Metrics: `aerosynthx_solver_runs_total{status}`
   (status ∈ {ok, skipped, failed}).
6. Artifacts: `solve.json` in the run dir; `solve` block in `run.json`.

## Out of scope (future)

- Body-fitted meshing around the airfoil (the bundled `blockMesh` domain
  is a rectangular far-field box; force coefficients therefore require a
  future meshing phase to be physically meaningful).
- Persisting `SolveResult` into the SQLite schema (kept in artifacts).
- Parallel (`mpirun`) execution and HPC schedulers.
- Live residual streaming.

## Public surface

```python
from aerosynthx.openfoam import (
    SolveResult,
    openfoam_available,
    run_case,
    default_command_runner,
    parse_residuals,
    parse_force_coefficients,
)
```

## Definition of done

- 100% line + branch coverage on new code (process boundary mocked).
- `ruff check`, `ruff format --check`, `mypy`, full `pytest` green.
- Version bumped to `1.3.0`, CHANGELOG updated, tagged `v1.3.0`, pushed.
