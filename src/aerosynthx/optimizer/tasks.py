"""Celery tasks for executing optimizations."""

from aerosynthx.task_queue import celery_app
from aerosynthx.optimizer.runner import OptimizationRunner
from aerosynthx.optimizer.schemas import OptimizationSpec
from aerosynthx.study.runner import StudyRunner
from aerosynthx.workflow.pipeline import Pipeline


@celery_app.task(bind=True)
def execute_optimization_task(self, spec_dict: dict, out_root_str: str, opt_id: str):
    """Celery task to execute an optimization study."""
    from pathlib import Path

    pipeline = Pipeline(out_root=Path(out_root_str))
    study_runner = StudyRunner(pipeline)
    opt_runner = OptimizationRunner(study_runner)

    # We validate but we need to put opt_id somewhere so runner knows
    # But runner takes the spec. We can just pass the opt_id to run_sync.
    spec = OptimizationSpec.model_validate(spec_dict)

    result = opt_runner.run_sync(spec, opt_id=opt_id)
    return result.model_dump()
