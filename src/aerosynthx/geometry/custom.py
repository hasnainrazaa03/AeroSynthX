"""Generator for user-supplied custom airfoil coordinates."""

import numpy as np

from aerosynthx.geometry.airfoil import Airfoil
from aerosynthx.geometry.errors import GeometryError
from aerosynthx.geometry.validators import validate_airfoil


def custom_airfoil(
    coordinates: list[tuple[float, float]],
    *,
    chord_m: float = 1.0,
    name: str = "Custom Airfoil",
) -> Airfoil:
    """
    Creates an Airfoil object from a user-provided list of coordinates.

    The function validates that the coordinates are normalized and in the correct
    Selig format (TE -> Upper -> LE -> Lower -> TE).

    Args:
        coordinates: A list of [x, y] pairs defining the airfoil shape,
                     normalized to a chord length of 1.
        chord_m: The target chord length in meters to scale the airfoil to.
        name: An optional name for the airfoil.

    Returns:
        An Airfoil object.

    Raises:
        GeometryError: If the coordinate data is invalid.
    """
    if not coordinates or len(coordinates) < 3:
        raise GeometryError(
            "Custom airfoil must have at least 3 coordinate points.",
            code="geometry.custom.insufficient_points",
        )

    coords = np.array(coordinates)
    x, y = coords[:, 0], coords[:, 1]

    # Validate that the input coordinates are normalized
    if not np.isclose(np.min(x), 0.0) or not np.isclose(np.max(x), 1.0):
        raise GeometryError(
            "Custom airfoil coordinates must be normalized to a chord of 1 (x-range from 0 to 1).",
            code="geometry.custom.not_normalized",
        )

    airfoil = Airfoil(
        name=name,
        chord_m=float(chord_m),
        x=tuple(x),
        y=tuple(y),
        closed_trailing_edge=np.isclose(y[0], y[-1]),
        metadata={"generator": "custom"},
    )

    # Use existing validators to check for closure, monotonicity, etc.
    try:
        validate_airfoil(airfoil)
    except GeometryError as e:
        # Re-raise with a more specific error code for custom airfoils
        raise GeometryError(
            f"Invalid custom airfoil coordinates: {e}",
            code="geometry.custom.validation_failed",
        ) from e

    return airfoil
