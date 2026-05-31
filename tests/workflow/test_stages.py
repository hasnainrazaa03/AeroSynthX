from __future__ import annotations

from aerosynthx.workflow.stages import STAGE_ORDER, StageName


def test_stage_values_are_lowercase() -> None:
    assert [s.value for s in StageName] == [
        "parse",
        "compute",
        "geometry",
        "case",
        "solve",
        "persist",
    ]


def test_stage_order_matches_enum() -> None:
    # SOLVE is an opt-in stage and is intentionally excluded from the
    # canonical ordering used for pending/backward-compatibility logic.
    assert STAGE_ORDER == (
        StageName.PARSE,
        StageName.COMPUTE,
        StageName.GEOMETRY,
        StageName.CASE,
        StageName.PERSIST,
    )
    assert len(STAGE_ORDER) == 5
    assert StageName.SOLVE not in STAGE_ORDER


def test_stage_name_is_string_compatible() -> None:
    assert StageName.PARSE.value == "parse"
    assert f"{StageName.CASE}" == "case"
