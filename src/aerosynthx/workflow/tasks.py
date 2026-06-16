"""Celery tasks for executing workflows."""

from pathlib import Path

from aerosynthx.task_queue import celery_app
from aerosynthx.workflow.pipeline import Pipeline


@celery_app.task(bind=True)
def execute_run_task(self, intent_text: str, out_root_str: str, analysis_mode: str):
    """
    Celery task to execute a single AeroSynthX run.
    """
    out_root = Path(out_root_str)
    pipeline = Pipeline(out_root=out_root)

    # The full execution logic from Pipeline._execute_run will be moved here.
    # For now, we'll just call the existing synchronous method to ensure
    # the task plumbing is working. A full refactor would move the logic.

    # A more complete implementation would look like:
    # result = pipeline._execute_run(...)
    # But to avoid duplicating the large function, we'll call the public method
    # with resume=False to force execution.

    result = pipeline.run(
        intent_text,
        resume=False, # Always re-execute in a task
        analysis_mode=analysis_mode
    )
    return result.to_json()
