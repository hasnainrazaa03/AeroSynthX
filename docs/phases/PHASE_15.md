# Phase 15 — Concurrency: per-run locking for safe parallel runs

**Version:** `v1.8.0`
**Status:** In progress
**Theme:** Workflow & data — make `Pipeline.run` safe under concurrent
invocation.

## Problem

`Pipeline.run` is fully synchronous, but the FastAPI app and any
multi-threaded caller can invoke it concurrently. Two concerns arise:

1. **Same intent, concurrent runs.** Two requests with identical
   `intent_text` map to the same `run_id`, the same on-disk
   `runs/<run_id>/` directory, and the same `RunRow`. Running both at once
   races: both call `build_case(..., overwrite=True)` against the same
   `case/` directory and both `_persist` delete-then-insert the same row,
   risking corrupted artifacts and `IntegrityError`-style churn.
2. **Different intents, concurrent runs.** These touch disjoint
   directories and rows and *should* proceed in parallel with no
   serialization penalty.

We need fine-grained, per-`run_id` mutual exclusion: serialize work for a
given run while letting unrelated runs run freely.

## Goals

- A process-local **per-run lock registry** keyed by `run_id`.
- `Pipeline.run` acquires the lock for its `run_id` for the duration of a
  fresh (uncached) execution.
- The common case — a second caller for an already-`completed` intent —
  blocks only briefly, then returns the cached `RunResult` via the
  existing resume path (no duplicate work).
- Different `run_id`s never contend.
- Zero new runtime dependencies; pure `threading` primitives.
- Deterministic, fast unit tests using real threads with a barrier to
  force overlap.

## Non-goals

- Cross-process / cross-host locking (advisory file locks, DB row locks).
  Out of scope; documented as future work.
- Async execution / a job queue. The pipeline stays synchronous.
- Changing the resume semantics or public `run()` signature.

## Design

### `workflow/locking.py` (new)

```python
class RunLockRegistry:
    """Hands out a reentrant-free per-key lock, reference-counted so
    idle locks are garbage-collected."""

    def __init__(self, *, lock_factory: Callable[[], AbstractContextManager] | None = None): ...

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        """Block until the lock for ``key`` is held, yield, then release.
        The underlying lock object is created on first use and removed
        once the last holder releases it (so the registry does not leak
        one lock per distinct run_id forever)."""
```

- Backed by a guarding `threading.Lock` around a `dict[str, _Entry]`,
  where each `_Entry` holds the per-key `threading.Lock` plus a waiter
  count. On release, when the waiter count hits zero the entry is deleted.
- `lock_factory` is injectable so tests can substitute an instrumented
  lock and assert ordering deterministically.
- A `aerosynthx_run_lock_waits_total` counter increments whenever a caller
  has to wait for a lock already held (observability of contention).

### `Pipeline` integration

- `Pipeline.__init__` gains `lock_registry: RunLockRegistry | None = None`
  (defaults to a shared module-level registry so all `Pipeline` instances
  in a process that share an `out_root` serialize correctly; the API
  constructs `pipeline` and `llm_pipeline` separately but they share the
  same default registry).
- `run()` wraps the uncached execution: after the optional resume check,
  it acquires `self._locks.acquire(run_id)`, then **re-checks resume
  inside the lock** (double-checked locking) so a caller that queued
  behind a now-finished run returns the freshly cached result instead of
  rebuilding.

```python
if resume and not execute:
    cached = self._maybe_resume(run_id)
    if cached is not None:
        return cached

with self._locks.acquire(run_id):
    if resume and not execute:
        cached = self._maybe_resume(run_id)   # someone may have finished while we waited
        if cached is not None:
            return cached
    with bind_correlation_id(run_id):
        return self._run_uncached(run_id, intent_text, execute=execute, control=control)
```

`execute=True` runs still acquire the lock (so a fresh execute does not
race a normal run for the same intent) but never short-circuit on resume.

## Tests

`tests/workflow/test_locking.py` (new):

- `acquire` is mutually exclusive for the same key (two threads, shared
  counter, barrier-forced overlap → no interleaving).
- different keys run concurrently (both can be inside their critical
  sections at once; verified with a barrier that only releases when both
  threads are inside).
- entries are reclaimed after release (registry dict empty once idle).
- the contention counter increments when a second caller waits.
- injectable `lock_factory` is honoured.

`tests/workflow/test_pipeline.py` (additions):

- two threads calling `run()` with the **same** intent produce exactly
  one fresh build; the second returns the cached result (assert
  `_run_uncached` invoked once via a spy / build_case call count).
- two threads with **different** intents both build (no false
  serialization / correct independent results).

## Acceptance

- 100% line + branch coverage maintained.
- `ruff check`, `ruff format`, `mypy`, `pytest` all green.
- No new runtime dependencies.
- Public `run()` behaviour unchanged for single-threaded callers.
