"""Structural validators for a generated OpenFOAM case directory.

These checks are deliberately *static*: they never execute OpenFOAM.
They catch the most common rendering or hand-edit mistakes:

- required files are present,
- braces are balanced in OpenFOAM dictionaries,
- known-required keys appear in their respective dictionaries.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from aerosynthx.openfoam.case import expected_case_files

# Required key tokens per dictionary file.
_REQUIRED_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "system/controlDict": ("application", "startTime", "endTime", "deltaT"),
    "system/fvSchemes": ("ddtSchemes", "gradSchemes", "divSchemes"),
    "system/fvSolution": ("solvers", "SIMPLE"),
    "system/blockMeshDict": ("vertices", "blocks", "boundary"),
    "constant/transportProperties": ("transportModel", "nu"),
    "constant/turbulenceProperties": ("simulationType", "RAS"),
    "0/U": ("dimensions", "internalField", "boundaryField"),
    "0/p": ("dimensions", "internalField", "boundaryField"),
    "0/k": ("dimensions", "internalField", "boundaryField"),
    "0/omega": ("dimensions", "internalField", "boundaryField"),
    "0/nut": ("dimensions", "internalField", "boundaryField"),
}


def _check_braces(text: str) -> bool:
    """Return ``True`` when ``{`` and ``}`` are balanced, ignoring comments."""
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # C-style line comment.
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        # C-style block comment.
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def _walk_required(case_dir: Path) -> Iterable[str]:
    for rel in expected_case_files():
        if not (case_dir / rel).is_file():
            yield f"missing file: {rel}"


def _walk_keys_and_braces(case_dir: Path) -> Iterable[str]:
    for rel, keys in _REQUIRED_KEYS.items():
        path = case_dir / rel
        if not path.is_file():
            # Already reported by _walk_required.
            continue
        text = path.read_text(encoding="utf-8")
        if not _check_braces(text):
            yield f"unbalanced braces in: {rel}"
        for key in keys:
            if key not in text:
                yield f"missing key {key!r} in: {rel}"


def validate_case_structure(case_dir: Path) -> list[str]:
    """Return a list of structural issues in ``case_dir``.

    An empty list means the case passed all static checks. The function
    never raises for ordinary structural problems; it only raises if
    ``case_dir`` itself is not a directory.

    Args:
        case_dir: Path to a generated case directory.

    Returns:
        Sorted list of human-readable issues.
    """
    if not case_dir.is_dir():
        return [f"not a directory: {case_dir}"]
    issues: list[str] = []
    issues.extend(_walk_required(case_dir))
    issues.extend(_walk_keys_and_braces(case_dir))
    return sorted(issues)
