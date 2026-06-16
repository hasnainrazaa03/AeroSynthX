"""Tests for the optimizer schemas."""

from aerosynthx.optimizer.schemas import OptimizationSpec

def test_optimization_spec_valid():
    """Test creating a valid OptimizationSpec."""
    spec = OptimizationSpec(
        objective="maximize_cl_cd",
        design_space={
            "flow.reynolds_target": [1e6, 2e6]
        },
        base_intent={
            "airfoil": {"family": "naca4", "designation": "0012"},
            "flow": {"velocity_m_s": 50, "angle_of_attack_deg": 2.0}
        }
    )
    assert spec.objective == "maximize_cl_cd"
    assert len(spec.design_space["flow.reynolds_target"]) == 2
