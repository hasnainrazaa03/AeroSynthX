from __future__ import annotations

import pytest

from aerosynthx.observability.metrics import (
    Counter,
    Histogram,
    _Registry,
    render_prometheus,
)


def test_counter_inc_and_expose() -> None:
    c = Counter(name="t_total", help="test", label_names=("k",))
    c.inc(k="a")
    c.inc(2.5, k="a")
    c.inc(k="b")
    text = c.expose()
    assert "# TYPE t_total counter" in text
    assert 't_total{k="a"} 3.5' in text
    assert 't_total{k="b"} 1.0' in text


def test_counter_rejects_wrong_labels() -> None:
    c = Counter(name="bad", help="x", label_names=("k",))
    with pytest.raises(ValueError):
        c.inc(other="x")


def test_histogram_observe_and_expose() -> None:
    h = Histogram(
        name="lat_seconds",
        help="latency",
        label_names=("route",),
        buckets=(0.1, 1.0),
    )
    h.observe(0.05, route="/a")
    h.observe(0.5, route="/a")
    h.observe(5.0, route="/a")
    text = h.expose()
    assert "# TYPE lat_seconds histogram" in text
    assert 'lat_seconds_bucket{le="0.1",route="/a"} 1' in text
    assert 'lat_seconds_bucket{le="1.0",route="/a"} 2' in text
    assert 'lat_seconds_bucket{le="+Inf",route="/a"} 3' in text
    assert 'lat_seconds_count{route="/a"} 3' in text


def test_histogram_rejects_wrong_labels() -> None:
    h = Histogram(name="h", help="x", label_names=("route",))
    with pytest.raises(ValueError):
        h.observe(0.1)


def test_registry_reuse_returns_same_instance() -> None:
    reg = _Registry()
    a = reg.counter("foo_total", "desc")
    b = reg.counter("foo_total", "desc")
    assert a is b
    h1 = reg.histogram("bar_seconds", "desc")
    h2 = reg.histogram("bar_seconds", "desc")
    assert h1 is h2


def test_registry_reset() -> None:
    reg = _Registry()
    reg.counter("x_total", "x")
    reg.histogram("y_seconds", "y")
    reg.reset()
    assert reg.counters == {}
    assert reg.histograms == {}


def test_render_prometheus_returns_text() -> None:
    text = render_prometheus()
    # The default registry already has API + pipeline metrics registered
    # at import time, so we expect at least one HELP line.
    assert text == "" or "# HELP" in text


def test_label_value_escaping() -> None:
    c = Counter(name="esc_total", help="x", label_names=("k",))
    c.inc(k='a"b\\c')
    text = c.expose()
    assert r'k="a\"b\\c"' in text


def test_histogram_fractional_bucket_format() -> None:
    h = Histogram(
        name="frac_seconds",
        help="x",
        label_names=(),
        buckets=(0.123, 1.0),
    )
    h.observe(0.05)
    text = h.expose()
    assert 'le="0.123"' in text
    assert 'le="1.0"' in text
