from __future__ import annotations

from pathlib import Path

from aerosynthx.intent import IntentError, ParseResult
from aerosynthx.workflow.pipeline import Pipeline
from aerosynthx.workflow.progress import ProgressEvent

_GOOD_INTENT = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


def test_progress_event_defaults() -> None:
    event = ProgressEvent(sequence=0, kind="run_finished", run_id="abc")
    assert event.stage is None
    assert event.status is None
    assert event.duration_ms is None


def test_run_emits_started_finished_pairs_and_run_finished(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    events: list[ProgressEvent] = []
    result = pipe.run(_GOOD_INTENT, on_event=events.append)

    # Sequences are monotonic from zero.
    assert [e.sequence for e in events] == list(range(len(events)))
    assert all(e.run_id == result.run_id for e in events)

    started = [e for e in events if e.kind == "stage_started"]
    finished = [e for e in events if e.kind == "stage_finished"]
    run_finished = [e for e in events if e.kind == "run_finished"]

    # One started + one finished per completed stage.
    assert len(started) == len(result.stages)
    assert len(finished) == len(result.stages)
    assert [e.stage for e in started] == [s.name for s in result.stages]
    for fin, stage in zip(finished, result.stages, strict=True):
        assert fin.stage == stage.name
        assert fin.status == stage.status
        assert fin.duration_ms == stage.duration_ms

    # Exactly one terminal run_finished carrying the run status, emitted last.
    assert len(run_finished) == 1
    assert events[-1].kind == "run_finished"
    assert events[-1].status == result.status
    assert events[-1].stage is None


def test_failed_run_still_emits_run_finished(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)

    def _boom(_text: str) -> ParseResult:
        raise IntentError("nope")

    pipe._parse_intent = _boom  # type: ignore[assignment]
    events: list[ProgressEvent] = []
    result = pipe.run("anything", on_event=events.append)

    assert result.status == "failed"
    assert events[-1].kind == "run_finished"
    assert events[-1].status == "failed"
    # The failed parse stage emitted a started + finished(failed) pair.
    assert events[0].kind == "stage_started"
    assert events[1].kind == "stage_finished"
    assert events[1].status == "failed"


def test_no_sink_path_is_silent_and_identical(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    with_none = pipe.run(_GOOD_INTENT, on_event=None)
    # A second resume-bypassed run produces an equivalent result without error.
    again = pipe.run(_GOOD_INTENT, resume=False)
    assert with_none.status == "completed"
    assert again.status == "completed"
    assert [s.name for s in with_none.stages] == [s.name for s in again.stages]
