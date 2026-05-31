"""Opt-in OpenFOAM solver execution with an injectable command runner.

Running a solver requires an OpenFOAM installation, so by default the
pipeline only *generates* a case. When execution is requested this module
shells out to ``blockMesh`` and ``simpleFoam`` and parses their logs for
convergence residuals and (when present) force coefficients.

The process boundary is isolated behind a :class:`CommandRunner` callable
so the harness — including the residual/coefficient parsers — is fully
unit-testable without OpenFOAM installed.
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

from aerosynthx.openfoam.errors import OpenFoamError


class OpenFoamNotAvailableError(OpenFoamError):
    """Raised when solver execution is requested but OpenFOAM is absent."""

    code = "openfoam.runner.unavailable"


class SolverExecutionError(OpenFoamError):
    """Raised when an OpenFOAM application exits with a non-zero status."""

    code = "openfoam.runner.failed"


_SOLVER_APPS: Final[tuple[str, ...]] = ("blockMesh", "simpleFoam")
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
    """Return ``True`` when an OpenFOAM toolchain looks usable.

    Requires ``WM_PROJECT_DIR`` to be set and every solver application to
    resolve on ``PATH``.
    """
    source = os.environ if env is None else env
    if not source.get("WM_PROJECT_DIR"):
        return False
    return all(shutil.which(app) is not None for app in _SOLVER_APPS)


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
    """Extract Cl/Cd/Cm from an OpenFOAM ``coefficient.dat``-style table.

    The last comment line is treated as the column header (the first
    column is the time/iteration); the last data row supplies the values.
    Unknown columns are ignored.
    """
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


def _read_coefficients(case_dir: Path) -> dict[str, float]:
    post = case_dir / "postProcessing"
    if not post.is_dir():
        return {}
    candidates = sorted(post.glob("**/coefficient.dat")) + sorted(post.glob("**/forceCoeffs.dat"))
    for path in candidates:
        coeffs = parse_force_coefficients(path.read_text(encoding="utf-8"))
        if coeffs:
            return coeffs
    return {}


def _write_log(case_dir: Path, app: str, result: CommandResult) -> None:
    body = result.stdout
    if result.stderr:
        body = f"{body}\n{result.stderr}"
    (case_dir / f"log.{app}").write_text(body, encoding="utf-8")


def run_case(
    case_dir: Path,
    *,
    runner: CommandRunner,
    timeout: float = 600.0,
) -> SolveResult:
    """Run ``blockMesh`` then ``simpleFoam`` in ``case_dir``.

    Args:
        case_dir: A generated case directory.
        runner: Callable that executes each command. Inject a fake runner
            to exercise the harness offline; use
            :func:`default_command_runner` for real execution.
        timeout: Per-command timeout in seconds.

    Returns:
        A :class:`SolveResult` with residual and coefficient summaries.

    Raises:
        SolverExecutionError: An application exited with a non-zero code.
    """
    executed: list[str] = []
    for app in _SOLVER_APPS:
        result = runner([app], cwd=case_dir, timeout=timeout)
        _write_log(case_dir, app, result)
        executed.append(app)
        if result.returncode != 0:
            raise SolverExecutionError(
                f"{app} exited with code {result.returncode}",
                code="openfoam.runner.failed",
            )

    solver_log = (case_dir / f"log.{_SOLVER_APPS[-1]}").read_text(encoding="utf-8")
    iterations, final_residual, converged = parse_residuals(solver_log)
    return SolveResult(
        ran=True,
        converged=converged,
        iterations=iterations,
        final_residual=final_residual,
        coefficients=_read_coefficients(case_dir),
        commands=tuple(executed),
    )
