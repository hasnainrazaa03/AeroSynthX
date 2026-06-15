"""Tests for the study schemas."""

from aerosynthx.study.schemas import StudySpec

def test_study_spec_valid():
    """Test creating a valid StudySpec."""
    spec = StudySpec(
        study_name="Test Study",
        base_intent={
            "airfoil": {"family": "naca4", "designation": "0012"},
            "flow": {"velocity_m_s": 50, "angle_of_attack_deg": 0.0}
        },
        variables={
            "flow.angle_of_attack_deg": [0.0, 5.0, 10.0]
        }
    )
    assert spec.study_name == "Test Study"
    assert len(spec.variables["flow.angle_of_attack_deg"]) == 3
