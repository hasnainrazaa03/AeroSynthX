# Phase 22 — Run reports with physics charts

Version: `v1.15.0`

## Goal

Give every finished run a **standalone, downloadable HTML report** with inline
SVG charts summarising pipeline timing, derived aerodynamic quantities, and
(when the solver ran) force coefficients. Expose the report through the CLI,
the HTTP API, and the static UI so engineers can review or share results without
running the platform.

## Scope

### Report renderer (`workflow/report.py`)

- `render_run_report(result: RunResult) -> str` — self-contained HTML with
  zero external asset references.
- Sections: run header, stage-duration bar chart, design-intent table, flow-
  conditions table, derived-aerodynamics bar chart (Re, Mach, turbulence
  intensity), and solver results (force-coefficient chart when present, else
  a solver summary table, else a “not run” notice).
- HTML-escapes all user-provided text.

### Reload (`workflow/pipeline.py`)

- `_load_solve_result(case_dir)` reads `<run_dir>/solve.json` written by the
  opt-in solve stage.
- `load_run` / resume paths populate `RunResult.solve_result` so reports
  reflect persisted solver output.

### CLI (`workflow/cli.py`)

- `aerosynthx report RUN_ID --out DIR [--output FILE]` — writes HTML to a
  file or stdout.

### HTTP API (`api/app.py`)

- `GET /api/v1/runs/{run_id}/report` (requires the `read` scope) returns
  `text/html`.

### Static UI (`api/static/`)

- Run-history table gains a **Report** link per row.
- The result panel gains a **Download report** link after a run completes.

## Quality gates

- 100% line + branch coverage on the new module and endpoint branches.
- ruff (+format), mypy strict, pytest green.

## Out of scope

- PDF export, email delivery, embedded geometry PNGs, OpenTelemetry tracing.
