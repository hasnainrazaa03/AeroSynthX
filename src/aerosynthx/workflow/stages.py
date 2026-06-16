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
    MESH = "mesh"
    CASE = "case"
    SOLVE = "solve"
    XFOIL = "xfoil"
    PERSIST = "persist"


STAGE_ORDER_2D: Final[tuple[StageName, ...]] = (
    StageName.PARSE,
    StageName.COMPUTE,
    StageName.GEOMETRY,
    StageName.CASE,
    StageName.PERSIST,
)

STAGE_ORDER_3D: Final[tuple[StageName, ...]] = (
    StageName.PARSE,
    StageName.COMPUTE,
    StageName.WING_GEOMETRY,
    StageName.MESH,
    StageName.PERSIST,
)
