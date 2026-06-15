"""Curve generation utilities."""

import numpy as np


def cosine_spacing(n_points: int) -> np.ndarray:
    """
    Generates a 1D array of points with cosine spacing.

    This distribution clusters points near the start (0) and end (1) of the
    interval, which is useful for airfoil generation where more detail is
    needed at the leading and trailing edges.

    Args:
        n_points: The number of points to generate.

    Returns:
        A NumPy array of points.
    """
    theta = np.linspace(0, np.pi, n_points)
    return 0.5 * (1 - np.cos(theta))
