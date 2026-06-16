"""Export a Wing object to an STL file string."""

import numpy as np

from aerosynthx.geometry.wing import Wing


def export_wing_to_stl(wing: Wing) -> str:
    """
    Converts a Wing object into an STL file format as a string.

    This function creates a triangular mesh from the structured point cloud
    of the wing's coordinates.
    """
    stl_parts = ["solid wing"]
    coords = np.array(wing.coordinates)
    num_stations, num_points_per_section, _ = coords.shape

    for i in range(num_stations - 1):
        for j in range(num_points_per_section - 1):
            p1 = coords[i, j]
            p2 = coords[i + 1, j]
            p3 = coords[i, j + 1]
            p4 = coords[i + 1, j + 1]

            # Create two triangles for each quad
            # Triangle 1: p1, p2, p4
            normal1 = np.cross(p2 - p1, p4 - p1)
            normal1 /= np.linalg.norm(normal1)
            stl_parts.append(f"  facet normal {normal1[0]:.6f} {normal1[1]:.6f} {normal1[2]:.6f}")
            stl_parts.append("    outer loop")
            stl_parts.append(f"      vertex {p1[0]:.6f} {p1[1]:.6f} {p1[2]:.6f}")
            stl_parts.append(f"      vertex {p2[0]:.6f} {p2[1]:.6f} {p2[2]:.6f}")
            stl_parts.append(f"      vertex {p4[0]:.6f} {p4[1]:.6f} {p4[2]:.6f}")
            stl_parts.append("    endloop")
            stl_parts.append("  endfacet")

            # Triangle 2: p1, p4, p3
            normal2 = np.cross(p4 - p1, p3 - p1)
            normal2 /= np.linalg.norm(normal2)
            stl_parts.append(f"  facet normal {normal2[0]:.6f} {normal2[1]:.6f} {normal2[2]:.6f}")
            stl_parts.append("    outer loop")
            stl_parts.append(f"      vertex {p1[0]:.6f} {p1[1]:.6f} {p1[2]:.6f}")
            stl_parts.append(f"      vertex {p4[0]:.6f} {p4[1]:.6f} {p4[2]:.6f}")
            stl_parts.append(f"      vertex {p3[0]:.6f} {p3[1]:.6f} {p3[2]:.6f}")
            stl_parts.append("    endloop")
            stl_parts.append("  endfacet")

    stl_parts.append("endsolid wing")
    return "\n".join(stl_parts)
