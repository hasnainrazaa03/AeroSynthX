"""Smoke tests for Phase 0 scaffolding.

These tests verify that the package is importable and that basic
project metadata is in place. Real engineering tests arrive from
Phase 1 onward.
"""

from __future__ import annotations

import aerosynthx


def test_package_imports() -> None:
    """The package must be importable."""
    assert aerosynthx is not None


def test_version_is_set() -> None:
    """A SemVer-shaped version string must be exposed."""
    version = aerosynthx.__version__
    assert isinstance(version, str)
    parts = version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), f"Non-SemVer version: {version}"
