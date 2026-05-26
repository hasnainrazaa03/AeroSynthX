"""Tests for ``aerosynthx.openfoam.validators``."""

from __future__ import annotations

from pathlib import Path

from aerosynthx.intent.schemas import (
    AirfoilSpec,
    DesignIntent,
    FlowCondition,
    ProvenanceMap,
)
from aerosynthx.openfoam.case import build_case
from aerosynthx.openfoam.validators import validate_case_structure


def _intent() -> DesignIntent:
    return DesignIntent(
        airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0),
        flow=FlowCondition(altitude_m=0.0, velocity_m_s=20.0, mach=None, angle_of_attack_deg=2.0),
        assumptions=[],
        provenance=ProvenanceMap(fields={}),
        notes=None,
    )


def test_clean_case_has_no_issues(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    assert validate_case_structure(case) == []


def test_missing_directory_returns_single_issue(tmp_path: Path) -> None:
    issues = validate_case_structure(tmp_path / "does-not-exist")
    assert len(issues) == 1
    assert "not a directory" in issues[0]


def test_missing_file_is_reported(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    (case / "0" / "U").unlink()
    issues = validate_case_structure(case)
    assert any("0/U" in i for i in issues)


def test_unbalanced_braces_detected(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    target = case / "system" / "controlDict"
    target.write_text(
        "application simpleFoam;\nstartTime 0;\nendTime 1;\ndeltaT 1;\n{\n", encoding="utf-8"
    )
    issues = validate_case_structure(case)
    assert any("unbalanced braces" in i and "controlDict" in i for i in issues)


def test_missing_key_detected(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    # Remove `simulationType` key from turbulenceProperties.
    target = case / "constant" / "turbulenceProperties"
    text = target.read_text(encoding="utf-8").replace("simulationType", "xxx")
    target.write_text(text, encoding="utf-8")
    issues = validate_case_structure(case)
    assert any("simulationType" in i for i in issues)


def test_brace_walker_ignores_comments(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    # Inject extra braces inside both kinds of comments; structure must
    # still be considered balanced.
    target = case / "system" / "fvSchemes"
    text = target.read_text(encoding="utf-8")
    text = "// stray { brace inside line comment\n/* and { inside block */\n" + text
    target.write_text(text, encoding="utf-8")
    issues = validate_case_structure(case)
    assert not any("unbalanced braces" in i for i in issues)


def test_unterminated_block_comment_does_not_crash(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    target = case / "system" / "fvSolution"
    target.write_text("/* never closed", encoding="utf-8")
    issues = validate_case_structure(case)
    # File still exists; required keys missing => issues, but no crash.
    assert any("fvSolution" in i for i in issues)


def test_unterminated_line_comment_does_not_crash(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    target = case / "system" / "fvSchemes"
    # File ending in a line comment with no newline exercises the
    # end-of-file branch of the comment skipper.
    target.write_text(
        "ddtSchemes {default steadyState;}\n"
        "gradSchemes {default Gauss linear;}\n"
        "divSchemes {default none;}\n"
        "// trailing comment no newline",
        encoding="utf-8",
    )
    issues = validate_case_structure(case)
    assert not any("unbalanced braces" in i and "fvSchemes" in i for i in issues)


def test_extra_closing_brace_detected(tmp_path: Path) -> None:
    case = tmp_path / "case"
    build_case(_intent(), case)
    target = case / "system" / "controlDict"
    target.write_text(
        "application simpleFoam;\nstartTime 0;\nendTime 1;\ndeltaT 1;\n}\n", encoding="utf-8"
    )
    issues = validate_case_structure(case)
    assert any("unbalanced braces" in i and "controlDict" in i for i in issues)
