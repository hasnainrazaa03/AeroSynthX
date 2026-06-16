from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from aerosynthx.intent.schemas import DesignIntent, AirfoilSpec, WingSpec
from aerosynthx.openfoam.runner import (
    CommandResult,
    SolverExecutionError,
    openfoam_available,
    parse_force_coefficients,
    parse_force_coefficients_3d,
    run_case,
)

_SOLVER_LOG = """\
Time = 1
smoothSolver:  Solving for Ux, Initial residual = 0.5, Final residual = 1e-3
smoothSolver:  Solving for Ux, Initial residual = 0.01, Final residual = 1e-5
SIMPLE solution converged in 2 iterations
"""

_COEFF_DAT_2D = """\
# Force coefficients
# Time Cd Cs Cl CmPitch
100 0.0123 0.0 0.456 -0.01
200 0.0120 0.0 0.789 -0.02
"""

_COEFF_DAT_3D = """\
# Time            forces(1)       forces(2)       forces(3)       moments(1)      moments(2)      moments(3)
1000            (0.1 0.2 0.3)   (0.4 0.5 0.6)   (0.7 0.8 0.9)   (1.0 1.1 1.2)   (1.3 1.4 1.5)   (1.6 1.7 1.8)
"""


def test_parse_residuals_extracts_iterations_and_convergence() -> None:
    iterations, final_residual, converged = parse_residuals(_SOLVER_LOG)
    assert iterations == 2
    assert final_residual == pytest.approx(0.01)
    assert converged is True


def test_parse_force_coefficients_2d() -> None:
    coeffs = parse_force_coefficients(_COEFF_DAT_2D)
    assert coeffs == {
        "cd": pytest.approx(0.012),
        "cl": pytest.approx(0.789),
        "cm": pytest.approx(-0.02),
    }


def test_parse_force_coefficients_3d() -> None:
    # This is a placeholder test, as the 3D parsing logic is not fully defined yet.
    # We will assume for now it has the same keys.
    # A proper implementation would parse the vector forces and calculate coefficients.
    pass


def test_openfoam_available_checks_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aerosynthx.openfoam.runner.shutil.which", lambda app: f"/usr/bin/{app}")
    assert openfoam_available({"WM_PROJECT_DIR": "/opt/openfoam"}) is True


def _fake_runner_factory(
    case_dir: Path, *, fail_on: str | None = None, with_coeffs: bool = True
) -> Callable[..., CommandResult]:
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        app = command[0]
        if app == fail_on:
            return CommandResult(command=tuple(command), returncode=1, stdout="boom", stderr="bad")
        stdout = _SOLVER_LOG if app == "simpleFoam" else f"{app} done"
        if app == "simpleFoam" and with_coeffs:
            target = case_dir / "postProcessing" / "forceCoeffs1" / "0"
            target.mkdir(parents=True, exist_ok=True)
            (target / "coefficient.dat").write_text(_COEFF_DAT_2D, encoding="utf-8")
        return CommandResult(command=tuple(command), returncode=0, stdout=stdout, stderr="")

    return runner


def test_run_case_2d_success(tmp_path: Path) -> None:
    (tmp_path / "Allrun").write_text("blockMesh\nsimpleFoam")
    intent = DesignIntent(airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0), flow={})
    result = run_case(tmp_path, intent=intent, runner=_fake_runner_factory(tmp_path))
    assert result.ran is True
    assert result.converged is True
    assert result.commands == ("blockMesh", "simpleFoam")
    assert result.coefficients["cl"] == pytest.approx(0.789)


def test_run_case_3d_success(tmp_path: Path) -> None:
    (tmp_path / "Allrun").write_text("blockMesh\nsnappyHexMesh\nsimpleFoam")
    intent = DesignIntent(wing=WingSpec(span=1, root_airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0)), flow={})

    def runner_3d(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        app = command[0]
        stdout = _SOLVER_LOG if app == "simpleFoam" else f"{app} done"
        if app == "simpleFoam":
            target = tmp_path / "postProcessing" / "forces" / "0"
            target.mkdir(parents=True, exist_ok=True)
            (target / "forceCoeffs.dat").write_text(_COEFF_DAT_3D, encoding="utf-8")
        return CommandResult(command=tuple(command), returncode=0, stdout=stdout, stderr="")

    result = run_case(tmp_path, intent=intent, runner=runner_3d)
    assert result.ran is True
    assert result.commands == ("blockMesh", "snappyHexMesh", "simpleFoam")
    # Placeholder for 3D coefficient parsing test
    assert "cl" in result.coefficients


def test_run_case_raises_on_solver_failure(tmp_path: Path) -> None:
    (tmp_path / "Allrun").write_text("blockMesh\nsimpleFoam")
    intent = DesignIntent(airfoil=AirfoilSpec(family="naca4", designation="0012", chord_m=1.0), flow={})
    with pytest.raises(SolverExecutionError):
        run_case(tmp_path, intent=intent, runner=_fake_runner_factory(tmp_path, fail_on="simpleFoam"))
    assert (tmp_path / "log.simpleFoam").read_text(encoding="utf-8") == "boom\nbad"
