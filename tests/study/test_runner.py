from pathlib import Path
from unittest.mock import MagicMock
import pytest

from aerosynthx.study.runner import StudyRunner
from aerosynthx.study.schemas import StudySpec
from aerosynthx.workflow.pipeline import Pipeline, RunResult
from aerosynthx.workflow.db import StudyRow, open_session

def test_study_runner_generates_and_runs_intents():
    """Test that the StudyRunner correctly generates and runs intents."""
    mock_pipeline = MagicMock()
    mock_pipeline.execute_run_sync.return_value = RunResult(
        run_id="mock_run",
        intent_text="",
        status="completed",
        intent=None,
        flow_state=None,
        case_dir=None,
        manifest_digest=None,
        stages=(),
    )

    runner = StudyRunner(mock_pipeline)
    spec = StudySpec(
        study_name="Test Reynolds Sweep",
        base_intent={
            "airfoil": {"family": "naca4", "designation": "0012", "chord_m": 1.0},
            "flow": {"velocity_m_s": 50, "angle_of_attack_deg": 2.0},
        },
        variables={
            "flow.reynolds_target": [1e6, 2e6]
        }
    )

    result = runner.run(spec)

    assert result.status == "completed"
    assert len(result.runs) == 2
    assert mock_pipeline.execute_run_sync.call_count == 2


def test_study_runner_handles_exceptions_and_sets_status_failed(tmp_path: Path) -> None:
    from unittest.mock import patch
    pipeline = Pipeline(out_root=tmp_path)
    runner = StudyRunner(pipeline)
    
    with open_session(pipeline.db_path) as session:
        study_row = StudyRow(
            id="failed_study_123",
            name="Failed Study Test",
            spec_json="{}",
            status="queued",
            created_at_iso="2026-06-18T12:00:00"
        )
        session.add(study_row)
        session.commit()
    
    spec = StudySpec(
        study_name="Failed Study Test",
        base_intent={"airfoil": {"family": "naca4", "designation": "0012", "chord_m": 1.0}, "flow": {"velocity_m_s": 50, "angle_of_attack_deg": 2.0}},
        variables={"flow.reynolds_target": [1e6]}
    )
    
    with patch.object(runner, "_generate_intents") as mock_gen:
        mock_gen.side_effect = Exception("Simulated intent generation failure")
        with pytest.raises(Exception):
            runner.run_sync(spec, study_id="failed_study_123")
        
    with open_session(pipeline.db_path) as session:
        study_row = session.get(StudyRow, "failed_study_123")
        assert study_row is not None
        assert study_row.status == "failed"

