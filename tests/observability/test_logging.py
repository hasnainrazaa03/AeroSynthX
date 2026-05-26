from __future__ import annotations

import io
import json
import logging

import pytest

from aerosynthx.observability import (
    bind_correlation_id,
    configure_logging,
    correlation_id_var,
)
from aerosynthx.observability.logging import JsonFormatter


def _capture_record(logger: logging.Logger, msg: str, **extra: object) -> dict[str, object]:
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info(msg, extra=extra)
    finally:
        logger.removeHandler(handler)
    return json.loads(buffer.getvalue())  # type: ignore[no-any-return]


def test_json_formatter_emits_basic_fields() -> None:
    payload = _capture_record(logging.getLogger("test.basic"), "hello")
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.basic"


def test_json_formatter_includes_extras() -> None:
    payload = _capture_record(logging.getLogger("test.extra"), "go", stage="parse", ms=12)
    assert payload["stage"] == "parse"
    assert payload["ms"] == 12


def test_correlation_id_propagates() -> None:
    with bind_correlation_id("abc123"):
        payload = _capture_record(logging.getLogger("test.cid"), "tagged")
    assert payload["correlation_id"] == "abc123"
    # Resets cleanly after the context.
    assert correlation_id_var.get() is None


def test_json_formatter_includes_exception_info() -> None:
    logger = logging.getLogger("test.exc")
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("kaput")
    finally:
        logger.removeHandler(handler)
    payload = json.loads(buffer.getvalue())
    assert "exc_info" in payload
    assert "ValueError" in payload["exc_info"]


def test_configure_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(json_format=True, level=logging.INFO)
    configure_logging(json_format=False, level=logging.DEBUG)
    logging.getLogger().info("plain")
    out = capsys.readouterr().out
    assert "plain" in out
    # Only one aerosynthx-tagged handler should remain.
    root = logging.getLogger()
    tagged = [h for h in root.handlers if getattr(h, "_aerosynthx_handler", False)]
    assert len(tagged) == 1
    # Restore default to avoid leaking into other tests.
    for h in list(root.handlers):
        if getattr(h, "_aerosynthx_handler", False):
            root.removeHandler(h)
