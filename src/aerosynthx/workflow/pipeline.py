"""Staged workflow pipeline: text -> intent -> flow state -> case dir.

This is the integration layer that stitches together
:mod:`aerosynthx.intent`, :mod:`aerosynthx.openfoam`, and persistent
storage. The pipeline is deterministic and offline by default: it uses
:func:`aerosynthx.intent.parse_offline` so it can run without an LLM.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from aerosynthx.intent import (
    DesignIntent,
    IntentError,
    IntentParser,
    LLMClient,
    ParseResult,
    parse_offline,
)
from aerosynthx.observability import METRICS, bind_correlation_id
from aerosynthx.openfoam import (
    CaseManifest,
    CommandRunner,
    FlowState,
    OpenFoamError,
    SolveResult,
    build_case,
    default_command_runner,
    derive_flow_state,
    openfoam_available,
    run_case,
)
from aerosynthx.workflow.cancellation import CancellationToken, RunControl
from aerosynthx.workflow.db import RunRow, StageRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.stages import STAGE_ORDER, StageName

_LOG = logging.getLogger("aerosynthx.workflow")

_STAGE_HIST = METRICS.histogram(
    "aerosynthx_pipeline_stage_duration_seconds",
    "Wall time per pipeline stage, labelled by stage name and outcome.",
    label_names=("stage", "status"),
)
_RUN_COUNTER = METRICS.counter(
    "aerosynthx_pipeline_runs_total",
    "Total pipeline runs, labelled by final status.",
    label_names=("status",),
)
_PARSE_COUNTER = METRICS.counter(
    "aerosynthx_intent_parse_total",
    "Intent parse attempts, labelled by mode and outcome.",
    label_names=("mode", "status"),
)
_SOLVER_COUNTER = METRICS.counter(
    "aerosynthx_solver_runs_total",
    "OpenFOAM solver executions, labelled by outcome.",
    label_names=("status",),
)

_StageStatus = Literal["ok", "skipped", "failed", "pending"]

_DEFAULT_DB_NAME: Final[str] = "aerosynthx.db"
_DEFAULT_SOLVER_TIMEOUT: Final[float] = 600.0


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


def _run_id_for(intent_text: str) -> str:
    digest = hashlib.sha256(_normalise_text(intent_text).encode("utf-8")).hexdigest()
    return digest[:16]


def _sha256_of_json(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True, slots=True)
class StageResult:
    """Outcome of a single pipeline stage."""

    name: str
    status: _StageStatus
    duration_ms: int
    output_digest: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Final outcome of a :meth:`Pipeline.run` invocation."""

    run_id: str
    intent_text: str
    status: Literal["completed", "failed"]
    intent: DesignIntent | None
    flow_state: FlowState | None
    case_dir: Path | None
    manifest_digest: str | None
    stages: tuple[StageResult, ...]
    solve_result: SolveResult | None = None

    def to_json(self) -> dict[str, Any]:
        """Render as a JSON-serialisable dict."""
        return {
            "run_id": self.run_id,
            "intent_text": self.intent_text,
            "status": self.status,
            "intent": self.intent.model_dump(mode="json") if self.intent else None,
            "flow_state": _flow_state_dict(self.flow_state) if self.flow_state else None,
            "case_dir": str(self.case_dir) if self.case_dir else None,
            "manifest_digest": self.manifest_digest,
            "stages": [asdict(s) for s in self.stages],
            "solve": _solve_dict(self.solve_result) if self.solve_result else None,
        }


def _solve_dict(state: SolveResult) -> dict[str, Any]:
    return {
        "ran": state.ran,
        "converged": state.converged,
        "iterations": state.iterations,
        "final_residual": state.final_residual,
        "coefficients": state.coefficients,
        "commands": list(state.commands),
    }


def _flow_state_dict(state: FlowState) -> dict[str, Any]:
    data = asdict(state)
    data["velocity_vector_m_s"] = list(data["velocity_vector_m_s"])
    return data


class Pipeline:
    """Staged execution of the full AeroSynthX text-to-case workflow."""

    def __init__(
        self,
        *,
        out_root: Path,
        db_path: Path | None = None,
        llm_client: LLMClient | None = None,
        command_runner: CommandRunner | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._out_root = out_root
        self._db_path = db_path if db_path is not None else out_root / _DEFAULT_DB_NAME
        self._llm_client = llm_client
        self._command_runner: CommandRunner = (
            command_runner if command_runner is not None else default_command_runner
        )
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic

    @property
    def db_path(self) -> Path:
        """Path to the SQLite run store."""
        return self._db_path

    def delete_run(self, run_id: str) -> bool:
        """Delete a run's store record and on-disk artifacts.

        The ``StageRow`` children cascade with the ``RunRow``; the run's
        directory tree (``<out_root>/runs/<run_id>``) is removed
        best-effort. Idempotent.

        Returns:
            ``True`` if a store record existed (and was removed), ``False``
            otherwise.
        """
        removed = False
        if self._db_path.exists():
            with open_session(self._db_path) as session:
                row = session.get(RunRow, run_id)
                if row is not None:
                    session.delete(row)
                    removed = True
        run_dir = self._out_root / "runs" / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        return removed

    def _parse_intent(self, intent_text: str) -> ParseResult:
        """Parse ``intent_text``, preferring the LLM when configured.

        When an LLM client is configured the LLM is tried first; any
        :class:`IntentError` triggers a deterministic offline fallback so
        a transient provider failure never breaks a run. The chosen mode
        and outcome are recorded in ``aerosynthx_intent_parse_total``.
        """
        if self._llm_client is None:
            result = parse_offline(intent_text)
            _PARSE_COUNTER.inc(mode="offline", status="ok")
            return result

        parser = IntentParser(self._llm_client, model_name="llm")
        try:
            result = parser.parse(intent_text)
        except IntentError as exc:
            _PARSE_COUNTER.inc(mode="llm", status="error")
            _LOG.warning(
                "llm parse failed; falling back to offline",
                extra={"error": str(exc)},
            )
            try:
                fallback = parse_offline(intent_text)
            except IntentError:
                _PARSE_COUNTER.inc(mode="fallback", status="error")
                raise
            _PARSE_COUNTER.inc(mode="fallback", status="ok")
            return fallback
        _PARSE_COUNTER.inc(mode="llm", status="ok")
        return result

    def run(
        self,
        intent_text: str,
        *,
        resume: bool = True,
        execute: bool = False,
        timeout: float | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RunResult:
        """Execute every pipeline stage for ``intent_text``.

        Args:
            intent_text: Natural-language design intent.
            resume: If true and a completed run already exists for this
                text, return the cached :class:`RunResult` without
                re-executing any stage. Ignored when ``execute`` is true.
            execute: If true, run the generated case through the OpenFOAM
                solver (when the toolchain is available). Execution always
                runs fresh, bypassing the resume cache.
            timeout: Optional wall-clock budget in seconds. When exceeded,
                the in-flight stage fails fast and the run finalises as
                ``"failed"`` with a ``workflow.run.timeout`` stage error.
            cancel_token: Optional :class:`CancellationToken`; tripping it
                aborts the run at the next stage boundary with a
                ``workflow.run.cancelled`` stage error.

        Returns:
            A :class:`RunResult`. Stage-level failures are captured in
            ``stages``; the final ``status`` is ``"completed"`` only when
            every stage succeeded.
        """
        if not intent_text or not intent_text.strip():
            raise StageError(
                "intent text must be non-empty",
                stage=StageName.PARSE.value,
                code="workflow.input.empty",
            )

        control = RunControl.create(timeout=timeout, cancel_token=cancel_token, clock=self._clock)
        run_id = _run_id_for(intent_text)
        if resume and not execute:
            cached = self._maybe_resume(run_id)
            if cached is not None:
                _LOG.info("resume.hit run_id=%s", run_id)
                return cached

        with bind_correlation_id(run_id):
            return self._run_uncached(run_id, intent_text, execute=execute, control=control)

    def _run_uncached(
        self,
        run_id: str,
        intent_text: str,
        *,
        execute: bool = False,
        control: RunControl,
    ) -> RunResult:
        run_dir = self._out_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        stages: list[StageResult] = []
        intent: DesignIntent | None = None
        flow: FlowState | None = None
        manifest: CaseManifest | None = None
        case_dir: Path | None = None
        solve_result: SolveResult | None = None

        # --- parse -------------------------------------------------
        with _timed(StageName.PARSE) as record:
            control.check(StageName.PARSE.value)
            try:
                parse_result = self._parse_intent(intent_text)
                intent = parse_result.intent
                record["digest"] = _sha256_of_json(intent.model_dump(mode="json"))
            except IntentError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        if record["result"].status == "failed":
            return self._finalise(run_id, intent_text, "failed", stages, None, None, None, None)

        # --- compute -----------------------------------------------
        with _timed(StageName.COMPUTE) as record:
            control.check(StageName.COMPUTE.value)
            try:
                assert intent is not None
                flow = derive_flow_state(intent)
                record["digest"] = _sha256_of_json(_flow_state_dict(flow))
            except OpenFoamError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        if record["result"].status == "failed":
            return self._finalise(run_id, intent_text, "failed", stages, intent, None, None, None)

        # --- geometry ---------------------------------------------
        # build_case re-generates geometry; we still record a stage so
        # the timeline is complete. No standalone artifact is written.
        with _timed(StageName.GEOMETRY) as record:
            control.check(StageName.GEOMETRY.value)
            assert intent is not None
            record["digest"] = hashlib.sha256(
                intent.airfoil.designation.encode("utf-8")
            ).hexdigest()
        stages.append(record["result"])

        # --- case --------------------------------------------------
        case_dir = run_dir / "case"
        with _timed(StageName.CASE) as record:
            control.check(StageName.CASE.value)
            try:
                assert intent is not None
                manifest = build_case(intent, case_dir, overwrite=True)
                record["digest"] = _sha256_of_json(manifest.files)
            except OpenFoamError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        if record["result"].status == "failed":
            return self._finalise(run_id, intent_text, "failed", stages, intent, flow, None, None)

        # --- solve (opt-in) ---------------------------------------
        if execute:
            assert case_dir is not None
            solve_result = self._solve_stage(case_dir, run_dir, stages, control)
            if stages[-1].status == "failed":
                return self._finalise(
                    run_id, intent_text, "failed", stages, intent, flow, case_dir, None
                )

        # --- persist -----------------------------------------------
        manifest_digest = _sha256_of_json(manifest.files) if manifest is not None else None
        with _timed(StageName.PERSIST) as record:
            self._persist(
                run_id=run_id,
                intent_text=intent_text,
                status="completed",
                intent=intent,
                flow=flow,
                case_dir=case_dir,
                manifest_digest=manifest_digest,
                stages_so_far=stages,
            )
            record["digest"] = manifest_digest
        stages.append(record["result"])
        # Re-persist with the persist-stage row included so the DB is
        # consistent with the in-memory result.
        self._persist(
            run_id=run_id,
            intent_text=intent_text,
            status="completed",
            intent=intent,
            flow=flow,
            case_dir=case_dir,
            manifest_digest=manifest_digest,
            stages_so_far=stages,
        )

        result = RunResult(
            run_id=run_id,
            intent_text=intent_text,
            status="completed",
            intent=intent,
            flow_state=flow,
            case_dir=case_dir,
            manifest_digest=manifest_digest,
            stages=tuple(stages),
            solve_result=solve_result,
        )
        (run_dir / "run.json").write_text(
            json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _RUN_COUNTER.inc(status="completed")
        return result

    def _solve_stage(
        self, case_dir: Path, run_dir: Path, stages: list[StageResult], control: RunControl
    ) -> SolveResult | None:
        """Run the opt-in solve stage, appending its :class:`StageResult`.

        Returns the :class:`SolveResult` on success, ``None`` when the
        toolchain is absent (stage recorded as ``skipped``) or the solver
        failed (stage recorded as ``failed``). The solver's per-command
        timeout is capped by the run's remaining time budget.
        """
        solve_result: SolveResult | None = None
        with _timed(StageName.SOLVE) as record:
            control.check(StageName.SOLVE.value)
            if not openfoam_available():
                record["skipped"] = True
                _SOLVER_COUNTER.inc(status="skipped")
            else:
                try:
                    solve_result = run_case(
                        case_dir,
                        runner=self._command_runner,
                        timeout=control.solver_timeout(_DEFAULT_SOLVER_TIMEOUT),
                    )
                    record["digest"] = _sha256_of_json(_solve_dict(solve_result))
                    _SOLVER_COUNTER.inc(status="ok")
                except OpenFoamError as exc:
                    record["error"] = str(exc)
                    _SOLVER_COUNTER.inc(status="failed")
        stages.append(record["result"])
        if solve_result is not None:
            (run_dir / "solve.json").write_text(
                json.dumps(_solve_dict(solve_result), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return solve_result

    # ------------------------------------------------------------------
    # Internal helpers

    def _maybe_resume(self, run_id: str) -> RunResult | None:
        if not self._db_path.exists():
            return None
        with open_session(self._db_path) as session:
            row = session.get(RunRow, run_id)
            if row is None or row.status != "completed":
                return None
            return _row_to_result(row)

    def _persist(
        self,
        *,
        run_id: str,
        intent_text: str,
        status: Literal["completed", "failed"],
        intent: DesignIntent | None,
        flow: FlowState | None,
        case_dir: Path | None,
        manifest_digest: str | None,
        stages_so_far: list[StageResult],
    ) -> None:
        now_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
        with open_session(self._db_path) as session:
            existing = session.get(RunRow, run_id)
            if existing is not None:
                session.delete(existing)
                session.flush()
            row = RunRow(
                id=run_id,
                intent_text=intent_text,
                intent_json=(
                    json.dumps(intent.model_dump(mode="json"), sort_keys=True)
                    if intent is not None
                    else None
                ),
                flow_state_json=(
                    json.dumps(_flow_state_dict(flow), sort_keys=True) if flow is not None else None
                ),
                status=status,
                case_dir=str(case_dir) if case_dir is not None else None,
                manifest_digest=manifest_digest,
                created_at_iso=now_iso,
                completed_at_iso=now_iso if status == "completed" else None,
                stages=[
                    StageRow(
                        ordinal=i,
                        name=s.name,
                        status=s.status,
                        duration_ms=s.duration_ms,
                        output_digest=s.output_digest,
                        error=s.error,
                    )
                    for i, s in enumerate(stages_so_far)
                ],
            )
            session.add(row)

    def _finalise(
        self,
        run_id: str,
        intent_text: str,
        status: Literal["completed", "failed"],
        stages: list[StageResult],
        intent: DesignIntent | None,
        flow: FlowState | None,
        case_dir: Path | None,
        manifest_digest: str | None,
    ) -> RunResult:
        # Mark any stages that never ran as pending.
        executed = {s.name for s in stages}
        for stage in STAGE_ORDER:
            if stage.value not in executed:
                stages.append(
                    StageResult(
                        name=stage.value,
                        status="pending",
                        duration_ms=0,
                        output_digest=None,
                        error=None,
                    )
                )
        # Best-effort persist of the failed run.
        try:
            self._persist(
                run_id=run_id,
                intent_text=intent_text,
                status=status,
                intent=intent,
                flow=flow,
                case_dir=case_dir,
                manifest_digest=manifest_digest,
                stages_so_far=stages,
            )
        except Exception:  # pragma: no cover - defensive
            _LOG.exception("failed to persist failed run %s", run_id)
        _RUN_COUNTER.inc(status=status)
        return RunResult(
            run_id=run_id,
            intent_text=intent_text,
            status=status,
            intent=intent,
            flow_state=flow,
            case_dir=case_dir,
            manifest_digest=manifest_digest,
            stages=tuple(stages),
        )


# ----------------------------------------------------------------------
# Stage timing helper


class _StageRecorder:
    """Context-manager helper that builds a :class:`StageResult`."""

    def __init__(self, stage: StageName) -> None:
        self._stage = stage
        self._start = 0.0
        self._record: dict[str, Any] = {
            "digest": None,
            "error": None,
            "skipped": False,
            "result": None,
        }

    def __enter__(self) -> dict[str, Any]:
        self._start = time.perf_counter()
        return self._record

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        elapsed = time.perf_counter() - self._start
        elapsed_ms = int(elapsed * 1000)
        if exc is not None:
            # Unexpected exception -- record as failure and swallow so
            # the pipeline can finalise cleanly.
            self._record["error"] = repr(exc)
        if self._record["error"]:
            status: _StageStatus = "failed"
        elif self._record["skipped"]:
            status = "skipped"
        else:
            status = "ok"
        self._record["result"] = StageResult(
            name=self._stage.value,
            status=status,
            duration_ms=elapsed_ms,
            output_digest=self._record["digest"],
            error=self._record["error"],
        )
        _STAGE_HIST.observe(elapsed, stage=self._stage.value, status=status)
        _LOG.info(
            "stage.done",
            extra={
                "stage": self._stage.value,
                "stage_status": status,
                "duration_ms": elapsed_ms,
            },
        )
        return True


def _timed(stage: StageName) -> _StageRecorder:
    return _StageRecorder(stage)


# ----------------------------------------------------------------------
# Read-side helpers


def _row_to_result(row: RunRow) -> RunResult:
    intent = (
        DesignIntent.model_validate_json(row.intent_json) if row.intent_json is not None else None
    )
    flow_state: FlowState | None = None
    if row.flow_state_json is not None:
        data = json.loads(row.flow_state_json)
        vec = data["velocity_vector_m_s"]
        flow_state = FlowState(
            velocity_m_s=data["velocity_m_s"],
            velocity_vector_m_s=(float(vec[0]), float(vec[1]), float(vec[2])),
            mach=data["mach"],
            altitude_m=data["altitude_m"],
            temperature_k=data["temperature_k"],
            pressure_pa=data["pressure_pa"],
            density_kg_m3=data["density_kg_m3"],
            kinematic_viscosity_m2_s=data["kinematic_viscosity_m2_s"],
            reynolds_chord=data["reynolds_chord"],
            turbulence_intensity=data["turbulence_intensity"],
            turbulence_length_scale_m=data["turbulence_length_scale_m"],
            k_m2_s2=data["k_m2_s2"],
            omega_1_s=data["omega_1_s"],
        )
    stages = tuple(
        StageResult(
            name=s.name,
            status=s.status,  # type: ignore[arg-type]
            duration_ms=s.duration_ms,
            output_digest=s.output_digest,
            error=s.error,
        )
        for s in row.stages
    )
    return RunResult(
        run_id=row.id,
        intent_text=row.intent_text,
        status=row.status,  # type: ignore[arg-type]
        intent=intent,
        flow_state=flow_state,
        case_dir=Path(row.case_dir) if row.case_dir else None,
        manifest_digest=row.manifest_digest,
        stages=stages,
    )


def load_run(db_path: Path, run_id: str) -> RunResult | None:
    """Return the persisted :class:`RunResult` for ``run_id`` or ``None``."""
    if not db_path.exists():
        return None
    with open_session(db_path) as session:
        row = session.get(RunRow, run_id)
        if row is None:
            return None
        return _row_to_result(row)
