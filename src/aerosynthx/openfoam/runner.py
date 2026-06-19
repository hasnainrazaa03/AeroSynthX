"""Opt-in OpenFOAM solver execution with an injectable command runner.

Running a solver requires an OpenFOAM installation, so by default the
pipeline only *generates* a case. When execution is requested this module
shells out to the necessary OpenFOAM applications and parses their logs for
convergence residuals and (when present) force coefficients.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from aerosynthx.intent.schemas import DesignIntent
from aerosynthx.openfoam.errors import OpenFoamError


class OpenFoamNotAvailableError(OpenFoamError):
    """Raised when solver execution is requested but OpenFOAM is absent."""
    code = "openfoam.runner.unavailable"


class SolverExecutionError(OpenFoamError):
    """Raised when an OpenFOAM application exits with a non-zero status."""
    code = "openfoam.runner.failed"


_RESIDUAL_RE: Final = re.compile(r"Solving for Ux, Initial residual = ([0-9.eE+-]+)")
_CONVERGED_RE: Final = re.compile(r"SIMPLE solution converged", re.IGNORECASE)
_COEFF_KEYS: Final[Mapping[str, str]] = {
    "cl": "cl",
    "cd": "cd",
    "cm": "cm",
    "cmpitch": "cm",
}


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of a single command invocation."""
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Callable that executes a command in ``cwd`` and returns its result."""
    def __call__(self, command: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        """Execute ``command`` in ``cwd`` and return its :class:`CommandResult`."""
        ...


@dataclass(frozen=True, slots=True)
class SolveResult:
    """Structured outcome of running a case through the solver."""
    ran: bool
    converged: bool
    iterations: int
    final_residual: float | None
    coefficients: dict[str, float]
    commands: tuple[str, ...]


def openfoam_available(env: Mapping[str, str] | None = None) -> bool:
    """Return ``True`` when an OpenFOAM toolchain looks usable."""
    source = os.environ if env is None else env
    if not source.get("WM_PROJECT_DIR"):
        return False
    # Check for a few key executables
    return all(shutil.which(app) is not None for app in ["blockMesh", "simpleFoam", "snappyHexMesh"])


def default_command_runner(
    command: Sequence[str], *, cwd: Path, timeout: float
) -> CommandResult:  # pragma: no cover - exercised only with real OpenFOAM
    """Run ``command`` via :func:`subprocess.run`, capturing its output."""
    proc = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        command=tuple(command),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def parse_residuals(log_text: str) -> tuple[int, float | None, bool]:
    """Extract ``(iterations, final_residual, converged)`` from a solver log."""
    residuals = [float(m.group(1)) for m in _RESIDUAL_RE.finditer(log_text)]
    final_residual = residuals[-1] if residuals else None
    converged = _CONVERGED_RE.search(log_text) is not None
    return len(residuals), final_residual, converged


def parse_force_coefficients(text: str) -> dict[str, float]:
    """Extract Cl/Cd/Cm from a 2D OpenFOAM ``coefficient.dat``-style table."""
    header: list[str] | None = None
    last_row: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            header = stripped.lstrip("#").split()
            continue
        last_row = stripped.split()
    if header is None or last_row is None:
        return {}

    coeffs: dict[str, float] = {}
    for name, value in zip(header, last_row, strict=False):
        key = _COEFF_KEYS.get(name.lower())
        if key is None:
            continue
        try:
            coeffs[key] = float(value)
        except ValueError:
            continue
    return coeffs


def parse_force_coefficients_3d(text: str) -> dict[str, float]:
    """Extract Cl/Cd/Cm from a 3D OpenFOAM ``forceCoeffs.dat`` file."""
    last_line = None
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            last_line = line
    if not last_line:
        return {}

    groups = re.findall(r"\(([^)]+)\)", last_line)
    if len(groups) < 6:
        return parse_force_coefficients(text)

    try:
        f1 = [float(x) for x in groups[0].split()]
        m1 = [float(x) for x in groups[3].split()]
        cl = f1[2] if len(f1) > 2 else 0.0
        cd = f1[0] if len(f1) > 0 else 0.0
        cm = m1[1] if len(m1) > 1 else 0.0
        return {"cl": cl, "cd": cd, "cm": cm}
    except (ValueError, IndexError):
        return {}


def _read_coefficients(case_dir: Path, is_3d: bool) -> dict[str, float]:
    post = case_dir / "postProcessing"
    if not post.is_dir():
        return {}

    # In 3D, the output is typically in forceCoeffs.dat, not coefficient.dat
    # and might be in a different subdirectory.
    # For now, we'll just search for both.
    candidates = sorted(post.glob("**/forceCoeffs.dat")) + sorted(post.glob("**/coefficient.dat"))

    for path in candidates:
        parser = parse_force_coefficients_3d if is_3d else parse_force_coefficients
        coeffs = parser(path.read_text(encoding="utf-8"))
        if coeffs:
            return coeffs
    return {}


def _write_log(case_dir: Path, app: str, result: CommandResult) -> None:
    body = result.stdout
    if result.stderr:
        body = f"{body}\n{result.stderr}"
    (case_dir / f"log.{app}").write_text(body, encoding="utf-8")


def _get_commands_from_allrun(case_dir: Path) -> list[str]:
    """Parses the Allrun script to find the sequence of commands to execute."""
    allrun_path = case_dir / "Allrun"
    if not allrun_path.is_file():
        return []

    valid_apps = {"blockMesh", "snappyHexMesh", "simpleFoam"}
    commands = []
    content = allrun_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for word in line.split():
            clean_word = word.strip('"\'')
            if clean_word in valid_apps:
                commands.append(clean_word)
                break
    return commands


def run_case(
    case_dir: Path,
    *,
    intent: DesignIntent,
    runner: CommandRunner,
    timeout: float = 3600.0, # Increased default for 3D
) -> SolveResult:
    """
    Executes the sequence of commands found in the Allrun script in ``case_dir``.

    Args:
        case_dir: A generated case directory.
        intent: The design intent, used to determine if the case is 2D or 3D.
        runner: Callable that executes each command.
        timeout: Per-command timeout in seconds.

    Returns:
        A :class:`SolveResult` with residual and coefficient summaries.

    Raises:
        SolverExecutionError: An application exited with a non-zero code.
    """
    commands_to_run = _get_commands_from_allrun(case_dir)
    if not commands_to_run:
        raise SolverExecutionError("No Allrun script found or it is empty.", code="openfoam.runner.no_script")

    executed: list[str] = []
    solver_log = ""
    for app in commands_to_run:
        result = runner([app], cwd=case_dir, timeout=timeout)
        _write_log(case_dir, app, result)
        executed.append(app)
        if result.returncode != 0:
            raise SolverExecutionError(
                f"{app} exited with code {result.returncode}",
                code="openfoam.runner.failed",
            )
        if app == "simpleFoam": # Assume simpleFoam is the main solver
            solver_log = result.stdout

    iterations, final_residual, converged = parse_residuals(solver_log)

    is_3d = intent.wing is not None
    coefficients = _read_coefficients(case_dir, is_3d)

    return SolveResult(
        ran=True,
        converged=converged,
        iterations=iterations,
        final_residual=final_residual,
        coefficients=coefficients,
        commands=tuple(executed),
    )
