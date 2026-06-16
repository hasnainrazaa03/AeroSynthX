"""Tests for the OptimizationRunner."""

from unittest.mock import MagicMock

from aerosynthx.optimizer.runner import OptimizationRunner
from aerosynthx.optimizer.schemas import OptimizationSpec
from aerosynthx.study.schemas import StudyResult
from aerosynthx.workflow.pipeline import RunResult

def test_optimization_runner_finds_best_run():
    """Test that the OptimizationRunner correctly finds the best run."""
    mock_study_runner = MagicMock()

    # Create mock run results
    run1 = RunResult(
        run_id="run1", intent_text="", status="completed", intent=None, flow_state=None,
        case_dir=None, manifest_digest=None, stages=(),
        xfoil_results=[{"alpha_deg": 2.0, "cl": 1.0, "cd": 0.1, "cm": 0.0}] # Cl/Cd = 10
    )
    run2 = RunResult(
        run_id="run2", intent_text="", status="completed", intent=None, flow_state=None,
        case_dir=None, manifest_digest=None, stages=(),
        xfoil_results=[{"alpha_deg": 2.0, "cl": 1.2, "cd": 0.1, "cm": 0.0}] # Cl/Cd = 12
    )

    mock_study_runner.run.return_value = StudyResult(
        study_id="study1", study_name="", spec=None, status="completed", runs=[run1, run2]
    )

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(
        objective="maximize_cl_cd",
        design_space={},
        base_intent={}
    )

    result = runner.run(spec)

    assert result.best_run_id == "run2"
