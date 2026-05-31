"""Structured progress events emitted during :class:`Pipeline.run`.

A :class:`ProgressEvent` is produced at each stage boundary and once when
the run finishes. Consumers supply a :data:`ProgressSink` callback to
observe a run live (CLI progress output, logging, future live streaming).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ProgressKind = Literal["stage_started", "stage_finished", "run_finished"]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """One progress notification emitted during a pipeline run.

    Attributes:
        sequence: Monotonic per-run counter starting at 0, so consumers can
            order and deduplicate events.
        kind: The event type.
        run_id: The run this event belongs to.
        stage: Stage name for ``stage_started`` / ``stage_finished`` events;
            ``None`` for ``run_finished``.
        status: Stage or run outcome (e.g. ``"ok"``, ``"failed"``,
            ``"completed"``); ``None`` for ``stage_started``.
        duration_ms: Stage wall time in milliseconds for ``stage_finished``;
            ``None`` otherwise.
    """

    sequence: int
    kind: ProgressKind
    run_id: str
    stage: str | None = None
    status: str | None = None
    duration_ms: int | None = None


ProgressSink = Callable[[ProgressEvent], None]
