"""Cooperative cancellation and wall-clock deadlines for pipeline runs.

The pipeline is synchronous, so a run is bounded *cooperatively*: a
:class:`RunControl` is checked at each stage boundary. When the run's
deadline has elapsed or its :class:`CancellationToken` has been tripped, the
in-flight stage fails fast with a stable, coded :class:`StageError`.

The wall clock is an injectable callable so timeout behaviour is fully
deterministic under test.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from aerosynthx.observability import METRICS
from aerosynthx.workflow.errors import RunCancelledError, RunTimeoutError

_INTERRUPT_COUNTER = METRICS.counter(
    "aerosynthx_runs_interrupted_total",
    "Pipeline runs aborted before completion, labelled by reason.",
    label_names=("reason",),
)


class CancellationToken:
    """Thread-safe, one-shot flag that callers trip to abort a run.

    A token is created un-cancelled. Calling :meth:`cancel` (idempotent)
    flips it permanently; the pipeline observes the change at the next stage
    boundary. Backed by :class:`threading.Event` so it can be tripped safely
    from another thread or a signal handler.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation; safe to call repeatedly."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """``True`` once :meth:`cancel` has been called."""
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class Deadline:
    """A monotonic wall-clock budget for a single run."""

    deadline: float | None
    clock: Callable[[], float]

    @classmethod
    def start(cls, timeout: float | None, *, clock: Callable[[], float] | None = None) -> Deadline:
        """Begin a budget of ``timeout`` seconds.

        ``timeout=None`` yields an unbounded deadline. A non-positive
        timeout is rejected with :class:`ValueError`.
        """
        monotonic = clock if clock is not None else time.monotonic
        if timeout is None:
            return cls(None, monotonic)
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        return cls(monotonic() + float(timeout), monotonic)

    @property
    def expired(self) -> bool:
        """``True`` once the budget has elapsed (always ``False`` if unbounded)."""
        if self.deadline is None:
            return False
        return self.clock() >= self.deadline

    def remaining(self) -> float | None:
        """Seconds left before expiry, or ``None`` when unbounded."""
        if self.deadline is None:
            return None
        return self.deadline - self.clock()


@dataclass(frozen=True, slots=True)
class RunControl:
    """A run's combined deadline + cancellation state."""

    deadline: Deadline
    token: CancellationToken | None

    @classmethod
    def create(
        cls,
        *,
        timeout: float | None,
        cancel_token: CancellationToken | None,
        clock: Callable[[], float] | None = None,
    ) -> RunControl:
        """Build control state from a timeout budget and optional token."""
        return cls(Deadline.start(timeout, clock=clock), cancel_token)

    def check(self, stage: str) -> None:
        """Raise if the run was cancelled or its deadline has elapsed.

        Cancellation takes precedence over a coincident timeout. Increments
        ``aerosynthx_runs_interrupted_total{reason}`` before raising.
        """
        if self.token is not None and self.token.cancelled:
            _INTERRUPT_COUNTER.inc(reason="cancelled")
            raise RunCancelledError("run was cancelled", stage=stage)
        if self.deadline.expired:
            _INTERRUPT_COUNTER.inc(reason="timeout")
            raise RunTimeoutError("run exceeded its time budget", stage=stage)

    def solver_timeout(self, default: float) -> float:
        """Per-command solver timeout, capped by the run's remaining budget."""
        remaining = self.deadline.remaining()
        if remaining is None:
            return default
        return min(default, max(remaining, 0.0))
