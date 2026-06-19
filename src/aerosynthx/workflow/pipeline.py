"""Staged workflow pipeline: text -> intent -> flow state -> case dir.

This is the integration layer that stitches together
:mod:`aerosynthx.intent`, :mod:`aerosynthx.openfoam`, and persistent
storage. The pipeline is deterministic and offline by default: it uses
:func:`aerosynthx.intent.parse_offline` so it can run without an LLM.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import shutil
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal

from sqlalchemy import func, select

from aerosynthx.geometry import Wing, generate_wing
from aerosynthx.geometry.custom import custom_airfoil
from aerosynthx.geometry.naca4 import naca4
from aerosynthx.geometry.naca5 import naca5
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
from aerosynthx.workflow.artifacts import ContentAddressedStore, RelinkResult
from aerosynthx.workflow.cancellation import CancellationToken, RunControl
from aerosynthx.workflow.db import RunRow, StageRow, XfoilResultRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.locking import DEFAULT_RUN_LOCKS, RunLockRegistry
from aerosynthx.workflow.progress import ProgressEvent, ProgressSink
from aerosynthx.workflow.retention import (
    _BLOBS_COLLECTED,
    _RUNS_PRUNED,
    GarbageCollectResult,
    PruneResult,
)
from aerosynthx.workflow.stages import STAGE_ORDER_2D, STAGE_ORDER_3D, StageName
from aerosynthx.xfoil import XfoilError, XfoilResult, run_xfoil

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
_DEFAULT_SOLVER_TIMEOUT: Final[float] = 3600.0 # Increased for 3D


# An internal emit callback: (kind, stage, status, duration_ms) -> None.
_Emit = Callable[[str, str | None, str | None, int | None], None]


def _noop_emit(kind: str, stage: str | None, status: str | None, duration_ms: int | None) -> None:
    """Emit callback used when no progress sink is configured."""
    return


def _make_emitter(run_id: str, sink: ProgressSink | None) -> _Emit:
    """Build a per-run emit callback wrapping ``sink`` with a sequence.

    Returns :func:`_noop_emit` when ``sink`` is ``None`` so the hot path is
    zero-cost. The returned closure owns its own sequence counter, so it is
    safe to create one per concurrent run.
    """
    if sink is None:
        return _noop_emit
    counter = itertools.count()

    def emit(kind: str, stage: str | None, status: str | None, duration_ms: int | None) -> None:
        sink(
            ProgressEvent(
                sequence=next(counter),
                kind=kind,  # type: ignore[arg-type]
                run_id=run_id,
                stage=stage,
                status=status,
                duration_ms=duration_ms,
            )
        )

    return emit


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


def _run_id_for(intent_text: str, mode: str = "openfoam") -> str:
    digest = hashlib.sha256(f"{_normalise_text(intent_text)}::{mode}".encode("utf-8")).hexdigest()
    return digest[:16]


def _sha256_of_json(payload: dict[str, Any] | list[dict[str, Any]]) -> str:
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
    xfoil_results: list[XfoilResult] | None = None
    wing: Wing | None = None

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
            "xfoil": [asdict(r) for r in self.xfoil_results] if self.xfoil_results else None,
            "xfoil_results": [asdict(r) for r in self.xfoil_results] if self.xfoil_results else None,
            "wing": asdict(self.wing) if self.wing else None,
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


def _load_solve_result(case_dir: Path | None) -> SolveResult | None:
    """Return the persisted :class:`SolveResult` for a run, if present."""
    if case_dir is None:
        return None
    solve_path = case_dir.parent / "solve.json"
    if not solve_path.is_file():
        return None
    try:
        data = json.loads(solve_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return SolveResult(
        ran=bool(data["ran"]),
        converged=bool(data["converged"]),
        iterations=int(data["iterations"]),
        final_residual=data.get("final_residual"),
        coefficients=dict(data.get("coefficients", {})),
        commands=tuple(data.get("commands", ())),
    )


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
        lock_registry: RunLockRegistry | None = None,
        artifact_store: ContentAddressedStore | None = None,
    ) -> None:
        self._out_root = out_root
        self._db_path = db_path if db_path is not None else out_root / _DEFAULT_DB_NAME
        self._llm_client = llm_client
        self._command_runner: CommandRunner = (
            command_runner if command_runner is not None else default_command_runner
        )
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._locks: RunLockRegistry = (
            lock_registry if lock_registry is not None else DEFAULT_RUN_LOCKS
        )
        self._artifact_store: ContentAddressedStore = (
            artifact_store
            if artifact_store is not None
            else ContentAddressedStore(out_root / "blobs")
        )

    @property
    def db_path(self) -> Path:
        """Path to the SQLite run store."""
        return self._db_path

    @property
    def artifact_store(self) -> ContentAddressedStore:
        """The content-addressed store de-duplicating run case files."""
        return self._artifact_store

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

    def prune_runs(
        self,
        *,
        max_age_days: float | None = None,
        max_count: int | None = None,
        now: datetime | None = None,
    ) -> PruneResult:
        """Delete runs that violate the retention policy.

        A run is removed when it is older than ``now - max_age_days`` *or*
        falls outside the newest ``max_count`` runs (the two predicates
        union). Runs are considered newest-first by ``created_at_iso``.
        Selected runs are removed via :meth:`delete_run`. Passing neither
        bound deletes nothing.

        Args:
            max_age_days: Maximum age, in days, a run may reach before it is
                pruned. ``None`` disables the age bound.
            max_count: Maximum number of (newest) runs to retain. ``None``
                disables the count bound.
            now: Reference time for the age bound; defaults to the current
                UTC time. Injectable for deterministic tests.

        Returns:
            A :class:`PruneResult` listing the deleted run ids (newest-first)
            and the number of runs kept.
        """
        reference = now if now is not None else datetime.now(tz=UTC)
        rows = self._run_ids_newest_first()
        cutoff_iso: str | None = None
        if max_age_days is not None:
            cutoff_iso = (reference - timedelta(days=max_age_days)).isoformat()
        doomed: list[str] = []
        for index, (run_id, created_at_iso) in enumerate(rows):
            too_old = cutoff_iso is not None and created_at_iso < cutoff_iso
            over_count = max_count is not None and index >= max_count
            if too_old or over_count:
                doomed.append(run_id)
        for run_id in doomed:
            self.delete_run(run_id)
            _RUNS_PRUNED.inc()
        return PruneResult(deleted=tuple(doomed), kept=len(rows) - len(doomed))

    def collect_garbage(self) -> GarbageCollectResult:
        """Remove store blobs no longer referenced by any surviving run.

        The set of live digests is rebuilt from every run's
        ``aerosynthx_manifest.json`` ``files`` map; any blob whose digest is
        absent from that set is deleted and its bytes reclaimed. Idempotent.

        Returns:
            A :class:`GarbageCollectResult` with the number of blobs
            collected, bytes freed, and live blobs retained.
        """
        referenced = self._referenced_digests()
        collected = 0
        freed = 0
        for digest in list(self._artifact_store.iter_digests()):
            if digest in referenced:
                continue
            freed += self._artifact_store.delete_blob(digest)
            collected += 1
            _BLOBS_COLLECTED.inc()
        return GarbageCollectResult(
            collected=collected,
            freed_bytes=freed,
            kept=len(referenced),
        )

    def _run_ids_newest_first(self) -> list[tuple[str, str]]:
        """Return ``(run_id, created_at_iso)`` pairs, newest first."""
        if not self._db_path.exists():
            return []
        with open_session(self._db_path) as session:
            stmt = select(RunRow).order_by(RunRow.created_at_iso.desc())
            return [(r.id, r.created_at_iso) for r in session.execute(stmt).scalars().all()]

    def _referenced_digests(self) -> set[str]:
        """Collect every blob digest referenced by a surviving run."""
        digests: set[str] = set()
        if not self._db_path.exists():
            return digests
        with open_session(self._db_path) as session:
            case_dirs = [r.case_dir for r in session.execute(select(RunRow)).scalars().all()]
        for case_dir in case_dirs:
            if case_dir is None:
                continue
            manifest_path = Path(case_dir) / "aerosynthx_manifest.json"
            if not manifest_path.is_file():
                continue
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            digests.update(data.get("files", {}).values())
        return digests

    def relink_runs(self) -> RelinkResult:
        """Hard-link every surviving run's case files into the artifact store.

        Reclaims the on-disk bytes duplicated between each run directory and
        the content-addressed store by replacing run files with hard links to
        their blobs. Idempotent: already-linked files are skipped.

        Returns:
            An aggregate :class:`RelinkResult` across all runs.
        """
        linked = 0
        reclaimed = 0
        skipped = 0
        for case_dir, files in self._iter_run_cases():
            result = self._artifact_store.link_case(case_dir, files)
            linked += result.linked
            reclaimed += result.bytes_reclaimed
            skipped += result.skipped
        return RelinkResult(linked=linked, bytes_reclaimed=reclaimed, skipped=skipped)

    def _iter_run_cases(self) -> Iterator[tuple[Path, dict[str, str]]]:
        """Yield ``(case_dir, files)`` for every run with a manifest on disk."""
        if not self._db_path.exists():
            return
        with open_session(self._db_path) as session:
            case_dirs = [r.case_dir for r in session.execute(select(RunRow)).scalars().all()]
        for case_dir in case_dirs:
            if case_dir is None:
                continue
            manifest_path = Path(case_dir) / "aerosynthx_manifest.json"
            if not manifest_path.is_file():
                continue
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            yield Path(case_dir), data.get("files", {})

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
        on_event: ProgressSink | None = None,
        analysis_mode: Literal["openfoam", "xfoil"] = "openfoam",
    ) -> RunResult:
        """
        Submits a run to the task queue and returns an initial result,
        or executes it synchronously if no task queue is configured.
        """
        from aerosynthx.workflow.tasks import execute_run_task

        if not intent_text or not intent_text.strip():
            raise StageError("Intent text cannot be empty or whitespace-only.", stage="parse")

        run_id = _run_id_for(intent_text, analysis_mode)

        with self._locks.acquire(run_id):
            if resume and not (execute and analysis_mode == "openfoam"):
                cached = self._maybe_resume(run_id)
                if cached is not None:
                    _LOG.info("resume.hit run_id=%s", run_id)
                    return cached

            # Create initial DB entry
            self._persist(
                run_id=run_id,
                intent_text=intent_text,
                status="queued",
                intent=None, flow=None, case_dir=None, manifest_digest=None,
                stages_so_far=[],
            )

            from aerosynthx.task_queue import celery_app
            if celery_app.conf.task_always_eager:
                control = RunControl.create(timeout=timeout, cancel_token=cancel_token, clock=self._clock)
                emit = _make_emitter(run_id, on_event)
                status = "failed"
                try:
                    res = self.execute_run_sync(
                        run_id=run_id,
                        intent_text=intent_text,
                        execute=execute,
                        control=control,
                        emit=emit,
                        analysis_mode=analysis_mode,
                    )
                    status = res.status
                    return res
                finally:
                    emit("run_finished", None, status, None)

            # Submit to Celery
            execute_run_task.delay(
                intent_text=intent_text,
                out_root_str=str(self._out_root),
                analysis_mode=analysis_mode,
                run_id=run_id,
            )

            # Return a placeholder result
            return RunResult(
                run_id=run_id,
                intent_text=intent_text,
                status="queued",
                intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(),
            )

    def execute_run_sync(
        self,
        run_id: str,
        intent_text: str,
        *,
        execute: bool = False,
        control: RunControl,
        emit: _Emit,
        analysis_mode: Literal["openfoam", "xfoil"] = "openfoam",
    ) -> RunResult:
        run_dir = self._out_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        stages: list[StageResult] = []
        intent: DesignIntent | None = None
        flow: FlowState | None = None
        manifest: CaseManifest | None = None
        case_dir: Path | None = None
        solve_result: SolveResult | None = None
        xfoil_results: list[XfoilResult] | None = None
        wing: Wing | None = None

        # --- parse -------------------------------------------------
        with _timed(StageName.PARSE, emit) as record:
            control.check(StageName.PARSE.value)
            try:
                parse_result = self._parse_intent(intent_text)
                intent = parse_result.intent
                record["digest"] = _sha256_of_json(intent.model_dump(mode="json"))
            except IntentError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        if record["result"].status == "failed":
            return self._finalise(run_id, intent_text, "failed", stages, None, None, None, None, None, None)

        # --- compute -----------------------------------------------
        with _timed(StageName.COMPUTE, emit) as record:
            control.check(StageName.COMPUTE.value)
            try:
                assert intent is not None
                flow = derive_flow_state(intent)
                record["digest"] = _sha256_of_json(_flow_state_dict(flow))
            except OpenFoamError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        if record["result"].status == "failed":
            return self._finalise(run_id, intent_text, "failed", stages, intent, None, None, None, None, None)

        if intent.wing:
            # --- wing_geometry -----------------------------------------
            with _timed(StageName.WING_GEOMETRY, emit) as record:
                control.check(StageName.WING_GEOMETRY.value)
                try:
                    wing = generate_wing(intent.wing)
                    wing_path = run_dir / "wing.json"
                    wing_path.write_text(json.dumps(asdict(wing), indent=2))
                    record["digest"] = _sha256_of_json(asdict(wing))
                except Exception as exc:
                    record["error"] = str(exc)
            stages.append(record["result"])
            if record["result"].status == "failed":
                return self._finalise(run_id, intent_text, "failed", stages, intent, flow, None, None, None, wing)

            # --- case (for 3D wing) ------------------------------------
            case_dir = run_dir / "case"
            with _timed(StageName.CASE, emit) as record:
                control.check(StageName.CASE.value)
                try:
                    manifest = build_case(intent, case_dir, overwrite=True)
                    record["digest"] = _sha256_of_json(manifest.files)
                    self._artifact_store.archive_case(case_dir, manifest.files)
                except OpenFoamError as exc:
                    record["error"] = str(exc)
            stages.append(record["result"])
            if record["result"].status == "failed":
                return self._finalise(run_id, intent_text, "failed", stages, intent, flow, None, None, None, wing)

            # --- mesh (for 3D wing) ------------------------------------
            with _timed(StageName.MESH, emit) as record:
                control.check(StageName.MESH.value)
                record["digest"] = "mesh_configured"
            stages.append(record["result"])
            if record["result"].status == "failed":
                return self._finalise(run_id, intent_text, "failed", stages, intent, flow, case_dir, None, None, wing)

            # --- solve (opt-in, 3D) ---------------------------------------
            if execute:
                assert case_dir is not None
                solve_result = self._solve_stage(case_dir, run_dir, stages, control, emit, intent=intent)
                if stages[-1].status == "failed":
                    return self._finalise(
                        run_id, intent_text, "failed", stages, intent, flow, case_dir, None, None, wing
                    )

        elif intent.airfoil:
            # --- geometry ---------------------------------------------
            with _timed(StageName.GEOMETRY, emit) as record:
                control.check(StageName.GEOMETRY.value)
                record["digest"] = hashlib.sha256(
                    intent.airfoil.designation.encode("utf-8") if intent.airfoil.designation else "custom".encode("utf-8")
                ).hexdigest()
            stages.append(record["result"])

            if analysis_mode == "openfoam":
                # --- case --------------------------------------------------
                case_dir = run_dir / "case"
                with _timed(StageName.CASE, emit) as record:
                    control.check(StageName.CASE.value)
                    try:
                        assert intent is not None
                        manifest = build_case(intent, case_dir, overwrite=True)
                        record["digest"] = _sha256_of_json(manifest.files)
                        self._artifact_store.archive_case(case_dir, manifest.files)
                    except OpenFoamError as exc:
                        record["error"] = str(exc)
                stages.append(record["result"])
                if record["result"].status == "failed":
                    return self._finalise(run_id, intent_text, "failed", stages, intent, flow, None, None, None, None)

                # --- solve (opt-in, 2D) ---------------------------------------
                if execute:
                    assert case_dir is not None
                    solve_result = self._solve_stage(case_dir, run_dir, stages, control, emit, intent=intent)
                    if stages[-1].status == "failed":
                        return self._finalise(
                            run_id, intent_text, "failed", stages, intent, flow, case_dir, None, None, None
                        )
            elif analysis_mode == "xfoil":
                # --- xfoil -------------------------------------------------
                assert intent is not None
                assert flow is not None
                xfoil_results = self._xfoil_stage(intent, stages, control, emit)
                if stages[-1].status == "failed":
                    return self._finalise(
                        run_id, intent_text, "failed", stages, intent, flow, None, None, None, None
                    )

        # --- persist -----------------------------------------------
        manifest_digest = _sha256_of_json(manifest.files) if manifest is not None else None
        with _timed(StageName.PERSIST, emit) as record:
            self._persist(
                run_id=run_id,
                intent_text=intent_text,
                status="completed",
                intent=intent,
                flow=flow,
                case_dir=case_dir,
                manifest_digest=manifest_digest,
                stages_so_far=stages,
                xfoil_results=xfoil_results,
                wing=wing,
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
            xfoil_results=xfoil_results,
            wing=wing,
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
            xfoil_results=xfoil_results,
            wing=wing,
        )
        (run_dir / "run.json").write_text(
            json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _RUN_COUNTER.inc(status="completed")
        return result

    def _solve_stage(
        self,
        case_dir: Path,
        run_dir: Path,
        stages: list[StageResult],
        control: RunControl,
        emit: _Emit = _noop_emit,
        intent: DesignIntent | None = None,
    ) -> SolveResult | None:
        """Run the opt-in solve stage, appending its :class:`StageResult`."""
        solve_result: SolveResult | None = None
        with _timed(StageName.SOLVE, emit) as record:
            control.check(StageName.SOLVE.value)
            if not openfoam_available():
                record["skipped"] = True
                _SOLVER_COUNTER.inc(status="skipped")
            else:
                try:
                    solve_result = run_case(
                        case_dir,
                        intent=intent,
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

    def _xfoil_stage(
        self,
        intent: DesignIntent,
        stages: list[StageResult],
        control: RunControl,
        emit: _Emit = _noop_emit,
    ) -> list[XfoilResult] | None:
        """Run the XFOIL analysis stage, appending its :class:`StageResult`."""
        xfoil_results: list[XfoilResult] | None = None
        with _timed(StageName.XFOIL, emit) as record:
            control.check(StageName.XFOIL.value)
            try:
                assert intent.airfoil is not None
                if intent.airfoil.family == "custom":
                    airfoil = custom_airfoil(intent.airfoil.coordinates, chord_m=float(intent.airfoil.chord_m))
                elif intent.airfoil.family == "naca5":
                    airfoil = naca5(intent.airfoil.designation, chord_m=float(intent.airfoil.chord_m))
                else:
                    airfoil = naca4(intent.airfoil.designation, chord_m=float(intent.airfoil.chord_m))

                xfoil_results = run_xfoil(airfoil, intent.flow)
                record["digest"] = _sha256_of_json([asdict(r) for r in xfoil_results])
            except XfoilError as exc:
                record["error"] = str(exc)
        stages.append(record["result"])
        return xfoil_results

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
        xfoil_results: list[XfoilResult] | None = None,
        wing: Wing | None = None,
    ) -> None:
        now_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
        with open_session(self._db_path) as session:
            existing = session.get(RunRow, run_id)
            if existing is not None:
                session.delete(existing)
                session.flush()

            xfoil_row = None
            if xfoil_results is not None:
                xfoil_row = XfoilResultRow(
                    polar_json=json.dumps([asdict(r) for r in xfoil_results])
                )

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
                xfoil_result=xfoil_row,
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
        xfoil_results: list[XfoilResult] | None,
        wing: Wing | None,
    ) -> RunResult:
        # Mark any stages that never ran as pending.
        executed = {s.name for s in stages}

        stage_order = STAGE_ORDER_3D if intent and intent.wing else STAGE_ORDER_2D

        for stage in stage_order:
            if stage.value not in executed and stage.value != StageName.XFOIL.value:
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
                xfoil_results=xfoil_results,
                wing=wing,
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
            xfoil_results=xfoil_results,
            wing=wing,
        )


# ----------------------------------------------------------------------
# Stage timing helper


class _StageRecorder:
    """Context-manager helper that builds a :class:`StageResult`."""

    def __init__(self, stage: StageName, emit: _Emit = _noop_emit) -> None:
        self._stage = stage
        self._emit = emit
        self._start = 0.0
        self._record: dict[str, Any] = {
            "digest": None,
            "error": None,
            "skipped": False,
            "result": None,
        }

    def __enter__(self) -> dict[str, Any]:
        self._start = time.perf_counter()
        self._emit("stage_started", self._stage.value, None, None)
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
        self._emit("stage_finished", self._stage.value, status, elapsed_ms)
        return True


def _timed(stage: StageName, emit: _Emit = _noop_emit) -> _StageRecorder:
    return _StageRecorder(stage, emit)


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
    case_dir = Path(row.case_dir) if row.case_dir else None

    xfoil_results = None
    if row.xfoil_result and row.xfoil_result.polar_json:
        xfoil_results = [XfoilResult(**r) for r in json.loads(row.xfoil_result.polar_json)]

    return RunResult(
        run_id=row.id,
        intent_text=row.intent_text,
        status=row.status,  # type: ignore[arg-type]
        intent=intent,
        flow_state=flow_state,
        case_dir=case_dir,
        manifest_digest=row.manifest_digest,
        stages=stages,
        solve_result=_load_solve_result(case_dir),
        xfoil_results=xfoil_results,
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


@dataclass(frozen=True, slots=True)
class RunListItem:
    """A lightweight, ORM-free summary of one persisted run."""

    run_id: str
    status: str
    intent_text: str
    created_at_iso: str
    completed_at_iso: str | None


@dataclass(frozen=True, slots=True)
class RunPage:
    """A single page of run summaries plus pagination metadata."""

    items: tuple[RunListItem, ...]
    total: int
    limit: int
    offset: int


def query_runs(
    db_path: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    q: str | None = None,
) -> RunPage:
    """Return a newest-first page of runs, optionally filtered and searched.

    ``status`` filters by exact run status and ``q`` performs a
    case-insensitive substring search over the stored intent text. ``total`` is
    the filtered match count, independent of the ``offset``/``limit`` slice.
    """
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    if not db_path.exists():
        return RunPage(items=(), total=0, limit=limit, offset=offset)
    filters = []
    if status is not None:
        filters.append(RunRow.status == status)
    if q:
        filters.append(RunRow.intent_text.ilike(f"%{q}%"))
    with open_session(db_path) as session:
        count_stmt = select(func.count()).select_from(RunRow)
        for clause in filters:
            count_stmt = count_stmt.where(clause)
        total = int(session.execute(count_stmt).scalar_one())
        stmt = select(RunRow).order_by(RunRow.created_at_iso.desc())
        for clause in filters:
            stmt = stmt.where(clause)
        stmt = stmt.offset(offset).limit(limit)
        rows = session.execute(stmt).scalars().all()
        items = tuple(
            RunListItem(
                run_id=r.id,
                status=r.status,
                intent_text=r.intent_text,
                created_at_iso=r.created_at_iso,
                completed_at_iso=r.completed_at_iso,
            )
            for r in rows
        )
    return RunPage(items=items, total=total, limit=limit, offset=offset)
