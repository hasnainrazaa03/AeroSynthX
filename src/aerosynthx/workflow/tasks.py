"""Celery tasks for executing workflows."""

from pathlib import Path

from aerosynthx.task_queue import celery_app
from aerosynthx.workflow.pipeline import Pipeline
from aerosynthx.workflow.cancellation import RunControl


@celery_app.task(bind=True)
def execute_run_task(self, intent_text: str, out_root_str: str, analysis_mode: str, run_id: str):
    """
    Celery task to execute a single AeroSynthX run.
    """
    out_root = Path(out_root_str)
    pipeline = Pipeline(out_root=out_root)

    # Create a default RunControl for the background task.
    # Timeouts and cancellation for Celery tasks are handled differently
    # (e.g., via task-level time limits) and are out of scope for this phase.
    control = RunControl.create(timeout=None, cancel_token=None)

    result = pipeline.execute_run_sync(
        run_id=run_id,
        intent_text=intent_text,
        analysis_mode=analysis_mode,
        control=control,
        emit=lambda *a, **kw: None, # Progress emission is not yet wired for Celery
    )
    return result.to_json()
