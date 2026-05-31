from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from aerosynthx.intent import DesignIntent
from aerosynthx.workflow.cancellation import CancellationToken
from aerosynthx.workflow.db import RunRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.pipeline import Pipeline, load_run

if TYPE_CHECKING:
    from aerosynthx.openfoam.runner import CommandRunner

_GOOD_INTENT = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


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
    # Mutate the case dir to detect re-execution.
    sentinel = first.case_dir / ".sentinel" if first.case_dir else None
    assert sentinel is not None
    sentinel.write_text("keep")

    second = pipe.run(_GOOD_INTENT)
    assert second.run_id == first.run_id
    assert second.status == "completed"
    assert sentinel.exists(), "resume must not re-execute the case stage"


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
    # Later stages must be marked pending.
    later = [s for s in result.stages if s.name in {"compute", "case", "persist"}]
    assert all(s.status == "pending" for s in later)


def test_load_run_returns_none_for_missing(tmp_path: Path) -> None:
    assert load_run(tmp_path / "missing.db", "deadbeef") is None
    # Now create db but no row.
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


def test_run_id_normalises_whitespace(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    a = pipe.run(_GOOD_INTENT)
    b = pipe.run("  " + _GOOD_INTENT.replace(" ", "  ") + "  ")
    assert a.run_id == b.run_id


def test_run_result_to_json_is_serialisable(tmp_path: Path) -> None:
    import json

    pipe = Pipeline(out_root=tmp_path)
    result = pipe.run(_GOOD_INTENT)
    blob = json.dumps(result.to_json())
    assert result.run_id in blob


def test_compute_stage_envelope_violation(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    # 110 m/s at sea level -> Mach > 0.3 -> envelope violation.
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

    # Restore: a second run with resume=True should NOT short-circuit
    # because the prior run did not complete; it must execute fully.
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
    """A non-domain exception inside a stage is captured as a failure."""
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

    # An empty response queue makes the parser raise, forcing fallback.
    client = StaticLLMClient([{"not": "valid"}, {"still": "bad"}, {"nope": True}])
    pipe = Pipeline(out_root=tmp_path, llm_client=client)
    result = pipe.run(_GOOD_INTENT, resume=False)
    assert result.status == "completed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "ok"


def test_run_records_failure_when_llm_and_offline_both_fail(tmp_path: Path) -> None:
    from aerosynthx.intent import StaticLLMClient

    # LLM returns junk (parser raises) AND the prose is unparseable offline,
    # so the fallback also raises -> the parse stage must fail cleanly.
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
    pipe.run(_GOOD_INTENT)  # completes & caches (5 stages, no solve)
    # execute=True must re-run and add the solve stage despite the cache.
    result = pipe.run(_GOOD_INTENT, execute=True)
    assert len(result.stages) == 6


# --- Phase 13: timeout + cancellation ---------------------------------


class _FakeClock:
    """A deterministic monotonic clock driven by a value queue."""

    def __init__(self, *values: float) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


def test_run_times_out_at_first_stage(tmp_path: Path) -> None:
    # clock: start() -> 0.0 (deadline = 1.0); parse check -> 100.0 (expired).
    pipe = Pipeline(out_root=tmp_path, clock=_FakeClock(0.0, 100.0))
    result = pipe.run(_GOOD_INTENT, timeout=1.0)

    assert result.status == "failed"
    parse = next(s for s in result.stages if s.name == "parse")
    assert parse.status == "failed"
    assert parse.error is not None and "RunTimeoutError" in parse.error
    later = [s for s in result.stages if s.name in {"compute", "case", "persist"}]
    assert all(s.status == "pending" for s in later)


def test_run_times_out_at_later_stage(tmp_path: Path) -> None:
    # start -> 0.0, parse check -> 0.0 (live), compute check -> 100.0 (expired).
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
    # Constant-zero clock never advances past the deadline.
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
    assert seen["timeout"] == 30.0


# --- Phase 14: run deletion -------------------------------------------


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
    pipe.run(_GOOD_INTENT)  # create the store so the db file exists
    assert pipe.delete_run("ffffffffffffffff") is False


def test_delete_run_without_store_returns_false(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    assert pipe.delete_run("deadbeef") is False


def test_delete_run_cleans_orphan_directory(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    pipe.run(_GOOD_INTENT)  # ensure the store file exists
    orphan = tmp_path / "runs" / "orphan00000000"
    orphan.mkdir(parents=True)
    (orphan / "stray.txt").write_text("x")

    # No store record, but the directory is cleaned up best-effort.
    assert pipe.delete_run("orphan00000000") is False
    assert not orphan.exists()


def test_concurrent_same_intent_builds_once(tmp_path: Path) -> None:
    import threading

    build_count = 0
    count_guard = threading.Lock()

    class _CountingPipeline(Pipeline):
        def _run_uncached(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            nonlocal build_count
            with count_guard:
                build_count += 1
            return super()._run_uncached(*args, **kwargs)  # type: ignore[arg-type]

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

    # The second caller queued behind the lock and resumed the cached run.
    assert build_count == 1
    run_ids = {r.run_id for r in results}  # type: ignore[attr-defined]
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

    assert {r.status for r in results.values()} == {"completed"}  # type: ignore[attr-defined]
    assert len({r.run_id for r in results.values()}) == 2  # type: ignore[attr-defined]
