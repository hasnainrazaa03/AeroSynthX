"""Server-Sent Events (SSE) framing helpers for the run-events endpoint.

These helpers are pure and synchronous so they can be unit-tested without
a running server. :func:`sse_message` renders a single spec-compliant SSE
block; :func:`run_event_stream` replays a persisted run's stage timeline as
a sequence of such blocks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict

from aerosynthx.workflow.pipeline import RunResult


def sse_message(
    data: str,
    *,
    event: str | None = None,
    event_id: str | None = None,
    retry_ms: int | None = None,
) -> str:
    """Render one SSE message block.

    The block ends with a blank line, per the SSE wire format. Multi-line
    ``data`` is emitted as one ``data:`` field per line so embedded
    newlines survive transport.

    Args:
        data: The event payload (typically a JSON string).
        event: Optional event name (``event:`` field).
        event_id: Optional event id (``id:`` field).
        retry_ms: Optional client reconnection hint in milliseconds.

    Returns:
        The fully framed SSE block including its terminating blank line.
    """
    lines: list[str] = []
    if event is not None:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    if retry_ms is not None:
        lines.append(f"retry: {retry_ms}")
    for chunk in data.split("\n"):
        lines.append(f"data: {chunk}")
    return "\n".join(lines) + "\n\n"


def run_event_stream(result: RunResult) -> Iterator[str]:
    """Yield SSE blocks replaying ``result``'s stage timeline.

    Emits one ``stage`` event per :class:`~aerosynthx.workflow.StageResult`
    (in order), then a terminal ``complete`` event carrying the run's id and
    final status.
    """
    for index, stage in enumerate(result.stages):
        payload = json.dumps(asdict(stage), sort_keys=True)
        yield sse_message(payload, event="stage", event_id=str(index))
    final = json.dumps({"run_id": result.run_id, "status": result.status}, sort_keys=True)
    yield sse_message(final, event="complete")
