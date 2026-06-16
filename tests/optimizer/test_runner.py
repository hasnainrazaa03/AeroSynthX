"""Tests for the OptimizationRunner."""

from unittest.mock import MagicMock

import pytest

from aerosynthx.optimizer.runner import OptimizationRunner
from aerosynthx.optimizer.schemas import OptimizationSpec
from aerosynthx.study.schemas import StudyResult
from aerosynthx.workflow.pipeline import RunResult

def _create_mock_study_runner(runs):
    mock_study_runner = MagicMock()
    mock_study_runner.run.return_value = StudyResult(
        study_id="study1", study_name="", spec=None, status="completed", runs=runs
    )
    return mock_study_runner

def test_optimization_runner_maximize_cl_cd():
    """Test the maximize_cl_cd objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 1.0, "cd": 0.1, "cm": 0.0}])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 1.2, "cd": 0.1, "cm": 0.0}])
    mock_study_runner = _create_mock_study_runner([run1, run2])

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="maximize_cl_cd", design_space={}, base_intent={})
    result = runner.run(spec)
    assert result.best_run_id == "run2"

def test_optimization_runner_minimize_cd():
    """Test the minimize_cd objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 1.0, "cd": 0.01, "cm": 0.0}])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 1.0, "cd": 0.005, "cm": 0.0}])
    mock_study_runner = _create_mock_study_runner([run1, run2])

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="minimize_cd", design_space={}, base_intent={})
    result = runner.run(spec)
    assert result.best_run_id == "run2"

def test_optimization_runner_target_cl():
    """Test the target_cl objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 0.8, "cd": 0.01, "cm": 0.0}])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[{"alpha_deg": 2.0, "cl": 0.55, "cd": 0.005, "cm": 0.0}])
    mock_study_runner = _create_mock_study_runner([run1, run2])

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="target_cl", target_cl=0.5, design_space={}, base_intent={})
    result = runner.run(spec)
    assert result.best_run_id == "run2"

def test_optimization_runner_no_results():
    """Test that an error is raised if no runs have results."""
    mock_study_runner = _create_mock_study_runner([])
    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="maximize_cl_cd", design_space={}, base_intent={})
    with pytest.raises(ValueError, match="Could not find a best run"):
        runner.run(spec)
