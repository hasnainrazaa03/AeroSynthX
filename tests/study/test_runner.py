"""Tests for the StudyRunner."""

from unittest.mock import MagicMock

from aerosynthx.study.runner import StudyRunner
from aerosynthx.study.schemas import StudySpec
from aerosynthx.workflow.pipeline import RunResult

def test_study_runner_generates_and_runs_intents():
    """Test that the StudyRunner correctly generates and runs intents."""
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = RunResult(
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
    assert mock_pipeline.run.call_count == 2
