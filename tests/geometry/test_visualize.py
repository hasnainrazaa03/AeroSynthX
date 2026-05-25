"""Smoke tests for the Matplotlib-backed airfoil renderer."""

from __future__ import annotations

from pathlib import Path

from aerosynthx.geometry import naca4, render_airfoil_png, render_airfoil_svg


def test_render_png_writes_file(tmp_path: Path) -> None:
    af = naca4("2412", n_per_side=80)
    out = tmp_path / "sub" / "naca2412.png"
    render_airfoil_png(af, out, dpi=80)
    assert out.exists()
    assert out.stat().st_size > 0
    # PNG magic number.
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_svg_writes_file(tmp_path: Path) -> None:
    af = naca4("0012", n_per_side=60)
    out = tmp_path / "naca0012.svg"
    render_airfoil_svg(af, out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml")
    assert "<svg" in text


def test_render_png_accepts_str_path(tmp_path: Path) -> None:
    af = naca4("4412", n_per_side=40)
    out = tmp_path / "naca4412.png"
    render_airfoil_png(af, str(out))
    assert out.exists()
