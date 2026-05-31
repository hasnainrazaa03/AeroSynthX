# Phase 14 — Run deletion + retention (v1.7.0)

## Goal

Round out the run lifecycle with a way to **delete** a run and reclaim its
artifacts. Until now runs only accumulate: there is no first-class way to
remove a record and its on-disk case directory. This phase adds run
deletion to the store, the CLI, and the HTTP API — the lowest-risk
remaining lifecycle gap before larger concurrency work.

Keeps project discipline: **zero new runtime dependencies**, deletion is
idempotent and path-safe, and 100% line + branch coverage.

## In scope

### Store / pipeline (`aerosynthx.workflow.pipeline`)
- `Pipeline.delete_run(run_id) -> bool`:
  - Removes the `RunRow` (its `StageRow` children cascade) when present.
  - Best-effort removes the run's directory tree
    (`<out_root>/runs/<run_id>`).
  - Returns `True` when a store record existed, `False` otherwise — so
    callers can distinguish "deleted" from "nothing to delete".

### API (`aerosynthx.api`)
- `DELETE /api/v1/runs/{run_id}` — requires the `run` scope:
  - `204 No Content` on success,
  - `404 Not Found` when no run with that id exists.

### CLI (`aerosynthx.workflow.cli`)
- `aerosynthx delete <run_id> --out <dir>`:
  - Exit `0` on success,
  - raises `RunNotFoundError` (non-zero) when the id is unknown, matching
    the existing `show` behaviour.

## Out of scope (future phases)
- Automatic time/space-based retention policies and scheduled cleanup.
- Bulk deletion or `DELETE /api/v1/runs` (all).
- Soft-delete / tombstones.

## Definition of done
- Deterministic tests for: delete an existing run (record + directory
  gone), delete a missing run (`False`, idempotent), delete when the store
  file is absent, and a directory-without-record cleanup branch; API
  `204`/`404`; CLI success and not-found paths.
- All gates green; version bumped to `1.7.0`; CHANGELOG + ROADMAP updated.
