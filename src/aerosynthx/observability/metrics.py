"""Tiny zero-dependency metrics registry with Prometheus text output."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Final


def _label_signature(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(labels.items()))


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{_escape(v)}"' for k, v in labels]
    return "{" + ",".join(parts) + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


@dataclass
class Counter:
    """Monotonic counter, labelled."""

    name: str
    help: str
    label_names: tuple[str, ...] = ()
    _values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        """Increment the counter for ``labels`` by ``amount``."""
        self._check(labels)
        key = _label_signature(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def _check(self, labels: dict[str, str]) -> None:
        if set(labels) != set(self.label_names):
            raise ValueError(
                f"counter {self.name!r} expects labels {self.label_names}, got {tuple(labels)}"
            )

    def expose(self) -> str:
        """Return the Prometheus text representation for this counter."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            items = list(self._values.items())
        for key, value in sorted(items):
            lines.append(f"{self.name}{_format_labels(key)} {value}")
        return "\n".join(lines)


_DEFAULT_BUCKETS: Final[tuple[float, ...]] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


@dataclass
class Histogram:
    """Cumulative histogram with configurable bucket bounds (seconds)."""

    name: str
    help: str
    label_names: tuple[str, ...] = ()
    buckets: tuple[float, ...] = _DEFAULT_BUCKETS
    _bucket_counts: dict[tuple[tuple[str, str], ...], list[int]] = field(default_factory=dict)
    _sums: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    _counts: dict[tuple[tuple[str, str], ...], int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float, **labels: str) -> None:
        """Record ``value`` (typically seconds) for ``labels``."""
        self._check(labels)
        key = _label_signature(labels)
        with self._lock:
            counts = self._bucket_counts.setdefault(key, [0] * len(self.buckets))
            for i, ub in enumerate(self.buckets):
                if value <= ub:
                    counts[i] += 1
            self._sums[key] = self._sums.get(key, 0.0) + value
            self._counts[key] = self._counts.get(key, 0) + 1

    def _check(self, labels: dict[str, str]) -> None:
        if set(labels) != set(self.label_names):
            raise ValueError(
                f"histogram {self.name!r} expects labels {self.label_names}, got {tuple(labels)}"
            )

    def expose(self) -> str:
        """Return the Prometheus text representation for this histogram."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            keys = sorted(self._counts)
            for key in keys:
                counts = self._bucket_counts[key]
                for ub, c in zip(self.buckets, counts, strict=True):
                    label_dict = dict(key)
                    label_dict["le"] = _fmt_bound(ub)
                    lines.append(
                        f"{self.name}_bucket{_format_labels(_label_signature(label_dict))} {c}"
                    )
                label_dict = dict(key)
                label_dict["le"] = "+Inf"
                lines.append(
                    f"{self.name}_bucket{_format_labels(_label_signature(label_dict))} "
                    f"{self._counts[key]}"
                )
                lines.append(f"{self.name}_sum{_format_labels(key)} {self._sums[key]}")
                lines.append(f"{self.name}_count{_format_labels(key)} {self._counts[key]}")
        return "\n".join(lines)


def _fmt_bound(value: float) -> str:
    if value == int(value):
        return f"{value:.1f}"
    return f"{value}"


@dataclass
class _Registry:
    counters: dict[str, Counter] = field(default_factory=dict)
    histograms: dict[str, Histogram] = field(default_factory=dict)

    def counter(self, name: str, help: str, label_names: tuple[str, ...] = ()) -> Counter:
        existing = self.counters.get(name)
        if existing is not None:
            return existing
        c = Counter(name=name, help=help, label_names=label_names)
        self.counters[name] = c
        return c

    def histogram(
        self,
        name: str,
        help: str,
        label_names: tuple[str, ...] = (),
        buckets: tuple[float, ...] = _DEFAULT_BUCKETS,
    ) -> Histogram:
        existing = self.histograms.get(name)
        if existing is not None:
            return existing
        h = Histogram(name=name, help=help, label_names=label_names, buckets=buckets)
        self.histograms[name] = h
        return h

    def reset(self) -> None:
        """Drop all registered metrics (used by tests)."""
        self.counters.clear()
        self.histograms.clear()


METRICS = _Registry()


def render_prometheus() -> str:
    """Render the default registry as a Prometheus text payload."""
    parts: list[str] = []
    for c in METRICS.counters.values():
        parts.append(c.expose())
    for h in METRICS.histograms.values():
        parts.append(h.expose())
    return "\n".join(parts) + ("\n" if parts else "")
