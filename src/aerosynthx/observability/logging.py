"""Structured JSON logging with correlation-id propagation."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("aerosynthx_correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    _RESERVED = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a single JSON line."""
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = correlation_id_var.get()
        if cid:
            payload["correlation_id"] = cid
        # Forward any extra= fields, skipping LogRecord internals.
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(*, json_format: bool = True, level: int = logging.INFO) -> None:
    """Install a single stdout handler with the chosen formatter.

    Idempotent: replaces any prior handlers installed by this function.
    """
    root = logging.getLogger()
    root.setLevel(level)
    # Remove handlers we previously installed (tagged with a marker
    # attribute) so repeat calls do not stack up duplicate handlers.
    for h in list(root.handlers):
        if getattr(h, "_aerosynthx_handler", False):
            root.removeHandler(h)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler._aerosynthx_handler = True  # type: ignore[attr-defined]
    handler.setLevel(level)
    handler.setFormatter(
        JsonFormatter()
        if json_format
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(handler)


@contextmanager
def bind_correlation_id(correlation_id: str) -> Iterator[str]:
    """Bind ``correlation_id`` to the current context for its lifetime."""
    token = correlation_id_var.set(correlation_id)
    try:
        yield correlation_id
    finally:
        correlation_id_var.reset(token)
