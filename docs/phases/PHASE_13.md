# Phase 13 — Run cancellation + timeout enforcement (v1.6.0)

## Goal

Give every pipeline run a **wall-clock budget** and a **cooperative
cancellation** hook so a run can be bounded in time and stopped cleanly
instead of running unbounded. This is the strongest remaining **P1** under
*Workflow & data*:

> Run cancellation + timeout enforcement.

The pipeline is synchronous, so enforcement is *cooperative*: a lightweight
control object is checked at each stage boundary. When the deadline has
elapsed or a cancellation token has been tripped, the in-flight stage fails
fast and the run finalises with `status="failed"` (the failed stage carries
a stable code — `workflow.run.timeout` or `workflow.run.cancelled`). The
opt-in solver stage additionally caps its per-command subprocess timeout to
the run's remaining budget so a hung solver can never outlive the run.

Keeps project discipline: **zero new runtime dependencies**, the clock is an
injectable callable so timeout behaviour is fully deterministic under test,
and 100% line + branch coverage.

## In scope

### New module `aerosynthx.workflow.cancellation`
- `CancellationToken` — thread-safe one-shot flag (`threading.Event`):
  `cancel()` (idempotent) and a `cancelled` property. Safe to trip from
  another thread / signal handler.
- `Deadline` (frozen dataclass) — a monotonic budget built from an
  injectable `clock`:
  - `Deadline.start(timeout, *, clock=None)` → unbounded when `timeout is
    None`; raises `ValueError` when `timeout <= 0`.
  - `expired` property and `remaining()` (`None` when unbounded).
- `RunControl` (frozen dataclass) wrapping a `Deadline` + optional
  `CancellationToken`:
  - `RunControl.create(*, timeout, cancel_token, clock=None)`.
  - `check(stage)` raises `RunCancelledError` (cancel wins) or
    `RunTimeoutError` (deadline) — incrementing
    `aerosynthx_runs_interrupted_total{reason}` first.
  - `solver_timeout(default)` → `default` when unbounded, else the remaining
    budget capped at `default`.

### Errors (`aerosynthx.workflow.errors`)
- `RunTimeoutError(StageError)` — `code = "workflow.run.timeout"`.
- `RunCancelledError(StageError)` — `code = "workflow.run.cancelled"`.

### Metric
- `aerosynthx_runs_interrupted_total{reason}` counter,
  `reason ∈ {timeout, cancelled}`.

### Pipeline (`aerosynthx.workflow.pipeline`)
- `Pipeline.__init__` gains `clock: Callable[[], float] | None = None`
  (default `time.monotonic`).
- `Pipeline.run(..., timeout: float | None = None,
  cancel_token: CancellationToken | None = None)`.
- `_run_uncached` builds a `RunControl` and calls `control.check(stage)` as
  the first statement inside each timed stage block for **parse, compute,
  geometry, case, solve** (not *persist* — bookkeeping always completes).
  A raised interrupt is caught by the existing `_StageRecorder`, recorded as
  a failed stage, and the existing finalise path returns a failed run.
- `_solve_stage` accepts the `RunControl` and passes
  `control.solver_timeout(600.0)` to `run_case`.

### API (`aerosynthx.api`)
- `RunRequest.timeout_seconds: float | None` (optional, `> 0`).
- `create_run` forwards `timeout=body.timeout_seconds` to `Pipeline.run`.

### CLI (`aerosynthx.workflow.cli`)
- `aerosynthx run --timeout SECONDS` (float) forwarded to `Pipeline.run`.

### Exports
- `CancellationToken`, `Deadline`, `RunControl`, `RunTimeoutError`,
  `RunCancelledError` exported from `aerosynthx.workflow`.

## Out of scope (future phases)
- Asynchronous/background run execution and an HTTP cancel endpoint
  (`POST /runs/{id}/cancel`) — meaningful only once runs execute off the
  request thread (a later concurrency phase).
- Signal-handler wiring of `SIGINT` to a token in the CLI.
- Run deletion / retention (next phase).

## Definition of done
- Deterministic tests (injected fake clock) for: deadline not expired,
  deadline expired aborts the next stage, pre-cancelled token aborts the
  first stage, cancel-wins-over-timeout precedence, `solver_timeout`
  capping, `Deadline.start` validation, and the API/CLI timeout plumbing.
- All gates green; version bumped to `1.6.0`; CHANGELOG + ROADMAP updated.
