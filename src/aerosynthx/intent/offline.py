"""Deterministic, offline regex-based intent parser.

This parser exists for two reasons:

1. Tests in this repository must run without network access; the offline
   parser is the parser-under-test in unit tests.
2. As a fallback for environments where no LLM provider is configured.

It implements a small grammar of extraction patterns and falls back to
documented defaults (recorded as :class:`Assumption` entries) for any
missing fields. It cannot understand free-form prose the way an LLM can;
its goal is to be predictable, not eloquent.
"""

from __future__ import annotations

import re

from aerosynthx.intent.errors import LLMParseError
from aerosynthx.intent.schemas import (
    AirfoilSpec,
    Assumption,
    DesignIntent,
    FlowCondition,
    ParseResult,
    ProvenanceMap,
)
from aerosynthx.physics.errors import UnitError
from aerosynthx.physics.units import to_si

OFFLINE_MODEL_NAME = "offline"

# --- Extraction patterns (case-insensitive). ---

_NACA4_RE = re.compile(r"naca[-_\s]*([0-9]{4})\b", re.IGNORECASE)
_NACA5_RE = re.compile(r"naca[-_\s]*([0-9]{5})\b", re.IGNORECASE)
_BARE_4DIGIT_RE = re.compile(r"(?<![0-9])([0-9]{4})(?![0-9])")
_BARE_5DIGIT_RE = re.compile(r"(?<![0-9])([0-9]{5})(?![0-9])")
_CHORD_RE = re.compile(
    r"""(?ix)
    chord
    (?:[\s_-]*(?:length|of))?
    [\s:=]*
    ([0-9]*\.?[0-9]+)
    \s*
    (millimeters|millimeter|centimeters|centimeter|meters|metres|meter|metre
     |inches|inch|feet|mm|cm|ft|in|m)?
    \b
    """,
)
_ALT_RE = re.compile(
    r"""(?ix)
    (?:altitude|elevation)
    (?:\s*of)?
    [\s:=]*
    ([0-9]*\.?[0-9]+)
    \s*
    (kilometers|kilometer|meters|meter|feet|km|ft|m)
    \b
    """,
)
_SEA_LEVEL_RE = re.compile(r"sea[-\s]?level", re.IGNORECASE)
_MACH_RE = re.compile(
    r"""(?ix)\bmach\b\s*[:=]?\s*([0-9]*\.?[0-9]+)|\bm\s*=\s*([0-9]*\.?[0-9]+)\b"""
)
_VELOCITY_RE = re.compile(
    r"""(?ix)
    ([0-9]*\.?[0-9]+)
    \s*
    (m/s|mps|meters/second|meter/second|km/h|kph|kilometers/hour|kilometer/hour
     |mph|miles/hour|mile/hour|knots|knot|kts|kt)
    \b
    """,
)
_AOA_RE = re.compile(
    r"""(?ix)
    (?:
        (?:angle[\s_-]*of[\s_-]*attack|aoa|alpha|\u03b1)
        [\s:=]*
        (-?[0-9]*\.?[0-9]+)
        \s*
        (?:deg|degree|degrees|\u00b0)?
    |
        (-?[0-9]*\.?[0-9]+)
        \s*
        (?:deg|degree|degrees|\u00b0)
    )
    """,
)
_REYNOLDS_RE = re.compile(
    r"""(?ix)
    (?:reynolds|\bre\b)
    [\s:=]*
    (?:of\s+)?
    ([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)
    (?:\s*(?:million|m))?
    """,
)

_VELOCITY_UNIT_NORMALIZE = {
    "mps": "m/s",
    "meters/second": "m/s",
    "meter/second": "m/s",
    "kph": "km/h",
    "kilometers/hour": "km/h",
    "kilometer/hour": "km/h",
    "miles/hour": "mph",
    "mile/hour": "mph",
    "kt": "knot",
    "kts": "knot",
    "knots": "knot",
}

# Default values applied when the user did not specify a field.
_DEFAULT_CHORD_M = 1.0
_DEFAULT_AOA_DEG = 0.0


def _to_si_or_error(value: float, unit: str, *, dimension: str, field: str) -> float:
    try:
        return to_si(value, unit, dimension=dimension)
    except UnitError as exc:
        raise LLMParseError(
            f"could not convert {field}: {exc}",
            code="intent.offline.unit",
        ) from exc


def _extract_naca(text: str) -> tuple[str, str] | None:
    """Extracts a NACA designation and its family ('naca4' or 'naca5')."""
    m5 = _NACA5_RE.search(text)
    if m5:
        return m5.group(1), "naca5"

    m4 = _NACA4_RE.search(text)
    if m4:
        return m4.group(1), "naca4"

    m5_bare = _BARE_5DIGIT_RE.search(text)
    if m5_bare:
        return m5_bare.group(1), "naca5"

    m4_bare = _BARE_4DIGIT_RE.search(text)
    if m4_bare:
        return m4_bare.group(1), "naca4"

    return None


def _extract_chord_m(text: str) -> float | None:
    m = _CHORD_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit:
        return _to_si_or_error(value, unit.lower(), dimension="length", field="chord")
    return value # Assume meters if no unit is provided


def _extract_altitude_m(text: str) -> float | None:
    if _SEA_LEVEL_RE.search(text):
        return 0.0
    m = _ALT_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    return _to_si_or_error(value, unit, dimension="length", field="altitude")


def _extract_velocity_m_s(text: str) -> float | None:
    m = _VELOCITY_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    unit = _VELOCITY_UNIT_NORMALIZE.get(unit, unit)
    return _to_si_or_error(value, unit, dimension="velocity", field="velocity")


def _extract_mach(text: str) -> float | None:
    m = _MACH_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    return float(raw)


def _extract_aoa_deg(text: str) -> float | None:
    m = _AOA_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    return float(raw)


def _extract_reynolds(text: str) -> float | None:
    m = _REYNOLDS_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    value = float(raw)
    tail = text[m.end() - 10 : m.end() + 10].lower()
    if "million" in tail or re.search(r"\bm\b", tail):
        value *= 1.0e6
    return value


def parse_offline(text: str) -> ParseResult:
    """Parse ``text`` deterministically without using any LLM.

    Returns a :class:`ParseResult` whose ``model`` field is the constant
    :data:`OFFLINE_MODEL_NAME`. Raises :class:`LLMParseError` for inputs
    that lack the minimum required information (a NACA designation and
    a flow speed).
    """
    if not isinstance(text, str) or not text.strip():
        raise LLMParseError(
            "intent input must be a non-empty string",
            code="intent.offline.empty_input",
        )

    naca_result = _extract_naca(text)
    if naca_result is None:
        raise LLMParseError(
            "could not find a NACA 4-digit or 5-digit designation in the input",
            code="intent.offline.missing_airfoil",
        )
    designation, family = naca_result

    velocity = _extract_velocity_m_s(text)
    mach = _extract_mach(text)
    if velocity is None and mach is None:
        raise LLMParseError(
            "could not find a flow speed (velocity or Mach) in the input",
            code="intent.offline.missing_speed",
        )
    if velocity is not None and mach is not None:
        raise LLMParseError(
            "input specifies both velocity and Mach; provide only one",
            code="intent.offline.conflicting_speed",
        )

    altitude = _extract_altitude_m(text)
    aoa = _extract_aoa_deg(text)
    chord = _extract_chord_m(text)
    reynolds = _extract_reynolds(text)

    assumptions: list[Assumption] = []
    provenance: dict[str, str] = {
        "airfoil.family": "user_provided",
        "airfoil.designation": "user_provided",
        "flow.angle_of_attack_deg": "user_provided" if aoa is not None else "inferred",
        "airfoil.chord_m": "user_provided" if chord is not None else "inferred",
    }

    if chord is None:
        chord = _DEFAULT_CHORD_M
        assumptions.append(
            Assumption(
                field_path="airfoil.chord_m",
                value=_DEFAULT_CHORD_M,
                reason=f"chord not specified; defaulted to {_DEFAULT_CHORD_M} m unit chord.",
            )
        )
    if aoa is None:
        aoa = _DEFAULT_AOA_DEG
        assumptions.append(
            Assumption(
                field_path="flow.angle_of_attack_deg",
                value=_DEFAULT_AOA_DEG,
                reason="angle of attack not specified; defaulted to 0 degrees.",
            )
        )

    provenance["flow.altitude_m"] = "user_provided" if altitude is not None else "inferred"
    if velocity is not None:
        provenance["flow.velocity_m_s"] = "user_provided"
    if mach is not None:
        provenance["flow.mach"] = "user_provided"
        if altitude is None:
            altitude = 0.0
            assumptions.append(
                Assumption(
                    field_path="flow.altitude_m",
                    value=0.0,
                    reason="altitude required for Mach-only input; defaulted to sea level.",
                )
            )
    if reynolds is not None:
        provenance["flow.reynolds_target"] = "user_provided"

    airfoil = AirfoilSpec(family=family, designation=designation, chord_m=chord)
    flow = FlowCondition(
        altitude_m=altitude,
        velocity_m_s=velocity,
        mach=mach,
        angle_of_attack_deg=aoa,
        reynolds_target=reynolds,
    )
    intent = DesignIntent(
        airfoil=airfoil,
        flow=flow,
        assumptions=assumptions,
        provenance=ProvenanceMap(fields=provenance),
        notes=None,
    )
    return ParseResult(
        intent=intent,
        raw_input=text,
        model=OFFLINE_MODEL_NAME,
        attempts=1,
    )
