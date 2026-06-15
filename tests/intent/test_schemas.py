"""Tests for the intent schemas (Pydantic v2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aerosynthx.intent.schemas import (
    AirfoilSpec,
    Assumption,
    DesignIntent,
    FlowCondition,
    ProvenanceMap,
    design_intent_json_schema,
)

# ----------------------------------------------------------- AirfoilSpec


def test_airfoil_spec_naca4_valid() -> None:
    s = AirfoilSpec(family="naca4", designation="2412", chord_m=1.0)
    assert s.designation == "2412"
    assert s.coordinates is None


def test_airfoil_spec_naca5_valid() -> None:
    s = AirfoilSpec(family="naca5", designation="23012", chord_m=1.0)
    assert s.designation == "23012"
    assert s.coordinates is None


def test_airfoil_spec_custom_valid() -> None:
    s = AirfoilSpec(family="custom", chord_m=1.0, coordinates=[(1.0, 0.0), (0.0, 0.0), (1.0, 0.0)])
    assert s.designation is None
    assert s.coordinates == [(1.0, 0.0), (0.0, 0.0), (1.0, 0.0)]


def test_airfoil_spec_custom_rejects_missing_coordinates() -> None:
    with pytest.raises(ValidationError, match="`coordinates` must be provided"):
        AirfoilSpec(family="custom", chord_m=1.0)


def test_airfoil_spec_custom_rejects_designation() -> None:
    with pytest.raises(ValidationError, match="`designation` must not be provided"):
        AirfoilSpec(family="custom", designation="1234", chord_m=1.0, coordinates=[(1.0, 0.0), (0.0, 0.0), (1.0, 0.0)])


def test_airfoil_spec_naca_rejects_coordinates() -> None:
    with pytest.raises(ValidationError, match="`coordinates` must not be provided"):
        AirfoilSpec(family="naca4", designation="2412", chord_m=1.0, coordinates=[(1.0, 0.0)])


@pytest.mark.parametrize("bad", ["", "241", "12345", "abcd", "24a2"])
def test_airfoil_spec_naca4_rejects_bad_designation(bad: str) -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca4", designation=bad, chord_m=1.0)


@pytest.mark.parametrize("bad", ["", "2301", "123456", "abcde", "23a12"])
def test_airfoil_spec_naca5_rejects_bad_designation(bad: str) -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca5", designation=bad, chord_m=1.0)


def test_airfoil_spec_naca4_rejects_camber_without_position() -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca4", designation="2012", chord_m=1.0)


def test_airfoil_spec_naca4_rejects_zero_thickness() -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca4", designation="0000", chord_m=1.0)


def test_airfoil_spec_naca5_rejects_zero_thickness() -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca5", designation="23000", chord_m=1.0)


def test_airfoil_spec_rejects_non_positive_chord() -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca4", designation="2412", chord_m=0.0)


def test_airfoil_spec_rejects_unknown_family() -> None:
    with pytest.raises(ValidationError):
        AirfoilSpec(family="naca6", designation="64012", chord_m=1.0)  # type: ignore[arg-type]


def test_airfoil_spec_is_frozen() -> None:
    s = AirfoilSpec(family="naca4", designation="2412", chord_m=1.0)
    with pytest.raises(ValidationError):
        s.designation = "4412"


# --------------------------------------------------------- FlowCondition


def test_flow_with_velocity_only() -> None:
    f = FlowCondition(velocity_m_s=50.0, angle_of_attack_deg=3.0)
    assert f.velocity_m_s == 50.0
    assert f.mach is None


def test_flow_with_mach_requires_altitude() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(mach=0.2, angle_of_attack_deg=0.0)


def test_flow_with_mach_and_altitude() -> None:
    f = FlowCondition(mach=0.2, altitude_m=1000.0, angle_of_attack_deg=0.0)
    assert f.mach == 0.2


def test_flow_rejects_both_velocity_and_mach() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(velocity_m_s=50.0, mach=0.2, altitude_m=0.0, angle_of_attack_deg=0.0)


def test_flow_rejects_neither_velocity_nor_mach() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(angle_of_attack_deg=0.0)


def test_flow_rejects_compressible_mach() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(mach=0.35, altitude_m=0.0, angle_of_attack_deg=0.0)


def test_flow_rejects_excessive_alpha() -> None:
    with pytest.raises(ValidationError):
        FlowCondition(velocity_m_s=10.0, angle_of_attack_deg=30.0)


@pytest.mark.parametrize("alt", [-1.0, 25_000.0])
def test_flow_rejects_out_of_range_altitude(alt: float) -> None:
    with pytest.raises(ValidationError):
        FlowCondition(velocity_m_s=10.0, altitude_m=alt, angle_of_attack_deg=0.0)


def test_flow_accepts_none_altitude_with_velocity() -> None:
    f = FlowCondition(velocity_m_s=10.0, angle_of_attack_deg=0.0)
    assert f.altitude_m is None


# ---------------------------------------------------------- DesignIntent


def _minimal_intent() -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(family="naca4", designation="2412", chord_m=1.0),
        flow=FlowCondition(velocity_m_s=50.0, angle_of_attack_deg=2.0),
        assumptions=[
            Assumption(field_path="x.y", value=1, reason="default"),
        ],
        provenance=ProvenanceMap(
            fields={
                "airfoil.family": "inferred",
                "airfoil.designation": "user_provided",
                "airfoil.chord_m": "user_provided",
                "flow.velocity_m_s": "user_provided",
                "flow.angle_of_attack_deg": "user_provided",
                "flow.altitude_m": "inferred",
            }
        ),
        notes=None,
    )


def test_design_intent_round_trip_json() -> None:
    di = _minimal_intent()
    payload = di.model_dump()
    restored = DesignIntent.model_validate(payload)
    assert restored == di


def test_design_intent_rejects_extra_fields() -> None:
    payload = _minimal_intent().model_dump()
    payload["unknown_field"] = "x"
    with pytest.raises(ValidationError):
        DesignIntent.model_validate(payload)


def test_design_intent_is_frozen() -> None:
    di = _minimal_intent()
    with pytest.raises(ValidationError):
        di.notes = "hi"


def test_provenance_rejects_unknown_tag() -> None:
    with pytest.raises(ValidationError):
        ProvenanceMap(fields={"x": "guessed"})  # type: ignore[dict-item]


def test_json_schema_exposed() -> None:
    schema = design_intent_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "airfoil" in schema["properties"]
