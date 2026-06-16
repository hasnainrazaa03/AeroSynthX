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
    WingSpec,
)
from aerosynthx.openfoam.case import (
    TEMPLATE_NAME_2D,
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


def _intent_wing() -> DesignIntent:
    return DesignIntent(
        wing=WingSpec(
            span=10.0,
            root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
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


def test_build_case_2d_creates_all_files(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_naca4(), case)

    assert case.is_dir()
    for rel in expected_case_files():
        assert (case / rel).is_file(), f"missing {rel}"

    assert manifest.template_name == TEMPLATE_NAME_2D
    assert manifest.intent["airfoil"]["designation"] == "2412"


def test_build_case_3d_creates_all_files(tmp_path: Path) -> None:
    case = tmp_path / "case"
    manifest = build_case(_intent_wing(), case)

    assert case.is_dir()
    assert (case / "constant" / "triSurface" / "wing.stl").is_file()
    assert (case / "system" / "snappyHexMeshDict").is_file()
    allrun_content = (case / "Allrun").read_text()
    assert "snappyHexMesh" in allrun_content


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
    assert "49.87" in u_text
    assert "3.48" in u_text


def test_build_case_refuses_to_overwrite(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    with pytest.raises(CaseExistsError):
        build_case(_intent_naca4(), case)


def test_build_case_overwrite_replaces_directory(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent_naca4(), case)
    sentinel = case / "leftover.txt"
    sentinel.write_text("stale", encoding="utf-8")
    assert sentinel.exists()
    build_case(_intent_naca4(), case, overwrite=True)
    assert not sentinel.exists()


def test_build_case_rejects_existing_non_directory(tmp_path: Path) -> None:
    target = tmp_path / "case"
    target.write_text("not a dir", encoding="utf-8")
    with pytest.raises(CaseExistsError):
        build_case(_intent_naca4(), target, overwrite=True)


def test_envelope_guard_rejects_unsupported_family(tmp_path: Path) -> None:
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
