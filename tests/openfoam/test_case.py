"""Tests for ``aerosynthx.openfoam.case.build_case``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aerosynthx.intent.schemas import (
    AirfoilSpec,
    DesignIntent,
    FlowCondition,
    ProvenanceMap,
)
from aerosynthx.openfoam.case import (
    TEMPLATE_NAME,
    TEMPLATE_VERSION,
    build_case,
    expected_case_files,
)
from aerosynthx.openfoam.errors import (
    CaseExistsError,
    EnvelopeViolationError,
)


def _intent_naca4() -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(family="naca4", designation="2412", chord_m=1.0),
        flow=FlowCondition(
            altitude_m=0.0,
            velocity_m_s=50.0,
            mach=None,
            angle_of_attack_deg=4.0,
        ),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes="test",
    )


def _intent_naca5() -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(family="naca5", designation="23012", chord_m=1.0),
        flow=FlowCondition(
            altitude_m=0.0,
            velocity_m_s=50.0,
            mach=None,
            angle_of_attack_deg=4.0,
        ),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes="test",
    )


def _intent_custom() -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(
            family="custom",
            chord_m=1.0,
            coordinates=[
                (1.0, 0.0),
                (0.5, 0.1),
                (0.0, 0.0),
                (0.5, -0.1),
                (1.0, 0.0),
            ],
        ),
        flow=FlowCondition(
            altitude_m=0.0,
            velocity_m_s=50.0,
            mach=None,
            angle_of_attack_deg=4.0,
        ),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes="test",
    )


def test_build_case_naca4_creates_all_files(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_naca4(), case)

    assert case.is_dir()
    for rel in expected_case_files():
        assert (case / rel).is_file(), f"missing {rel}"

    # Manifest sanity.
    assert manifest.template_name == TEMPLATE_NAME
    assert manifest.template_version == TEMPLATE_VERSION
    assert manifest.intent["airfoil"]["designation"] == "2412"
    assert manifest.flow_state["velocity_m_s"] == pytest.approx(50.0)
    assert "0/U" in manifest.files
    assert "aerosynthx_manifest.json" not in manifest.files


def test_build_case_naca5_creates_all_files(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_naca5(), case)

    assert case.is_dir()
    for rel in expected_case_files():
        assert (case / rel).is_file(), f"missing {rel}"

    # Manifest sanity.
    assert manifest.intent["airfoil"]["designation"] == "23012"
    assert (case / "constant" / "triSurface" / "airfoil.dat").is_file()


def test_build_case_custom_creates_all_files(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_custom(), case)

    assert case.is_dir()
    for rel in expected_case_files():
        assert (case / rel).is_file(), f"missing {rel}"

    # Manifest sanity.
    assert manifest.intent["airfoil"]["family"] == "custom"
    assert (case / "constant" / "triSurface" / "airfoil.dat").is_file()


def test_manifest_file_on_disk_matches_returned_manifest(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_naca4(), case)
    on_disk = json.loads((case / "aerosynthx_manifest.json").read_text(encoding="utf-8"))
    assert on_disk["template_name"] == manifest.template_name
    assert set(on_disk["files"]) == set(manifest.files)


def test_velocity_vector_written_into_U_file(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    u_text = (case / "0" / "U").read_text(encoding="utf-8")
    # AoA 4 deg => ux ~ 50 * cos(4) ~ 49.878, uy ~ 50 * sin(4) ~ 3.488.
    assert "49.87" in u_text
    assert "3.48" in u_text


def test_build_case_refuses_to_overwrite(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    with pytest.raises(CaseExistsError) as exc:
        build_case(_intent_naca4(), case)
    assert exc.value.code == "openfoam.case.exists"


def test_build_case_overwrite_replaces_directory(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    sentinel = case / "leftover.txt"
    sentinel.write_text("stale", encoding="utf-8")
    assert sentinel.exists()
    build_case(_intent_naca4(), case, overwrite=True)
    assert not sentinel.exists()
    assert (case / "0" / "U").is_file()


def test_build_case_rejects_existing_non_directory(tmp_path: Path) -> None:
    target = tmp_path / "case"
    target.write_text("not a dir", encoding="utf-8")
    with pytest.raises(CaseExistsError) as exc:
        build_case(_intent_naca4(), target, overwrite=True)
    assert exc.value.code == "openfoam.case.not_a_directory"


def test_envelope_guard_rejects_unsupported_family(tmp_path: Path) -> None:
    # Schema doesn't permit family != "naca4", "naca5", or "custom"; bypass with model_construct
    # to exercise the defensive guard at the openfoam boundary.
    spec = AirfoilSpec.model_construct(family="naca6", designation="64012", chord_m=1.0)
    intent = DesignIntent.model_construct(
        airfoil=spec,
        flow=FlowCondition(altitude_m=0.0, velocity_m_s=30.0, mach=None, angle_of_attack_deg=0.0),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes=None,
    )
    with pytest.raises(EnvelopeViolationError):
        build_case(intent, tmp_path / "case")


def test_envelope_guard_rejects_intent_without_speed(tmp_path: Path) -> None:
    flow = FlowCondition.model_construct(
        altitude_m=0.0, velocity_m_s=None, mach=None, angle_of_attack_deg=0.0
    )
    intent = DesignIntent.model_construct(
        airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        flow=flow,
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes=None,
    )
    with pytest.raises(EnvelopeViolationError):
        build_case(intent, tmp_path / "case")


def test_build_case_is_deterministic(tmp_path: Path) -> None:
    a = build_case(_intent_naca4(), tmp_path / "a")
    b = build_case(_intent_naca4(), tmp_path / "b")
    # File digests for all rendered template files match across runs;
    # only the manifest itself varies due to timestamps.
    assert a.files == b.files


def test_allrun_is_executable(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    mode = (case / "Allrun").stat().st_mode & 0o777
    assert mode & 0o100  # owner-executable bit set


def test_template_render_error_is_wrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from jinja2 import TemplateSyntaxError

    from aerosynthx.openfoam import case as case_mod
    from aerosynthx.openfoam.errors import TemplateRenderError

    class _BrokenTemplate:
        def render(self, **_: object) -> str:
            raise TemplateSyntaxError("boom", 1)

    class _BrokenEnv:
        def get_template(self, _name: str) -> _BrokenTemplate:
            return _BrokenTemplate()

    monkeypatch.setattr(case_mod, "_make_env", lambda: _BrokenEnv())
    with pytest.raises(TemplateRenderError) as exc:
        build_case(_intent_naca4(), tmp_path / "case")
    assert exc.value.code == "openfoam.template.render_failed"
