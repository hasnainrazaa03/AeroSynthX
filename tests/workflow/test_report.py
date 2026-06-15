from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aerosynthx.openfoam.runner import SolveResult
from aerosynthx.workflow.pipeline import Pipeline, RunResult, StageResult
from aerosynthx.workflow.report import render_run_report

_GOOD = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


def _run(tmp_path: Path) -> RunResult:
    return Pipeline(out_root=tmp_path).run(_GOOD)


def test_report_is_standalone_html_with_chart(tmp_path: Path) -> None:
    result = _run(tmp_path)

    html = render_run_report(result)

    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html.rstrip().splitlines()[-1] or html.rstrip().endswith("</html>")
    # No external assets are referenced.
    assert "http://" not in html
    assert "https://" not in html
    # Header, intent, derived flow conditions, and a stage chart are present.
    assert result.run_id in html
    assert "Stage durations" in html
    assert "<svg" in html
    assert "Design intent" in html
    assert "Flow conditions" in html
    assert "Reynolds (chord)" in html
    assert "NACA 2412" in html
    assert "Derived aerodynamics" in html
    assert "Solver not run" in html


def test_report_includes_coefficient_chart(tmp_path: Path) -> None:
    result = _run(tmp_path)
    solved = replace(
        result,
        solve_result=SolveResult(
            ran=True,
            converged=True,
            iterations=42,
            final_residual=1e-5,
            coefficients={"cl": 0.78, "cd": 0.012, "cm": -0.04},
            commands=("blockMesh", "simpleFoam"),
        ),
    )

    html = render_run_report(solved)

    assert "Force coefficients" in html
    assert "Cl" in html
    assert "Cd" in html
    assert html.count("<rect") >= 4  # stages + physics + coefficients


def test_report_solver_summary_without_coefficients(tmp_path: Path) -> None:
    result = _run(tmp_path)
    solved = replace(
        result,
        solve_result=SolveResult(
            ran=True,
            converged=False,
            iterations=100,
            final_residual=0.01,
            coefficients={},
            commands=("blockMesh", "simpleFoam"),
        ),
    )

    html = render_run_report(solved)

    assert "Solver results" in html
    assert "Converged" in html
    assert "no" in html
    assert "Force coefficients" not in html


def test_report_solver_summary_without_final_residual(tmp_path: Path) -> None:
    result = _run(tmp_path)
    solved = replace(
        result,
        solve_result=SolveResult(
            ran=True,
            converged=True,
            iterations=1,
            final_residual=None,
            coefficients={},
            commands=("blockMesh", "simpleFoam"),
        ),
    )

    html = render_run_report(solved)

    assert "Solver results" in html
    assert "Final residual" not in html


def test_report_escapes_intent_text(tmp_path: Path) -> None:
    result = _run(tmp_path)
    tampered = replace(result, intent_text="<script>alert(1)</script>")

    html = render_run_report(tampered)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_report_handles_missing_intent_and_flow_state(tmp_path: Path) -> None:
    result = _run(tmp_path)
    minimal = replace(result, intent=None, flow_state=None)

    html = render_run_report(minimal)

    assert "Intent unavailable." in html
    assert "Flow state unavailable." in html
    # The stage chart still renders.
    assert "<svg" in html


def test_report_handles_no_stages_and_zero_durations(tmp_path: Path) -> None:
    result = _run(tmp_path)

    empty = replace(result, stages=())
    assert "No data to chart." in render_run_report(empty)

    zeroed = replace(
        result,
        stages=tuple(replace(stage, duration_ms=0) for stage in result.stages),
    )
    html = render_run_report(zeroed)
    # All-zero durations render a chart with zero-width bars (no crash).
    assert "<svg" in html
    assert 'width="0.0"' in html


def test_report_omits_optional_intent_fields(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.intent is not None
    # A mach-only flow condition exercises the velocity/altitude branches.
    flow = result.intent.flow.model_copy(
        update={"velocity_m_s": None, "mach": 0.1, "altitude_m": 1000.0}
    )
    intent = result.intent.model_copy(update={"flow": flow})
    html = render_run_report(replace(result, intent=intent))

    assert "Mach" in html
    assert "Altitude" in html


def test_stage_chart_renders_one_bar_per_stage(tmp_path: Path) -> None:
    result = _run(tmp_path)
    one_stage = replace(
        result,
        flow_state=None,
        intent=None,
        stages=(
            StageResult(
                name="solo",
                status="ok",
                duration_ms=5,
                output_digest=None,
                error=None,
            ),
        ),
    )
    html = render_run_report(one_stage)

    assert html.count("<rect") == 1
    assert "solo" in html
