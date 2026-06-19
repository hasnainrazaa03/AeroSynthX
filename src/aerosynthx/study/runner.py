"""Orchestrator for running parametric studies."""

import itertools
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aerosynthx.intent.schemas import DesignIntent
from aerosynthx.study.schemas import StudySpec, StudyResult
from aerosynthx.workflow.db import RunRow, StudyRow, open_session
from aerosynthx.workflow.pipeline import Pipeline


class StudyRunner:
    """Executes and manages parametric studies."""

    def __init__(self, pipeline: Pipeline):
        self._pipeline = pipeline

    def run(self, spec: StudySpec) -> StudyResult:
        """
        Submits an asynchronous study job to Celery.
        """
        from aerosynthx.study.tasks import execute_study_task

        study_id = uuid.uuid4().hex[:16]

        with open_session(self._pipeline.db_path) as session:
            study_row = StudyRow(
                id=study_id,
                name=spec.study_name,
                spec_json=spec.model_dump_json(),
                status="queued",
                created_at_iso=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            )
            session.add(study_row)
            session.commit()

        # Add study_id to the spec dict so the task knows which DB row to update
        spec_dict = spec.model_dump()
        spec_dict["_study_id"] = study_id

        from aerosynthx.task_queue import celery_app
        if celery_app.conf.task_always_eager:
            return self.run_sync(spec, study_id=study_id)

        execute_study_task.delay(
            spec_dict=spec_dict,
            out_root_str=str(self._pipeline._out_root),
        )

        return StudyResult(
            study_id=study_id,
            study_name=spec.study_name,
            spec=spec,
            status="queued",
            runs=[],
        )

    def run_sync(self, spec: StudySpec, study_id: str | None = None) -> StudyResult:
        """
        Synchronously runs a study defined by the StudySpec.
        This is intended to be called by a Celery task.
        """
        # Retrieve the pre-generated study ID, or create a new one
        if study_id is None:
            spec_dict = spec.model_dump()
            study_id = spec_dict.pop("_study_id", uuid.uuid4().hex[:16])

        # We need a clean spec without internal fields for DB persistence
        spec_dict = spec.model_dump()
        spec_dict.pop("_study_id", None)
        clean_spec = StudySpec.model_validate(spec_dict)

        with open_session(self._pipeline.db_path) as session:
            study_row = session.get(StudyRow, study_id)
            if study_row:
                study_row.status = "running"
                session.commit()

        try:
            intents = self._generate_intents(clean_spec)
            run_results = []
            for intent_dict in intents:
                intent_text = f"Study: {clean_spec.study_name}, Airfoil: {intent_dict.get('airfoil', {}).get('designation', 'custom')}"

                # Use run_sync for individual runs to avoid spawning thousands of nested Celery tasks
                # which could overwhelm the broker and make dependency tracking harder.
                from aerosynthx.workflow.cancellation import RunControl
                run_id = uuid.uuid4().hex[:16]
                result = self._pipeline.execute_run_sync(
                    run_id=run_id,
                    intent_text=intent_text,
                    analysis_mode="xfoil",
                    control=RunControl.create(timeout=None, cancel_token=None),
                    emit=lambda *a, **kw: None,
                )
                run_results.append(result)

                with open_session(self._pipeline.db_path) as session:
                    run_row = session.get(RunRow, result.run_id)
                    if run_row:
                        run_row.study_id = study_id
                        session.commit()

            with open_session(self._pipeline.db_path) as session:
                study_row = session.get(StudyRow, study_id)
                if study_row:
                    study_row.status = "completed"
                    study_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
                    session.commit()

            return StudyResult(
                study_id=study_id,
                study_name=clean_spec.study_name,
                spec=clean_spec,
                status="completed",
                runs=run_results,
            )
        except Exception:
            with open_session(self._pipeline.db_path) as session:
                study_row = session.get(StudyRow, study_id)
                if study_row:
                    study_row.status = "failed"
                    study_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
                    session.commit()
            raise

    def _generate_intents(self, spec: StudySpec) -> list[dict[str, Any]]:
        """Generates a list of DesignIntent dictionaries from a StudySpec."""
        variable_keys = list(spec.variables.keys())
        variable_values = list(spec.variables.values())

        intents = []
        for combination in itertools.product(*variable_values):
            intent_dict = spec.base_intent.copy()
            for i, key in enumerate(variable_keys):
                keys = key.split('.')
                d = intent_dict
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                d[keys[-1]] = combination[i]
            intents.append(intent_dict)

        return intents
