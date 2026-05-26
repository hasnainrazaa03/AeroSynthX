from __future__ import annotations

from pathlib import Path

from aerosynthx.workflow.db import RunRow, StageRow, init_db, open_session


def test_init_db_creates_file_and_schema(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "runs.db"
    init_db(db)
    assert db.exists()
    # Idempotent: second call must not raise.
    init_db(db)


def test_open_session_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "runs.db"
    init_db(db)
    with open_session(db) as session:
        session.add(
            RunRow(
                id="abc123",
                intent_text="hello",
                intent_json=None,
                flow_state_json=None,
                status="completed",
                case_dir=None,
                manifest_digest=None,
                created_at_iso="2026-01-01T00:00:00+00:00",
                completed_at_iso="2026-01-01T00:00:00+00:00",
                stages=[
                    StageRow(
                        ordinal=0,
                        name="parse",
                        status="ok",
                        duration_ms=5,
                        output_digest="d1",
                        error=None,
                    ),
                    StageRow(
                        ordinal=1,
                        name="compute",
                        status="ok",
                        duration_ms=1,
                        output_digest=None,
                        error=None,
                    ),
                ],
            )
        )

    with open_session(db) as session:
        row = session.get(RunRow, "abc123")
        assert row is not None
        assert [s.name for s in row.stages] == ["parse", "compute"]


def test_open_session_rolls_back_on_exception(tmp_path: Path) -> None:
    db = tmp_path / "runs.db"
    init_db(db)
    try:
        with open_session(db) as session:
            session.add(
                RunRow(
                    id="rollback",
                    intent_text="x",
                    intent_json=None,
                    flow_state_json=None,
                    status="completed",
                    case_dir=None,
                    manifest_digest=None,
                    created_at_iso="2026-01-01T00:00:00+00:00",
                    completed_at_iso=None,
                )
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with open_session(db) as session:
        assert session.get(RunRow, "rollback") is None
