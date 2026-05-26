from __future__ import annotations

from aerosynthx.workflow.stages import STAGE_ORDER, StageName


def test_stage_values_are_lowercase() -> None:
    assert [s.value for s in StageName] == [
        "parse",
        "compute",
        "geometry",
        "case",
        "persist",
    ]


def test_stage_order_matches_enum() -> None:
    assert tuple(StageName) == STAGE_ORDER
    assert len(STAGE_ORDER) == 5


def test_stage_name_is_string_compatible() -> None:
    assert StageName.PARSE.value == "parse"
    assert f"{StageName.CASE}" == "case"
