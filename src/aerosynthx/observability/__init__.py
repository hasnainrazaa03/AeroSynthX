"""Operability primitives: structured logging + lightweight metrics.

This package intentionally has zero external dependencies. The metrics
registry implements just enough of the Prometheus text-exposition
format to be scraped by a standard Prometheus server.
"""

from __future__ import annotations

from aerosynthx.observability.logging import (
    bind_correlation_id,
    configure_logging,
    correlation_id_var,
)
from aerosynthx.observability.metrics import (
    METRICS,
    Counter,
    Histogram,
    render_prometheus,
)

__all__ = [
    "METRICS",
    "Counter",
    "Histogram",
    "bind_correlation_id",
    "configure_logging",
    "correlation_id_var",
    "render_prometheus",
]
