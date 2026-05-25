"""Matplotlib-backed airfoil rendering.

Uses the non-interactive ``Agg`` backend so the module is safe to import
on headless systems and inside CI. Matplotlib is imported lazily so the
geometry package can be used (for case generation, tests, etc.) without
forcing a Matplotlib import at package load time.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.errors import GeometryError

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


def _import_pyplot() -> Any:
    """Import Matplotlib pyplot with the ``Agg`` backend selected."""
    try:
        import matplotlib

        matplotlib.use("Agg", force=False)
        from matplotlib import pyplot as plt
    except ImportError as exc:  # pragma: no cover - matplotlib is required
        raise GeometryError(
            f"matplotlib is required for rendering: {exc}",
            code="geometry.render.missing_backend",
        ) from exc
    return plt


def _render(af: Airfoil, path: Path, *, fmt: str, dpi: int) -> None:
    plt = _import_pyplot()
    fig = plt.figure(figsize=(8, 2.5), dpi=dpi)
    try:
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(af.x, af.y, color="#1f77b4", linewidth=1.2)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title(af.name)
        ax.set_xlabel("x / c")
        ax.set_ylabel("y / c")
        ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(path), format=fmt, bbox_inches="tight")
    finally:
        plt.close(fig)


def render_airfoil_png(af: Airfoil, path: str | Path, *, dpi: int = 150) -> None:
    """Render the airfoil to a PNG file."""
    _render(af, Path(path), fmt="png", dpi=dpi)


def render_airfoil_svg(af: Airfoil, path: str | Path) -> None:
    """Render the airfoil to an SVG file."""
    _render(af, Path(path), fmt="svg", dpi=100)
