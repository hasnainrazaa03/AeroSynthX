from __future__ import annotations

from aerosynthx.workflow.stages import STAGE_ORDER_2D, STAGE_ORDER_3D, StageName


def test_stage_values_are_lowercase() -> None:
    for s in StageName:
        assert s.value.islower()


def test_stage_order_matches_enum() -> None:
    # SOLVE is an opt-in stage and is intentionally excluded from the
    # canonical ordering used for pending/backward-compatibility logic.
    assert STAGE_ORDER_2D == (
        StageName.PARSE,
        StageName.COMPUTE,
        StageName.GEOMETRY,
        StageName.CASE,
        StageName.PERSIST,
    )
    assert len(STAGE_ORDER_2D) == 5
    assert StageName.SOLVE not in STAGE_ORDER_2D

    assert STAGE_ORDER_3D == (
        StageName.PARSE,
        StageName.COMPUTE,
        StageName.WING_GEOMETRY,
        StageName.MESH,
        StageName.PERSIST,
    )
    assert len(STAGE_ORDER_3D) == 5
    assert StageName.SOLVE not in STAGE_ORDER_3D


def test_stage_name_is_string_compatible() -> None:
    assert StageName.PARSE.value == "parse"
    assert f"{StageName.CASE}" == "case"
