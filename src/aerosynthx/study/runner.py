"""Orchestrator for running parametric studies."""

import itertools
import json
import uuid
from datetime import UTC, datetime

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
        Runs a study defined by the StudySpec.

        Args:
            spec: The specification of the study to run.

        Returns:
            A StudyResult containing the aggregated results.
        """
        study_id = uuid.uuid4().hex[:16]
        intents = self._generate_intents(spec)

        with open_session(self._pipeline.db_path) as session:
            study_row = StudyRow(
                id=study_id,
                name=spec.study_name,
                spec_json=spec.model_dump_json(),
                status="running",
                created_at_iso=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            )
            session.add(study_row)
            session.commit()

        run_results = []
        for intent_dict in intents:
            # This is a simplified representation of the intent text for now
            intent_text = f"Study: {spec.study_name}, Airfoil: {intent_dict.get('airfoil', {}).get('designation', 'custom')}"
            result = self._pipeline.run(intent_text, analysis_mode="xfoil")
            run_results.append(result)

            # Link the run to the study
            with open_session(self._pipeline.db_path) as session:
                run_row = session.get(RunRow, result.run_id)
                if run_row:
                    run_row.study_id = study_id
                    session.commit()

        with open_session(self._pipeline.db_path) as session:
            study_row = session.get(StudyRow, study_id)
            study_row.status = "completed"
            study_row.completed_at_iso = datetime.now(tz=UTC).isoformat(timespec="seconds")
            session.commit()

        return StudyResult(
            study_id=study_id,
            study_name=spec.study_name,
            spec=spec,
            status="completed",
            runs=run_results,
        )

    def _generate_intents(self, spec: StudySpec) -> list[dict[str, Any]]:
        """Generates a list of DesignIntent dictionaries from a StudySpec."""
        variable_keys = list(spec.variables.keys())
        variable_values = list(spec.variables.values())

        intents = []
        for combination in itertools.product(*variable_values):
            intent_dict = spec.base_intent.copy()
            for i, key in enumerate(variable_keys):
                # This is a simple dot-notation update, e.g., "flow.reynolds_target"
                keys = key.split('.')
                d = intent_dict
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                d[keys[-1]] = combination[i]
            intents.append(intent_dict)

        return intents
