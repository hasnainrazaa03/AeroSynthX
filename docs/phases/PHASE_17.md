# Phase 17 — Pipeline progress events

**Version:** `v1.10.0`
**Status:** In progress
**Theme:** Workflow & data — emit structured progress events *during*
`Pipeline.run`, the foundation for live progress surfaces.

## Problem

Phase 16 streams a run's stage timeline over SSE, but only by *replaying*
the already-persisted run after it finishes. There is no hook to observe a
run's stages as they execute. Live progress (and richer logging) needs the
pipeline to emit events at each stage boundary while it runs.

## Goals

- A typed **progress event** model and an injectable **sink** callback.
- `Pipeline.run(..., on_event=sink)` emits, in order:
  - `stage_started` before each stage executes,
  - `stage_finished` after each stage, carrying its `status` and
    `duration_ms`,
  - a single terminal `run_finished` event with the run's final status.
- Each event carries a monotonically increasing `sequence` so consumers
  can order/deduplicate.
- A **real consumer**: CLI `run --progress` prints each event to stderr as
  it happens, so the hook is exercised end-to-end (no dead code).
- The hook is opt-in and zero-cost when no sink is supplied (a shared
  no-op emitter), and thread-safe — the emitter is created per run and
  passed through call arguments, never stored on the instance (preserving
  the Phase 15 concurrency guarantees).
- Zero new runtime dependencies.

## Non-goals

- Wiring progress events into the HTTP SSE endpoint in real time (that
  needs background execution / a pub-sub bus; a later phase). The SSE
  endpoint keeps replaying the persisted timeline for now.
- Changing the persisted run shape or any existing endpoint.

## Design

### `workflow/progress.py` (new)

```python
ProgressKind = Literal["stage_started", "stage_finished", "run_finished"]

@dataclass(frozen=True, slots=True)
class ProgressEvent:
    sequence: int
    kind: ProgressKind
    run_id: str
    stage: str | None = None
    status: str | None = None
    duration_ms: int | None = None

ProgressSink = Callable[[ProgressEvent], None]
```

### `Pipeline` integration

- `run(..., on_event: ProgressSink | None = None)` forwards the sink.
- `_run_uncached` becomes a thin wrapper: it builds a per-run emitter
  (`_make_emitter(run_id, on_event)` — a closure owning an
  `itertools.count` sequence), delegates to the existing stage logic
  (renamed `_execute_run(..., emit=emit)`), emits the terminal
  `run_finished` with the result's status, and returns.
- `_StageRecorder`/`_timed(stage, emit)` emit `stage_started` on enter and
  `stage_finished` (with status + duration) on exit. `_solve_stage` takes
  and forwards `emit`.
- The internal emit callable has signature
  `(kind, stage, status, duration_ms) -> None`; a module-level
  `_noop_emit` is used when no sink is configured.

### CLI consumer

`run --progress` builds a sink that writes one line per event to stderr,
e.g. `progress: parse stage_finished ok (46ms)`, then prints the run JSON
to stdout as today.

## Tests

`tests/workflow/test_progress.py` (new):
- `ProgressEvent` construction / defaults,
- a collecting sink receives `stage_started`/`stage_finished` pairs for
  every stage plus one `run_finished`, in strictly increasing `sequence`
  order, with correct `status`/`duration_ms` shapes,
- a failed run still emits `run_finished` with `status="failed"`,
- no sink ⇒ no error and identical result (zero-cost path).

`tests/workflow/test_cli.py` (addition):
- `run --progress` writes progress lines to stderr and the run JSON to
  stdout.

## Acceptance

- 100% line + branch coverage maintained.
- `ruff check`, `ruff format`, `mypy`, `pytest` all green.
- No new runtime dependencies; existing behaviour unchanged when
  `on_event` is omitted.
