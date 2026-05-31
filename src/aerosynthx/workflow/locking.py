"""Per-run mutual exclusion for safe concurrent pipeline execution.

Two :meth:`aerosynthx.workflow.pipeline.Pipeline.run` calls for the same
design intent map to the same ``run_id`` and therefore the same on-disk
directory and database row. :class:`RunLockRegistry` hands out a
process-local lock per ``run_id`` so such calls serialize, while calls for
*different* runs proceed in parallel without contention.

Locks are reference-counted: the underlying lock object is created on first
use and removed once the last waiter releases it, so the registry never
accumulates one lock per distinct ``run_id`` for the lifetime of the
process.

Scope: this is *process-local* coordination only. Cross-process or
cross-host locking (advisory file locks, database row locks) is out of
scope.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field

from aerosynthx.observability import METRICS

_LOCK_WAIT_COUNTER = METRICS.counter(
    "aerosynthx_run_lock_waits_total",
    "Times a caller had to wait for a per-run lock already held elsewhere.",
)

LockFactory = Callable[[], AbstractContextManager[bool]]


def _default_lock_factory() -> AbstractContextManager[bool]:
    return threading.Lock()


@dataclass(slots=True)
class _Entry:
    """A per-key lock plus the number of callers referencing it."""

    lock: AbstractContextManager[bool]
    waiters: int = field(default=0)


class RunLockRegistry:
    """Reference-counted registry of per-key locks.

    Acquiring the same key from two threads serializes them; acquiring
    distinct keys never contends. Idle entries are reclaimed so the
    registry's memory footprint tracks *active* keys, not all keys ever
    seen.
    """

    def __init__(self, *, lock_factory: LockFactory | None = None) -> None:
        self._lock_factory: LockFactory = lock_factory or _default_lock_factory
        self._guard = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    @property
    def active_keys(self) -> frozenset[str]:
        """Keys with at least one current waiter or holder (test hook)."""
        with self._guard:
            return frozenset(self._entries)

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        """Block until the lock for ``key`` is held, then yield.

        On exit the lock is released and, when no other caller references
        the key, its entry is discarded.
        """
        entry, contended = self._checkout(key)
        if contended:
            _LOCK_WAIT_COUNTER.inc()
        with entry.lock:
            try:
                yield
            finally:
                self._return(key)

    def _checkout(self, key: str) -> tuple[_Entry, bool]:
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(lock=self._lock_factory())
                self._entries[key] = entry
            contended = entry.waiters > 0
            entry.waiters += 1
            return entry, contended

    def _return(self, key: str) -> None:
        with self._guard:
            entry = self._entries[key]
            entry.waiters -= 1
            if entry.waiters == 0:
                del self._entries[key]


#: Shared registry used by :class:`~aerosynthx.workflow.pipeline.Pipeline`
#: instances that do not supply their own, so separate pipelines pointed at
#: the same output root still serialize same-run work.
DEFAULT_RUN_LOCKS = RunLockRegistry()
