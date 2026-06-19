"""Orchestrator for running optimization jobs."""

import uuid
from datetime import UTC, datetime

from aerosynthx.optimizer.engine import GridSearchEngine
from aerosynthx.optimizer.schemas import OptimizationSpec, OptimizationResult
from aerosynthx.study.runner import StudyRunner
from aerosynthx.workflow.db import OptimizationRow, StudyRow, open_session


class OptimizationRunner:
    """Executes and manages optimization studies."""

    def __init__(self, study_runner: StudyRunner):
        self._study_runner = study_runner
        self._engine = GridSearchEngine()

    def run(self, spec: OptimizationSpec) -> OptimizationResult:
        """
        Submits an asynchronous optimization job to Celery.
        """
        from aerosynthx.optimizer.tasks import execute_optimization_task

        opt_id = uuid.uuid4().hex[:16]

        with open_session(self._study_runner._pipeline.db_path) as session:
            opt_row = OptimizationRow(
                id=opt_id,
                spec_json=spec.model_dump_json(),
                status="queued",
                created_at_iso=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            )
            session.add(opt_row)
            session.commit()

        from aerosynthx.task_queue import celery_app
        if celery_app.conf.task_always_eager:
            return self.run_sync(spec, opt_id=opt_id)

        execute_optimization_task.delay(
            spec_dict=spec.model_dump(),
            out_root_str=str(self._study_runner._pipeline._out_root),
            opt_id=opt_id,
        )

        return OptimizationResult(
            optimization_id=opt_id,
            study_id="",
            best_run_id="",
            best_run_result={},
        )

    def run_sync(self, spec: OptimizationSpec, opt_id: str) -> OptimizationResult:
        """
        Synchronously runs an optimization study.
        This is intended to be called by a Celery task.
        """
        with open_session(self._study_runner._pipeline.db_path) as session:
            opt_row = session.get(OptimizationRow, opt_id)
            if opt_row:
                opt_row.status = "running"
                session.commit()

        try:
            study_spec = self._engine.create_study_spec(spec)
            study_result = self._study_runner.run_sync(study_spec)

            best_run = self._find_best_run(study_result, spec)

            result = OptimizationResult(
                optimization_id=opt_id,
                study_id=study_result.study_id,
                best_run_id=best_run.run_id,
                best_run_result=best_run.to_json(),
            )

            with open_session(self._study_runner._pipeline.db_path) as session:
                opt_row = session.get(OptimizationRow, opt_id)
                if opt_row:
                    opt_row.status = "completed"
                    opt_row.result_json = result.model_dump_json()
                    opt_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")

                # Link the study to the optimization
                study_row = session.get(StudyRow, study_result.study_id)
                if study_row:
                    study_row.optimization_id = opt_id

                session.commit()

            return result
        except Exception:
            with open_session(self._study_runner._pipeline.db_path) as session:
                opt_row = session.get(OptimizationRow, opt_id)
                if opt_row:
                    opt_row.status = "failed"
                    opt_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
                    session.commit()
            raise

    def _find_best_run(self, study_result, spec: OptimizationSpec):
        """Finds the best run in a study based on the objective."""
        best_run = None

        if spec.objective == "maximize_cl_cd":
            max_cl_cd = -1
            for run in study_result.runs:
                if run.xfoil_results:
                    res = run.xfoil_results[0]
                    if res.cd > 0:
                        cl_cd = res.cl / res.cd
                        if cl_cd > max_cl_cd:
                            max_cl_cd = cl_cd
                            best_run = run

        elif spec.objective == "minimize_cd":
            min_cd = float("inf")
            for run in study_result.runs:
                if run.xfoil_results:
                    res = run.xfoil_results[0]
                    if res.cd < min_cd:
                        min_cd = res.cd
                        best_run = run

        elif spec.objective == "target_cl":
            min_diff = float("inf")
            for run in study_result.runs:
                if run.xfoil_results:
                    res = run.xfoil_results[0]
                    diff = abs(res.cl - spec.target_cl)
                    if diff < min_diff:
                        min_diff = diff
                        best_run = run

        else:
            raise NotImplementedError(f"Objective '{spec.objective}' not implemented.")

        if best_run is None:
            raise ValueError("Could not find a best run. The study may have failed or produced no results.")

        return best_run
