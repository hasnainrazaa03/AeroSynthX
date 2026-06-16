"""Orchestrator for running optimization jobs."""

import uuid
from datetime import UTC, datetime

from aerosynthx.optimizer.engine import GridSearchEngine
from aerosynthx.optimizer.schemas import OptimizationSpec, OptimizationResult
from aerosynthx.study.runner import StudyRunner
from aerosynthx.workflow.db import OptimizationRow, open_session


class OptimizationRunner:
    """Executes and manages optimization studies."""

    def __init__(self, study_runner: StudyRunner):
        self._study_runner = study_runner
        self._engine = GridSearchEngine()

    def run(self, spec: OptimizationSpec) -> OptimizationResult:
        """
        Runs an optimization study.

        Args:
            spec: The specification of the optimization.

        Returns:
            An OptimizationResult with the best found candidate.
        """
        opt_id = uuid.uuid4().hex[:16]

        with open_session(self._study_runner._pipeline.db_path) as session:
            opt_row = OptimizationRow(
                id=opt_id,
                spec_json=spec.model_dump_json(),
                status="running",
                created_at_iso=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            )
            session.add(opt_row)
            session.commit()

        study_spec = self._engine.create_study_spec(spec)
        study_result = self._study_runner.run(study_spec)

        best_run = self._find_best_run(study_result, spec.objective)

        result = OptimizationResult(
            optimization_id=opt_id,
            study_id=study_result.study_id,
            best_run_id=best_run.run_id,
            best_run_result=best_run.to_json(),
        )

        with open_session(self._study_runner._pipeline.db_path) as session:
            opt_row = session.get(OptimizationRow, opt_id)
            opt_row.status = "completed"
            opt_row.result_json = result.model_dump_json()
            opt_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")

            # Link the study to the optimization
            study_row = session.get(self._study_runner.StudyRow, study_result.study_id)
            if study_row:
                study_row.optimization_id = opt_id

            session.commit()

        return result

    def _find_best_run(self, study_result, objective):
        """Finds the best run in a study based on the objective."""
        if objective == "maximize_cl_cd":
            best_run = None
            max_cl_cd = -1
            for run in study_result.runs:
                if run.xfoil_results:
                    # For simplicity, use the first result point for comparison
                    res = run.xfoil_results[0]
                    if res.cd > 0:
                        cl_cd = res.cl / res.cd
                        if cl_cd > max_cl_cd:
                            max_cl_cd = cl_cd
                            best_run = run
            return best_run
        else:
            raise NotImplementedError(f"Objective '{objective}' not implemented.")
