from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aerosynthx.optimizer.runner import OptimizationRunner
from aerosynthx.optimizer.schemas import OptimizationSpec
from aerosynthx.study.runner import StudyRunner
from aerosynthx.study.schemas import StudyResult, StudySpec
from aerosynthx.workflow.pipeline import Pipeline, RunResult
from aerosynthx.workflow.db import OptimizationRow, open_session
from aerosynthx.xfoil import XfoilResult

def _create_mock_study_runner(runs):
    mock_study_runner = MagicMock()
    dummy_spec = StudySpec(study_name="dummy", base_intent={}, variables={})
    mock_study_runner.run_sync.return_value = StudyResult(
        study_id="study1", study_name="", spec=dummy_spec, status="completed", runs=runs
    )
    return mock_study_runner

def test_optimization_runner_maximize_cl_cd():
    """Test the maximize_cl_cd objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=1.0, cd=0.1, cm=0.0)])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=1.2, cd=0.1, cm=0.0)])
    mock_study_runner = _create_mock_study_runner([run1, run2])

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="maximize_cl_cd", design_space={}, base_intent={})
    result = runner.run(spec)
    assert result.best_run_id == "run2"

def test_optimization_runner_minimize_cd():
    """Test the minimize_cd objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=1.0, cd=0.01, cm=0.0)])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=1.0, cd=0.005, cm=0.0)])
    mock_study_runner = _create_mock_study_runner([run1, run2])

    runner = OptimizationRunner(mock_study_runner)
    spec = OptimizationSpec(objective="minimize_cd", design_space={}, base_intent={})
    result = runner.run(spec)
    assert result.best_run_id == "run2"

def test_optimization_runner_target_cl():
    """Test the target_cl objective."""
    run1 = RunResult(run_id="run1", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=0.8, cd=0.01, cm=0.0)])
    run2 = RunResult(run_id="run2", intent_text="", status="completed", intent=None, flow_state=None, case_dir=None, manifest_digest=None, stages=(), xfoil_results=[XfoilResult(alpha_deg=2.0, cl=0.55, cd=0.005, cm=0.0)])
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


def test_optimization_runner_handles_exceptions_and_sets_status_failed(tmp_path: Path) -> None:
    from unittest.mock import patch
    pipeline = Pipeline(out_root=tmp_path)
    study_runner = StudyRunner(pipeline)
    runner = OptimizationRunner(study_runner)
    
    with open_session(pipeline.db_path) as session:
        opt_row = OptimizationRow(
            id="failed_opt_123",
            spec_json="{}",
            status="queued",
            created_at_iso="2026-06-18T12:00:00"
        )
        session.add(opt_row)
        session.commit()
        
    spec = OptimizationSpec(
        objective="maximize_cl_cd",
        design_space={"airfoil.designation": ["0012"]},
        base_intent={"airfoil": {"family": "naca4", "chord_m": 1.0}, "flow": {"velocity_m_s": 50, "angle_of_attack_deg": 4.0}}
    )
    
    with patch.object(runner._engine, "create_study_spec") as mock_create:
        mock_create.side_effect = Exception("Simulated optimization failure")
        with pytest.raises(Exception):
            runner.run_sync(spec, opt_id="failed_opt_123")
        
    with open_session(pipeline.db_path) as session:
        opt_row = session.get(OptimizationRow, "failed_opt_123")
        assert opt_row is not None
        assert opt_row.status == "failed"

