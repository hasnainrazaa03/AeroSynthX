"""Celery tasks for executing studies."""

from aerosynthx.task_queue import celery_app
from aerosynthx.study.runner import StudyRunner
from aerosynthx.study.schemas import StudySpec
from aerosynthx.workflow.pipeline import Pipeline


@celery_app.task(bind=True)
def execute_study_task(self, spec_dict: dict, out_root_str: str):
    """Celery task to execute a parametric study."""
    from pathlib import Path

    pipeline = Pipeline(out_root=Path(out_root_str))
    study_runner = StudyRunner(pipeline)
    spec = StudySpec.model_validate(spec_dict)

    # This will now block inside the Celery worker, which is what we want.
    # The web server returns immediately.
    result = study_runner.run_sync(spec)
    return result.model_dump()
