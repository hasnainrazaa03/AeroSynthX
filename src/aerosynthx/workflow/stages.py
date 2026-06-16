"""Stage definitions for the AeroSynthX workflow pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class StageName(StrEnum):
    """Ordered pipeline stage names."""

    PARSE = "parse"
    COMPUTE = "compute"
    GEOMETRY = "geometry"
    WING_GEOMETRY = "wing_geometry"
    CASE = "case"
    SOLVE = "solve"
    XFOIL = "xfoil"
    PERSIST = "persist"


STAGE_ORDER: Final[tuple[StageName, ...]] = (
    StageName.PARSE,
    StageName.COMPUTE,
    StageName.GEOMETRY,
    StageName.CASE,
    StageName.PERSIST,
)
