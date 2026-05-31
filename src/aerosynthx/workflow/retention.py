"""Automatic retention & cleanup policy for runs and store blobs.

Runs accumulate without bound: each leaves a case tree under
``runs/<run_id>/``, a row in the SQLite store, and (via Phase 18) blobs in
the shared content-addressed store. This module provides the *policy* layer
that caps that growth:

- :func:`PruneResult` / :func:`GarbageCollectResult` describe the outcome of
  a pruning pass and a blob garbage-collection pass.
- The actual selection logic lives on :class:`aerosynthx.workflow.pipeline.Pipeline`
  (``prune_runs`` / ``collect_garbage``); this module owns only the typed
  results and the observability counters so the policy stays decoupled from
  storage details.
"""

from __future__ import annotations

from dataclasses import dataclass

from aerosynthx.observability import METRICS

_RUNS_PRUNED = METRICS.counter(
    "aerosynthx_runs_pruned_total",
    "Runs deleted by the retention pruning policy.",
)
_BLOBS_COLLECTED = METRICS.counter(
    "aerosynthx_blobs_collected_total",
    "Unreferenced store blobs removed by garbage collection.",
)


@dataclass(frozen=True, slots=True)
class PruneResult:
    """Outcome of a :meth:`Pipeline.prune_runs` pass.

    Attributes:
        deleted: Run ids removed, in the newest-first order they were
            selected.
        kept: Number of runs left in the store afterwards.
    """

    deleted: tuple[str, ...]
    kept: int

    @property
    def count(self) -> int:
        """Number of runs deleted (``len(deleted)``)."""
        return len(self.deleted)


@dataclass(frozen=True, slots=True)
class GarbageCollectResult:
    """Outcome of a :meth:`Pipeline.collect_garbage` pass.

    Attributes:
        collected: Number of unreferenced blobs removed.
        freed_bytes: Total bytes reclaimed by removing those blobs.
        kept: Number of blobs still referenced and retained.
    """

    collected: int = 0
    freed_bytes: int = 0
    kept: int = 0
