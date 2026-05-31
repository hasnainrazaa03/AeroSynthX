from __future__ import annotations

import json

from aerosynthx.api.sse import run_event_stream, sse_message
from aerosynthx.workflow.pipeline import RunResult, StageResult


def test_sse_message_minimal() -> None:
    assert sse_message("hello") == "data: hello\n\n"


def test_sse_message_all_fields() -> None:
    out = sse_message("payload", event="stage", event_id="3", retry_ms=2000)
    assert out == "event: stage\nid: 3\nretry: 2000\ndata: payload\n\n"


def test_sse_message_multiline_data() -> None:
    out = sse_message("line1\nline2", event="x")
    assert out == "event: x\ndata: line1\ndata: line2\n\n"


def _stage(name: str, status: str) -> StageResult:
    return StageResult(
        name=name,
        status=status,  # type: ignore[arg-type]
        duration_ms=1,
        output_digest=None,
        error=None,
    )


def test_run_event_stream_emits_stage_then_complete() -> None:
    result = RunResult(
        run_id="abc123",
        intent_text="x",
        status="completed",
        intent=None,
        flow_state=None,
        case_dir=None,
        manifest_digest=None,
        stages=(_stage("parse", "ok"), _stage("compute", "ok")),
    )

    blocks = list(run_event_stream(result))

    assert len(blocks) == 3
    assert blocks[0].startswith("event: stage\nid: 0\n")
    assert blocks[1].startswith("event: stage\nid: 1\n")
    assert blocks[2].startswith("event: complete\n")

    first_data = blocks[0].split("data: ", 1)[1].rsplit("\n\n", 1)[0]
    assert json.loads(first_data)["name"] == "parse"

    final_data = blocks[2].split("data: ", 1)[1].rsplit("\n\n", 1)[0]
    assert json.loads(final_data) == {"run_id": "abc123", "status": "completed"}
