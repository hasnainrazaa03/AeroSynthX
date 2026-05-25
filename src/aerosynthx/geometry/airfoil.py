"""The :class:`Airfoil` immutable result type."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Airfoil:
    """An immutable airfoil geometry.

    Coordinates are stored in Selig ordering: starting at the trailing
    edge, traversing the upper surface to the leading edge, then the
    lower surface back to the trailing edge. ``x`` and ``y`` are
    normalized by the chord (``x`` in [0, 1]); ``chord_m`` is the
    dimensional chord length carried as metadata for downstream
    consumers.

    Attributes:
        name: Short identifier (e.g. ``"NACA2412"``).
        chord_m: Chord length in meters. Informational; does not scale
            ``x`` or ``y``.
        x: Tuple of normalized x coordinates.
        y: Tuple of normalized y coordinates.
        closed_trailing_edge: Whether the trailing edge was generated
            with the closed-TE coefficient set.
        metadata: Read-only mapping of generator inputs, useful for
            run-manifest reproducibility.
    """

    name: str
    chord_m: float
    x: tuple[float, ...]
    y: tuple[float, ...]
    closed_trailing_edge: bool
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        """Defensively freeze the metadata mapping."""
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def n_points(self) -> int:
        """Number of coordinate pairs."""
        return len(self.x)
