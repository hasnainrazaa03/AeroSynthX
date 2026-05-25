"""Boundary unit conversion.

The engineering core works in SI base units (see ``docs/ARCHITECTURE.md``,
section 3). This module is the single entry point for converting a
user-supplied value + unit string into a canonical SI ``float``.

Typical usage::

    chord_m = to_si(1.2, "m", dimension="length")
    velocity_m_s = to_si(50, "m/s", dimension="velocity")
    altitude_m = to_si(5000, "ft", dimension="length")

If ``dimension`` is provided, the input unit must be compatible with it;
otherwise a :class:`UnitError` is raised.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Final

import pint

from aerosynthx.physics.errors import UnitError

# A single, shared, lazily-constructed registry keeps `pint`'s internal
# caches warm and prevents accidental cross-registry comparisons.
# Typed as ``Any`` because ``pint.UnitRegistry`` is a generic at the type
# level whose parameters are uninteresting to callers of this module.
_REGISTRY: Any = None


def _registry() -> Any:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = pint.UnitRegistry()
    return _REGISTRY


# Mapping of supported "dimension" labels to a canonical SI target unit.
# The canonical unit is what we convert into; the dimension check uses
# pint's own dimensionality matching for safety.
_DIMENSION_TARGETS: Final[dict[str, str]] = {
    "length": "meter",
    "mass": "kilogram",
    "time": "second",
    "temperature": "kelvin",
    "pressure": "pascal",
    "velocity": "meter / second",
    "density": "kilogram / meter ** 3",
    "dynamic_viscosity": "pascal * second",
    "kinematic_viscosity": "meter ** 2 / second",
    "angle": "radian",
    "dimensionless": "dimensionless",
}


@lru_cache(maxsize=64)
def _target_unit(dimension: str) -> Any:
    try:
        return _registry().parse_units(_DIMENSION_TARGETS[dimension])
    except KeyError as exc:
        msg = f"unknown dimension label {dimension!r}"
        raise UnitError(msg, code="physics.unit.unknown_dimension") from exc


def to_si(value: float, unit: str, *, dimension: str | None = None) -> float:
    """Convert ``value`` expressed in ``unit`` into a canonical SI float.

    Args:
        value: Numeric magnitude. Must be finite.
        unit: A unit string parseable by ``pint`` (e.g. ``"m"``, ``"ft"``,
            ``"m/s"``, ``"deg C"``).
        dimension: Optional expected dimension label. One of the keys of
            ``_DIMENSION_TARGETS``. If provided, the input unit must be
            convertible to the canonical SI unit for that dimension.

    Returns:
        The value in the canonical SI unit for its dimension, as a
        Python ``float``.

    Raises:
        UnitError: If ``unit`` is empty, unparseable, or incompatible with
            the requested ``dimension``.
    """
    if not isinstance(unit, str) or not unit.strip():
        raise UnitError(
            "unit string must be a non-empty string",
            code="physics.unit.invalid",
        )

    reg = _registry()
    try:
        # ``Quantity(value, unit)`` (rather than ``value * unit``) is required
        # so offset units like degC do not raise OffsetUnitCalculusError.
        quantity = reg.Quantity(value, unit)
    except (
        pint.errors.UndefinedUnitError,
        pint.errors.DefinitionSyntaxError,
        AttributeError,
        TypeError,
        ValueError,
    ) as exc:
        raise UnitError(
            f"could not parse unit {unit!r}: {exc}",
            code="physics.unit.invalid",
        ) from exc

    if dimension is None:
        # Without a declared dimension, return the magnitude in the unit's
        # base (SI) representation.
        return float(quantity.to_base_units().magnitude)

    target = _target_unit(dimension)
    try:
        converted = quantity.to(target)
    except pint.errors.DimensionalityError as exc:
        raise UnitError(
            f"unit {unit!r} is not compatible with dimension {dimension!r}",
            code="physics.unit.dimension_mismatch",
        ) from exc
    return float(converted.magnitude)
