from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from aerosynthx.intent import DesignIntent, WingSpec, AirfoilSpec
from aerosynthx.workflow.cancellation import CancellationToken
from aerosynthx.workflow.db import RunRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.pipeline import Pipeline, load_run, query_runs
from aerosynthx.xfoil import XfoilResult

if TYPE_CHECKING:
    from aerosynthx.openfoam.runner import CommandRunner

_GOOD_INTENT = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."
_GOOD_INTENT_SWEEP = "NACA 0012 at 50 m/s, from 0 to 5 degrees alpha by 1 degree"
_OTHER_INTENT = "NACA 2412 at 65 m/s, alpha 3 deg, chord 1.0 m."
_WING_INTENT = "3D wing, span 10m, root NACA 0012 chord 1m, tip NACA 0012 chord 0.5m"


def test_run_happy_path_produces_all_stage_results(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)

    assert result.status == "completed"
    assert len(result.stages) == 5
    assert all(s.status == "ok" for s in result.stages)
    assert isinstance(result.intent, DesignIntent)
    assert result.flow_state is not None
    assert result.case_dir is not None and result.case_dir.exists()
    assert result.manifest_digest is not None
    run_json = tmp_path / "runs" / result.run_id / "run.json"
    assert run_json.exists()


@patch("aerosynthx.workflow.pipeline.generate_wing")
def test_run_wing_geometry_path(mock_generate_wing, tmp_path: Path) -> None:
    """Test that a wing intent runs the wing_geometry stage."""
    from aerosynthx.geometry.wing import Wing
    mock_generate_wing.return_value = Wing(span=10, root_chord=1, tip_chord=0.5, sweep_deg=0, dihedral_deg=0, twist_deg=0, root_airfoil=None, tip_airfoil=None, coordinates=(), metadata={})

    pipe = Pipeline(out_root=tmp_path)
    # This is a simplified intent for testing; the offline parser doesn't support wings yet.
    # We construct the DesignIntent manually.
    intent = DesignIntent(
        wing=WingSpec(
            span=10,
            root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
            tip_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=0.5),
        ),
        flow={"velocity_m_s": 50, "angle_of_attack_deg": 2.0},
        assumptions=[],
        provenance={"fields": {}},
    )

    # We need to bypass the text-based run method for this test
    run_id = "wing_run_123"
    from aerosynthx.intent import ParseResult
    with patch.object(pipe, "_parse_intent") as mock_parse:
        mock_parse.return_value = ParseResult(
            intent=intent, raw_input=_WING_INTENT, model="test", attempts=1
        )
        result = pipe.execute_run_sync(
            run_id,
            _WING_INTENT,
            execute=False,
            control=MagicMock(),
            emit=lambda *a, **kw: None,
        )

    assert result.status == "completed"
    stage_names = {s.name for s in result.stages}
    assert "wing_geometry" in stage_names
    assert "case" in stage_names
    assert "mesh" in stage_names
    mock_generate_wing.assert_called_once()


@patch("aerosynthx.workflow.pipeline.run_xfoil")
def test_run_xfoil_mode_single_point(mock_run_xfoil, tmp_path: Path) -> None:
    """Test the happy path for a single-point xfoil analysis."""
    mock_run_xfoil.return_value = [XfoilResult(alpha_deg=3.0, cl=0.5, cd=0.01, cm=-0.02)]
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT, analysis_mode="xfoil")

    assert result.status == "completed"
    assert result.xfoil_results is not None
    assert len(result.xfoil_results) == 1
    assert result.xfoil_results[0].cl == 0.5
    assert result.case_dir is None

    stage_names = {s.name for s in result.stages}
    assert "xfoil" in stage_names
    assert "case" not in stage_names

    with open_session(pipe.db_path) as session:
        row = session.get(RunRow, result.run_id)
        assert row is not None
        assert row.xfoil_result is not None
        import json
        data = json.loads(row.xfoil_result.polar_json)
        assert len(data) == 1
        assert data[0]["cl"] == 0.5


@patch("aerosynthx.workflow.pipeline.run_xfoil")
def test_run_xfoil_mode_sweep(mock_run_xfoil, tmp_path: Path) -> None:
    """Test the happy path for an xfoil sweep analysis."""
    mock_run_xfoil.return_value = [
        XfoilResult(alpha_deg=0.0, cl=0.0, cd=0.005, cm=0.0),
        XfoilResult(alpha_deg=1.0, cl=0.1, cd=0.006, cm=0.0),
    ]
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT_SWEEP, analysis_mode="xfoil")

    assert result.status == "completed"
    assert result.xfoil_results is not None
    assert len(result.xfoil_results) == 2
    assert result.xfoil_results[1].cl == 0.1

    with open_session(pipe.db_path) as session:
        row = session.get(RunRow, result.run_id)
        assert row is not None
        assert row.xfoil_result is not None
        import json
        data = json.loads(row.xfoil_result.polar_json)
        assert len(data) == 2
        assert data[1]["cl"] == 0.1


def test_run_persists_to_db(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    with open_session(pipe.db_path) as session:
        row = session.get(RunRow, result.run_id)
        assert row is not None
        assert row.status == "completed"
        assert len(row.stages) == 5


def test_run_is_resumable(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    first = pipe.run(_GOOD_INTENT)
    sentinel = first.case_dir / ".sentinel" if first.case_dir else None
    assert sentinel is not None
    sentinel.write_text("keep")

    second = pipe.run(_GOOD_INTENT)
    assert second.run_id == first.run_id
    assert second.status == "completed"
    assert sentinel.exists(), "resume must not re-execute the case stage"


def test_run_archives_case_into_store(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    assert result.case_dir is not None

    manifest_path = result.case_dir / "aerosynthx_manifest.json"
    import json
    manifest = json.loads(manifest_path.read_text())
    store = pipe.artifact_store
    for digest in manifest["files"].values():
        assert store.has(digest)

    blobs_before = store.stats().blobs
    pipe.run(_GOOD_INTENT, resume=False)
    assert store.stats().blobs == blobs_before


def test_injected_artifact_store_is_used(tmp_path: Path) -> None:
    from aerosynthx.workflow.artifacts import ContentAddressedStore
    store = ContentAddressedStore(tmp_path / "custom-blobs")
    pipe = Pipeline(out_root=tmp_path, artifact_store=store)
    assert pipe.artifact_store is store
    pipe.run(_GOOD_INTENT)
    assert store.stats().blobs > 0


def test_run_no_resume_re_executes(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    first = pipe.run(_GOOD_INTENT)
    sentinel = first.case_dir / ".sentinel" if first.case_dir else None
    assert sentinel is not None
    sentinel.write_text("keep")

    second = pipe.run(_GOOD_INTENT, resume=False)
    assert second.run_id == first.run_id
    assert not sentinel.exists(), "no-resume must rebuild the case dir"


def test_run_rejects_empty_intent(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    with pytest.raises(StageError) as excinfo:
        pipe.run("   ")
    assert excinfo.value.stage == "parse"


def test_run_records_parse_failure(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run("totally unparseable gibberish without numbers")
    assert result.status == "failed"
    parse_stage = next(s for s in result.stages if s.name == "parse")
    assert parse_stage.status == "failed"
    assert parse_stage.error
    later = [s for s in result.stages if s.name in {"compute", "case", "persist"}]
    assert all(s.status == "pending" for s in later)


def test_load_run_returns_none_for_missing(tmp_path: Path) -> None:
    assert load_run(tmp_path / "missing.db", "deadbeef") is None
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    assert load_run(pipe.db_path, "0000000000000000") is None


def test_load_run_returns_persisted(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    reloaded = load_run(pipe.db_path, result.run_id)
    assert reloaded is not None
    assert reloaded.run_id == result.run_id
    assert reloaded.intent is not None
    assert reloaded.flow_state is not None
    assert reloaded.status == "completed"
    assert reloaded.case_dir == result.case_dir
    assert reloaded.manifest_digest == result.manifest_digest


def test_load_run_restores_solve_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: True)
    holder: dict[str, Path] = {}
    pipe = Pipeline(out_root=tmp_path, command_runner=_coeff_runner(holder))
    result = pipe.run(_GOOD_INTENT, execute=True)
    reloaded = load_run(pipe.db_path, result.run_id)
    assert reloaded is not None
    assert reloaded.solve_result is not None
    assert reloaded.solve_result.ran is True
    assert reloaded.solve_result.converged is True


def test_load_run_ignores_corrupt_solve_json(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    assert result.case_dir is not None
    (result.case_dir.parent / "solve.json").write_text("{not json", encoding="utf-8")
    reloaded = load_run(pipe.db_path, result.run_id)
    assert reloaded is not None
    assert reloaded.solve_result is None


def test_query_runs_missing_db_is_empty(tmp_path: Path) -> None:
    page = query_runs(tmp_path / "missing.db")
    assert page.items == ()
    assert page.total == 0
    assert page.limit == 50
    assert page.offset == 0


def test_query_runs_returns_all_unfiltered(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    pipe.run(_OTHER_INTENT)
    page = query_runs(pipe.db_path)
    assert page.total == 2
    assert len(page.items) == 2


def test_query_runs_paginates_and_clamps(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    for velocity in (50, 55, 60):
        pipe.run(f"NACA 2412 at {velocity} m/s, alpha 3 deg, chord 1.0 m.")
    first = query_runs(pipe.db_path, limit=0, offset=-5)
    assert first.limit == 1
    assert first.offset == 0
    assert first.total == 3
    assert len(first.items) == 1
    second = query_runs(pipe.db_path, limit=2, offset=2)
    assert second.total == 3
    assert len(second.items) == 1


def test_query_runs_status_filter(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    pipe.run("totally unparseable gibberish without numbers")
    completed = query_runs(pipe.db_path, status="completed")
    assert completed.total == 1
    assert completed.items[0].status == "completed"
    failed = query_runs(pipe.db_path, status="failed")
    assert failed.total == 1
    assert failed.items[0].status == "failed"


def test_query_runs_search_matches_intent(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    pipe.run(_OTHER_INTENT)
    page = query_runs(pipe.db_path, q="65 M/S")
    assert page.total == 1
    assert "65 m/s" in page.items[0].intent_text


def test_run_id_normalises_whitespace(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    a = pipe.run(_GOOD_INTENT)
    b = pipe.run("  " + _GOOD_INTENT.replace(" ", "  ") + "  ")
    assert a.run_id == b.run_id


def test_relink_runs_noop_when_db_missing(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.relink_runs()
    assert (result.linked, result.bytes_reclaimed, result.skipped) == (0, 0, 0)


def test_relink_runs_links_then_idempotent(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    first = pipe.relink_runs()
    assert first.linked > 0
    assert first.bytes_reclaimed > 0
    second = pipe.relink_runs()
    assert second.linked == 0
    assert second.bytes_reclaimed == 0
    assert second.skipped > 0


def test_relink_runs_skips_missing_manifest(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    run = pipe.run(_GOOD_INTENT)
    assert run.case_dir is not None
    (run.case_dir / "aerosynthx_manifest.json").unlink()
    result = pipe.relink_runs()
    assert (result.linked, result.bytes_reclaimed, result.skipped) == (0, 0, 0)


def test_relink_runs_skips_rows_without_case_dir(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    with open_session(pipe.db_path) as session:
        for row in session.execute(select(RunRow)).scalars().all():
            row.case_dir = None
        session.commit()
    result = pipe.relink_runs()
    assert (result.linked, result.bytes_reclaimed, result.skipped) == (0, 0, 0)


def test_run_result_to_json_is_serialisable(tmp_path: Path) -> None:
    import json
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    blob = json.dumps(result.to_json())
    assert result.run_id in blob


def test_compute_stage_envelope_violation(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run("NACA 2412 at 110 m/s, alpha 0 deg, sea level.")
    assert result.status == "failed"
    compute = next(s for s in result.stages if s.name == "compute")
    assert compute.status == "failed"


def test_case_stage_failure_is_captured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerosynthx.openfoam.errors import OpenFoamError
    from aerosynthx.workflow import pipeline as pipe_mod
    def boom(*_a: object, **_k: object) -> None:
        raise OpenFoamError("case build failed", code="openfoam.case.broken")
    monkeypatch.setattr(pipe_mod, "build_case", boom)
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    assert result.status == "failed"
    case = next(s for s in result.stages if s.name == "case")
    assert case.status == "failed"
    persist = next(s for s in result.stages if s.name == "persist")
    assert persist.status == "pending"


def test_resume_skips_only_completed_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerosynthx.openfoam.errors import OpenFoamError
    from aerosynthx.workflow import pipeline as pipe_mod
    def boom(*_a: object, **_k: object) -> None:
        raise OpenFoamError("nope", code="openfoam.case.broken")
    monkeypatch.setattr(pipe_mod, "build_case", boom)
    pipe = Pipeline(out_root=tmp_path)
    first = pipe.run(_GOOD_INTENT)
    assert first.status == "failed"
    monkeypatch.undo()
    second = pipe.run(_GOOD_INTENT)
    assert second.status == "completed"
    assert second.run_id == first.run_id


def test_load_run_handles_failed_run_with_no_flow(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run("totally unparseable gibberish without numbers")
    assert result.status == "failed"
    reloaded = load_run(pipe.db_path, result.run_id)
    assert reloaded is not None
    assert reloaded.status == "failed"
    assert reloaded.flow_state is None


def test_run_handles_unexpected_stage_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aerosynthx.workflow import pipeline as pipe_mod
    def boom(_intent: object) -> None:
        raise RuntimeError("kaboom")
    monkeypatch.setattr(pipe_mod, "derive_flow_state", boom)
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    assert result.status == "failed"
    compute = next(s for s in result.stages if s.name == "compute")
    assert compute.status == "failed"
    assert "kaboom" in (compute.error or "")


def _valid_intent_payload() -> dict[str, object]:
    from aerosynthx.intent import parse_offline
    return parse_offline(_GOOD_INTENT).intent.model_dump(mode="json")


def test_run_uses_llm_client_when_provided(tmp_path: Path) -> None:
    from aerosynthx.intent import StaticLLMClient
    client = StaticLLMClient([_valid_intent_payload()])
    pipe = Pipeline(out_root=tmp_path, llm_client=client)
    result = pipe.run(_GOOD_INTENT, resume=False)
    assert result.status == "completed"
    assert client.calls, "LLM client should have been invoked"


def test_run_falls_back_to_offline_on_llm_failure(tmp_path: Path) -> None:
    from aerosynthx.intent import StaticLLMClient
    client = StaticLLMClient([{"not": "valid"}, {"still": "bad"}, {"nope": True}])
    pipe = Pipeline(out_root=tmp_path, llm_client=client)
    result = pipe.run(_GOOD_INTENT, resume=False)
    assert result.status == "completed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "ok"


def test_run_records_failure_when_llm_and_offline_both_fail(tmp_path: Path) -> None:
    from aerosynthx.intent import StaticLLMClient
    client = StaticLLMClient([{"bad": 1}, {"bad": 2}, {"bad": 3}])
    pipe = Pipeline(out_root=tmp_path, llm_client=client)
    result = pipe.run("totally unparseable gibberish", resume=False)
    assert result.status == "failed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "failed"


def _coeff_runner(case_dir_holder: dict[str, Path]) -> CommandRunner:
    from collections.abc import Sequence
    from aerosynthx.openfoam.runner import CommandResult
    log = (
        "smoothSolver:  Solving for Ux, Initial residual = 0.01\n"
        "SIMPLE solution converged in 1 iterations\n"
    )
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        case_dir_holder["cwd"] = cwd
        return CommandResult(command=tuple(command), returncode=0, stdout=log, stderr="")
    return runner


def test_run_execute_runs_solver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: True)
    holder: dict[str, Path] = {}
    pipe = Pipeline(out_root=tmp_path, command_runner=_coeff_runner(holder))
    result = pipe.run(_GOOD_INTENT, execute=True)
    assert result.status == "completed"
    assert result.solve_result is not None
    assert result.solve_result.converged is True
    assert len(result.stages) == 6
    solve = next(s for s in result.stages if s.name == "solve")
    assert solve.status == "ok"
    assert (tmp_path / "runs" / result.run_id / "solve.json").is_file()


def test_run_execute_skips_without_openfoam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: False)
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT, execute=True)
    assert result.status == "completed"
    assert result.solve_result is None
    solve = next(s for s in result.stages if s.name == "solve")
    assert solve.status == "skipped"


def test_run_execute_records_solver_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Sequence
    from aerosynthx.openfoam.runner import CommandResult
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: True)
    def failing(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        return CommandResult(command=tuple(command), returncode=1, stdout="", stderr="boom")
    pipe = Pipeline(out_root=tmp_path, command_runner=failing)
    result = pipe.run(_GOOD_INTENT, execute=True)
    assert result.status == "failed"
    solve = next(s for s in result.stages if s.name == "solve")
    assert solve.status == "failed"
    persist = next(s for s in result.stages if s.name == "persist")
    assert persist.status == "pending"


def test_run_execute_bypasses_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: False)
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    result = pipe.run(_GOOD_INTENT, execute=True)
    assert len(result.stages) == 6


class _FakeClock:
    def __init__(self, *values: float) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0
    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


def test_run_times_out_at_first_stage(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path, clock=_FakeClock(0.0, 100.0))
    result = pipe.run(_GOOD_INTENT, timeout=1.0)
    assert result.status == "failed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "failed"
    assert parse.error is not None and "RunTimeoutError" in parse.error
    later = [s for s in result.stages if s.name in {"compute", "case", "persist"}]
    assert all(s.status == "pending" for s in later)


def test_run_times_out_at_later_stage(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path, clock=_FakeClock(0.0, 0.0, 100.0))
    result = pipe.run(_GOOD_INTENT, timeout=1.0)
    assert result.status == "failed"
    assert next(s for s in result.stages if s.name == "parse").status == "ok"
    compute = next(s for s in result.stages if s.name == "compute")
    assert compute.status == "failed"
    assert compute.error is not None and "RunTimeoutError" in compute.error


def test_run_cancelled_fails_at_parse(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT, cancel_token=token)
    assert result.status == "failed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "failed"
    assert parse.error is not None and "RunCancelledError" in parse.error


def test_run_completes_with_generous_timeout(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path, clock=_FakeClock(0.0))
    result = pipe.run(_GOOD_INTENT, timeout=60.0)
    assert result.status == "completed"
    assert all(s.status == "ok" for s in result.stages)


def test_execute_caps_solver_timeout_to_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Sequence
    from aerosynthx.openfoam.runner import CommandResult
    from aerosynthx.workflow import pipeline as pipe_mod
    monkeypatch.setattr(pipe_mod, "openfoam_available", lambda: True)
    seen: dict[str, float] = {}
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        seen["timeout"] = timeout
        return CommandResult(command=tuple(command), returncode=0, stdout="", stderr="")
    pipe = Pipeline(out_root=tmp_path, command_runner=runner, clock=_FakeClock(0.0))
    result = pipe.run(_GOOD_INTENT, execute=True, timeout=30.0)
    assert result.status == "completed"
    assert seen["timeout"] == pytest.approx(30.0)


def test_delete_run_removes_record_and_artifacts(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    run_dir = tmp_path / "runs" / result.run_id
    assert run_dir.is_dir()
    assert pipe.delete_run(result.run_id) is True
    assert not run_dir.exists()
    assert load_run(pipe.db_path, result.run_id) is None


def test_delete_run_missing_returns_false(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    assert pipe.delete_run("ffffffffffffffff") is False


def test_delete_run_without_store_returns_false(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    assert pipe.delete_run("deadbeef") is False


def test_delete_run_cleans_orphan_directory(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)
    orphan = tmp_path / "runs" / "orphan00000000"
    orphan.mkdir(parents=True)
    (orphan / "stray.txt").write_text("x")
    assert pipe.delete_run("orphan00000000") is False
    assert not orphan.exists()


def test_concurrent_same_intent_builds_once(tmp_path: Path) -> None:
    import threading
    build_count = 0
    count_guard = threading.Lock()
    class _CountingPipeline(Pipeline):
        def execute_run_sync(self, *args: object, **kwargs: object):
            nonlocal build_count
            with count_guard:
                build_count += 1
            return super().execute_run_sync(*args, **kwargs)
    pipe = _CountingPipeline(out_root=tmp_path)
    start = threading.Barrier(2)
    results: list[object] = []
    results_guard = threading.Lock()
    def worker() -> None:
        start.wait()
        result = pipe.run(_GOOD_INTENT)
        with results_guard:
            results.append(result)
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert build_count == 1
    run_ids = {r.run_id for r in results}
    assert len(run_ids) == 1


def test_concurrent_distinct_intents_both_build(tmp_path: Path) -> None:
    import threading
    pipe = Pipeline(out_root=tmp_path)
    intents = [
        "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m.",
        "NACA 0012 at 40 m/s, alpha 5 deg, chord 0.5 m.",
    ]
    start = threading.Barrier(2)
    results: dict[str, object] = {}
    results_guard = threading.Lock()
    def worker(text: str) -> None:
        start.wait()
        result = pipe.run(text)
        with results_guard:
            results[text] = result
    threads = [threading.Thread(target=worker, args=(text,)) for text in intents]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert {r.status for r in results.values()} == {"completed"}
    assert len({r.run_id for r in results.values()}) == 2
