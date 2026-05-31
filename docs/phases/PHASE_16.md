# Phase 16 — SSE streaming of run stage timeline

**Version:** `v1.9.0`
**Status:** In progress
**Theme:** API & UI — let clients consume a run's stage timeline over a
streaming transport instead of a single JSON blob.

## Problem

Today a client learns a run's outcome only by polling
`GET /api/v1/runs/{id}` and reading the full `stages` array at once. There
is no streaming transport, so a UI cannot render the stage timeline
progressively, and there is no foundation for live progress in future
phases.

## Goals

- A new **Server-Sent Events** endpoint:
  `GET /api/v1/runs/{run_id}/events` (media type `text/event-stream`).
- Emit one `stage` event per persisted `StageResult`, in order, each
  carrying that stage's JSON (`name`, `status`, `duration_ms`,
  `output_digest`, `error`), followed by a terminal `complete` event with
  the run's final `run_id` and `status`.
- Correct SSE framing (`event:` / `data:` / blank-line terminator),
  guarded with `Cache-Control: no-cache` and `X-Accel-Buffering: no` so
  proxies do not buffer the stream.
- `404` for unknown runs (consistent with the other run endpoints), behind
  the existing `read` scope.
- Pure standard library + Starlette's `StreamingResponse`; **zero new
  runtime dependencies**.

## Non-goals

- Live, mid-execution progress events (the pipeline is synchronous and a
  persisted run is already complete). The endpoint replays the persisted
  timeline as a stream; true live progress is a later phase that would
  emit events *during* `Pipeline.run`.
- WebSockets. SSE is sufficient for unidirectional server→client
  streaming and needs no extra dependency.

## Design

### `api/sse.py` (new)

A tiny, pure SSE-framing helper, fully unit-testable without a server.

```python
def sse_message(
    data: str,
    *,
    event: str | None = None,
    event_id: str | None = None,
    retry_ms: int | None = None,
) -> str:
    """Render one SSE message block (fields + blank-line terminator).

    Multi-line ``data`` is split into one ``data:`` field per line, per
    the SSE spec."""

def run_event_stream(result: RunResult) -> Iterator[str]:
    """Yield SSE blocks: one ``stage`` event per stage, then ``complete``."""
```

`run_event_stream` serialises each `StageResult` via `dataclasses.asdict`
+ `json.dumps(sort_keys=True)` for the `stage` events, and a small
`{"run_id", "status"}` payload for the final `complete` event.

### `api/app.py` integration

```python
@app.get("/api/v1/runs/{run_id}/events", tags=["runs"], dependencies=[auth_read])
def stream_run_events(run_id: str) -> StreamingResponse:
    result = load_run(pipeline.db_path, run_id)
    if result is None:
        raise HTTPException(404, ...)
    return StreamingResponse(
        run_event_stream(result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

## Tests

`tests/api/test_sse.py` (new) — pure helper coverage:
- single-line and multi-line `data` framing,
- optional `event`, `id`, `retry` fields included only when given,
- `run_event_stream` yields N `stage` blocks + 1 `complete` block in order,
  carrying the right payloads, for a representative `RunResult`.

`tests/api/test_app.py` (additions):
- `GET /runs/{id}/events` returns `200`, `text/event-stream`, the
  `no-cache` / `X-Accel-Buffering` headers, and a body containing the
  stage events and a trailing `complete` event.
- unknown run id → `404`.
- the endpoint requires the `read` scope (401/403 when keys configured).

## Acceptance

- 100% line + branch coverage maintained.
- `ruff check`, `ruff format`, `mypy`, `pytest` all green.
- No new runtime dependencies.
- Existing endpoints unchanged.
