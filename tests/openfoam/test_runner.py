from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from aerosynthx.openfoam.runner import (
    CommandResult,
    SolverExecutionError,
    openfoam_available,
    parse_force_coefficients,
    parse_residuals,
    run_case,
)

_SOLVER_LOG = """\
Time = 1
smoothSolver:  Solving for Ux, Initial residual = 0.5, Final residual = 1e-3
smoothSolver:  Solving for Ux, Initial residual = 0.01, Final residual = 1e-5
SIMPLE solution converged in 2 iterations
"""

_COEFF_DAT = """\
# Force coefficients
# Time Cd Cs Cl CmPitch
100 0.0123 0.0 0.456 -0.01
200 0.0120 0.0 0.789 -0.02
"""


def test_parse_residuals_extracts_iterations_and_convergence() -> None:
    iterations, final_residual, converged = parse_residuals(_SOLVER_LOG)
    assert iterations == 2
    assert final_residual == pytest.approx(0.01)
    assert converged is True


def test_parse_residuals_handles_empty_log() -> None:
    iterations, final_residual, converged = parse_residuals("nothing here")
    assert iterations == 0
    assert final_residual is None
    assert converged is False


def test_parse_force_coefficients_maps_columns() -> None:
    coeffs = parse_force_coefficients(_COEFF_DAT)
    assert coeffs == {
        "cd": pytest.approx(0.012),
        "cl": pytest.approx(0.789),
        "cm": pytest.approx(-0.02),
    }


def test_parse_force_coefficients_no_data_returns_empty() -> None:
    assert parse_force_coefficients("# only a header\n") == {}
    assert parse_force_coefficients("") == {}


def test_parse_force_coefficients_skips_blank_lines() -> None:
    text = "\n# Time Cl\n\n100 0.42\n\n"
    assert parse_force_coefficients(text) == {"cl": pytest.approx(0.42)}


def test_parse_force_coefficients_skips_unparsable_values() -> None:
    text = "# Time Cl\n100 not-a-number\n"
    assert parse_force_coefficients(text) == {}


def test_openfoam_available_requires_wm_project_dir() -> None:
    assert openfoam_available({}) is False


def test_openfoam_available_checks_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aerosynthx.openfoam.runner.shutil.which", lambda app: f"/usr/bin/{app}")
    assert openfoam_available({"WM_PROJECT_DIR": "/opt/openfoam"}) is True
    monkeypatch.setattr("aerosynthx.openfoam.runner.shutil.which", lambda app: None)
    assert openfoam_available({"WM_PROJECT_DIR": "/opt/openfoam"}) is False


def _fake_runner_factory(
    case_dir: Path, *, fail_on: str | None = None, with_coeffs: bool = True
) -> Callable[..., CommandResult]:
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        app = command[0]
        if app == fail_on:
            return CommandResult(command=tuple(command), returncode=1, stdout="boom", stderr="bad")
        stdout = _SOLVER_LOG if app == "simpleFoam" else "blockMesh done"
        if app == "simpleFoam" and with_coeffs:
            target = case_dir / "postProcessing" / "forceCoeffs1" / "0"
            target.mkdir(parents=True, exist_ok=True)
            (target / "coefficient.dat").write_text(_COEFF_DAT, encoding="utf-8")
        return CommandResult(command=tuple(command), returncode=0, stdout=stdout, stderr="")

    return runner


def test_run_case_success(tmp_path: Path) -> None:
    result = run_case(tmp_path, runner=_fake_runner_factory(tmp_path))
    assert result.ran is True
    assert result.converged is True
    assert result.iterations == 2
    assert result.commands == ("blockMesh", "simpleFoam")
    assert result.coefficients["cl"] == pytest.approx(0.789)
    assert (tmp_path / "log.blockMesh").is_file()
    assert (tmp_path / "log.simpleFoam").is_file()


def test_run_case_without_coefficients(tmp_path: Path) -> None:
    result = run_case(tmp_path, runner=_fake_runner_factory(tmp_path, with_coeffs=False))
    assert result.coefficients == {}


def test_run_case_raises_on_solver_failure(tmp_path: Path) -> None:
    with pytest.raises(SolverExecutionError):
        run_case(tmp_path, runner=_fake_runner_factory(tmp_path, fail_on="simpleFoam"))
    # The failing command's log is still written.
    assert (tmp_path / "log.simpleFoam").read_text(encoding="utf-8") == "boom\nbad"


def test_run_case_ignores_empty_coefficient_file(tmp_path: Path) -> None:
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        app = command[0]
        if app == "simpleFoam":
            target = case_dir = tmp_path / "postProcessing" / "f" / "0"
            target.mkdir(parents=True, exist_ok=True)
            (target / "coefficient.dat").write_text("# header only\n", encoding="utf-8")
            _ = case_dir
        return CommandResult(command=tuple(command), returncode=0, stdout=_SOLVER_LOG, stderr="")

    result = run_case(tmp_path, runner=runner)
    assert result.coefficients == {}


def test_run_case_falls_back_to_force_coeffs_file(tmp_path: Path) -> None:
    def runner(command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        if command[0] == "simpleFoam":
            empty = tmp_path / "postProcessing" / "a" / "0"
            empty.mkdir(parents=True, exist_ok=True)
            (empty / "coefficient.dat").write_text("# header only\n", encoding="utf-8")
            forces = tmp_path / "postProcessing" / "b" / "0"
            forces.mkdir(parents=True, exist_ok=True)
            (forces / "forceCoeffs.dat").write_text(_COEFF_DAT, encoding="utf-8")
        return CommandResult(command=tuple(command), returncode=0, stdout=_SOLVER_LOG, stderr="")

    result = run_case(tmp_path, runner=runner)
    assert result.coefficients["cl"] == pytest.approx(0.789)
