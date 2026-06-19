"""Tests for the deterministic offline intent parser."""

from __future__ import annotations

import pytest

from aerosynthx.intent import LLMParseError, parse_offline
from aerosynthx.intent.offline import OFFLINE_MODEL_NAME


def test_basic_velocity_request() -> None:
    res = parse_offline("Design a NACA 2412 at 50 m/s, 3 degree angle of attack.")
    assert res.model == OFFLINE_MODEL_NAME
    assert res.attempts == 1
    di = res.intent
    assert di.airfoil.designation == "2412"
    assert di.airfoil.family == "naca4"
    assert di.flow.velocity_m_s == pytest.approx(50.0)
    assert di.flow.mach is None
    assert di.flow.angle_of_attack_deg == pytest.approx(3.0)
    # No altitude requested; remains None.
    assert di.flow.altitude_m is None


def test_mach_request_defaults_altitude_to_sea_level() -> None:
    res = parse_offline("NACA 0012 at Mach 0.2, alpha 0.")
    di = res.intent
    assert di.flow.mach == pytest.approx(0.2)
    assert di.flow.altitude_m == pytest.approx(0.0)
    # The altitude=0 default should be recorded as an assumption.
    paths = [a.field_path for a in di.assumptions]
    assert "flow.altitude_m" in paths


def test_explicit_altitude_marked_user_provided() -> None:
    res = parse_offline(
        "NACA 4412 at 30 m/s and altitude of 1000 m, angle of attack 5 deg, chord 0.5 m."
    )
    di = res.intent
    assert di.flow.altitude_m == pytest.approx(1000.0)
    assert di.airfoil.chord_m == pytest.approx(0.5)
    assert di.provenance.fields["flow.altitude_m"] == "user_provided"
    assert di.provenance.fields["airfoil.chord_m"] == "user_provided"


def test_unit_conversion_for_chord() -> None:
    res = parse_offline("NACA 0012 at 20 m/s, chord 200 mm.")
    assert res.intent.airfoil.chord_m == pytest.approx(0.2)


def test_velocity_units_converted() -> None:
    res = parse_offline("NACA 0012 at 100 knots.")
    # 100 knots = 51.4444 m/s.
    assert res.intent.flow.velocity_m_s == pytest.approx(51.4444, rel=1e-4)


def test_sea_level_phrase_recognized() -> None:
    res = parse_offline("NACA 0012 at Mach 0.15, sea level.")
    assert res.intent.flow.altitude_m == pytest.approx(0.0)
    assert res.intent.provenance.fields["flow.altitude_m"] == "user_provided"


def test_chord_defaulted_with_assumption_when_missing() -> None:
    res = parse_offline("NACA 2412 at 40 m/s.")
    di = res.intent
    assert di.airfoil.chord_m == pytest.approx(1.0)
    assert di.provenance.fields["airfoil.chord_m"] == "inferred"
    assert any(a.field_path == "airfoil.chord_m" for a in di.assumptions)


def test_aoa_defaulted_with_assumption_when_missing() -> None:
    res = parse_offline("NACA 2412 at 40 m/s.")
    di = res.intent
    assert di.flow.angle_of_attack_deg == pytest.approx(0.0)
    assert di.provenance.fields["flow.angle_of_attack_deg"] == "inferred"


def test_reynolds_target_extracted_million_shorthand() -> None:
    res = parse_offline("NACA 0012 at 50 m/s, Reynolds 3 million.")
    assert res.intent.flow.reynolds_target == pytest.approx(3.0e6)


def test_reynolds_target_extracted_scientific() -> None:
    res = parse_offline("NACA 0012 at 50 m/s, Re = 1.5e6.")
    assert res.intent.flow.reynolds_target == pytest.approx(1.5e6)


# ----------------------------------------------------------------- bad


def test_empty_input_rejected() -> None:
    with pytest.raises(LLMParseError) as ei:
        parse_offline("   ")
    assert ei.value.code == "intent.offline.empty_input"


def test_non_string_input_rejected() -> None:
    with pytest.raises(LLMParseError) as ei:
        parse_offline(None)  # type: ignore[arg-type]
    assert ei.value.code == "intent.offline.empty_input"


def test_missing_airfoil_designation_rejected() -> None:
    with pytest.raises(LLMParseError) as ei:
        parse_offline("Design an airfoil at 50 m/s.")
    assert ei.value.code == "intent.offline.missing_airfoil"


def test_missing_speed_rejected() -> None:
    with pytest.raises(LLMParseError) as ei:
        parse_offline("Design a NACA 2412.")
    assert ei.value.code == "intent.offline.missing_speed"


def test_both_velocity_and_mach_rejected() -> None:
    with pytest.raises(LLMParseError) as ei:
        parse_offline("NACA 0012 at 50 m/s and Mach 0.15, sea level.")
    assert ei.value.code == "intent.offline.conflicting_speed"


def test_envelope_violation_propagates_from_schema() -> None:
    # Mach 0.5 exceeds the incompressible envelope; schema must reject.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        parse_offline("NACA 0012 at Mach 0.5, sea level.")


def test_3d_wing_parsing() -> None:
    res = parse_offline("3D wing, span 12m, root NACA 0012 chord 1.5m, tip NACA 4415 chord 0.75m, sweep 10, dihedral 2, twist 4, velocity 60 m/s")
    assert res.intent.wing is not None
    assert res.intent.wing.span == pytest.approx(12.0)
    assert res.intent.wing.sweep_deg == pytest.approx(10.0)
    assert res.intent.wing.dihedral_deg == pytest.approx(2.0)
    assert res.intent.wing.twist_deg == pytest.approx(4.0)
    assert res.intent.wing.root_airfoil.designation == "0012"
    assert res.intent.wing.root_airfoil.chord_m == pytest.approx(1.5)
    assert res.intent.wing.tip_airfoil.designation == "4415"
    assert res.intent.wing.tip_airfoil.chord_m == pytest.approx(0.75)
    assert res.intent.flow.velocity_m_s == pytest.approx(60.0)


def test_3d_wing_parsing_with_angles_and_aoa() -> None:
    res = parse_offline("3D wing, span 12.0m, sweep 10.0 deg, dihedral 2.0 deg, twist 4.0 deg, root NACA 0012 chord 1.5m, tip NACA 4415 chord 0.75m, velocity 60.0 m/s at alpha 2.0 deg")
    assert res.intent.wing is not None
    assert res.intent.wing.span == pytest.approx(12.0)
    assert res.intent.wing.sweep_deg == pytest.approx(10.0)
    assert res.intent.wing.dihedral_deg == pytest.approx(2.0)
    assert res.intent.wing.twist_deg == pytest.approx(4.0)
    assert res.intent.flow.angle_of_attack_deg == pytest.approx(2.0)

