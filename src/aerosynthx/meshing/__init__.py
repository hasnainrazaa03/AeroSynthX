"""Package for 3D mesh generation."""

from aerosynthx.meshing.snappy import generate_snappy_dict
from aerosynthx.meshing.stl_exporter import export_wing_to_stl

__all__ = ["export_wing_to_stl", "generate_snappy_dict"]
