"""Self-contained HTML report rendering for a finished run.

This module turns a :class:`~aerosynthx.workflow.pipeline.RunResult` into a
single standalone HTML document with inline SVG charts. It pulls in **zero**
new runtime dependencies and emits no external asset references, so the
rendered string can be saved to disk, emailed, or served directly.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aerosynthx.workflow.pipeline import RunResult

_CHART_WIDTH = 520
_LABEL_WIDTH = 170
_BAR_HEIGHT = 22
_BAR_GAP = 8


@dataclass(frozen=True, slots=True)
class _Bar:
    """A single labelled value in a horizontal bar chart."""

    label: str
    value: float


def _esc(value: object) -> str:
    """HTML-escape ``value`` after stringifying it."""
    return html.escape(str(value))


def _fmt(value: float) -> str:
    """Format a float compactly, trimming trailing zeros."""
    return f"{value:.4g}"


def _bar_chart_svg(bars: list[_Bar], *, unit: str) -> str:
    """Render ``bars`` as an inline horizontal-bar SVG chart."""
    if not bars:
        return "<p class='empty'>No data to chart.</p>"
    max_value = max(bar.value for bar in bars)
    track_width = _CHART_WIDTH - _LABEL_WIDTH
    height = len(bars) * (_BAR_HEIGHT + _BAR_GAP)
    rows: list[str] = []
    for index, bar in enumerate(bars):
        y = index * (_BAR_HEIGHT + _BAR_GAP)
        fraction = bar.value / max_value if max_value > 0 else 0.0
        bar_width = fraction * track_width
        text_y = y + _BAR_HEIGHT * 0.7
        rows.append(
            f'<text x="0" y="{text_y:.1f}" class="bar-label">{_esc(bar.label)}</text>'
            f'<rect x="{_LABEL_WIDTH}" y="{y}" width="{bar_width:.1f}" '
            f'height="{_BAR_HEIGHT}" class="bar" rx="3" />'
            f'<text x="{_LABEL_WIDTH + bar_width + 6:.1f}" y="{text_y:.1f}" '
            f'class="bar-value">{_esc(_fmt(bar.value))} {_esc(unit)}</text>'
        )
    return (
        f'<svg viewBox="0 0 {_CHART_WIDTH} {height}" width="{_CHART_WIDTH}" '
        f'height="{height}" role="img" class="chart">{"".join(rows)}</svg>'
    )


def _kv_table(rows: list[tuple[str, str]]) -> str:
    """Render labelled key/value pairs as an HTML table."""
    body = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows
    )
    return f"<table class='kv'>{body}</table>"


def _intent_rows(result: RunResult) -> list[tuple[str, str]]:
    """Build the intent-summary key/value rows."""
    intent = result.intent
    if intent is None:
        return []
    airfoil = intent.airfoil
    flow = intent.flow
    rows = [
        ("Airfoil", f"{airfoil.family} {airfoil.designation}"),
        ("Chord", f"{_fmt(airfoil.chord_m)} m"),
        ("Angle of attack", f"{_fmt(flow.angle_of_attack_deg)} deg"),
    ]
    if flow.velocity_m_s is not None:
        rows.append(("Velocity", f"{_fmt(flow.velocity_m_s)} m/s"))
    if flow.mach is not None:
        rows.append(("Mach", _fmt(flow.mach)))
    if flow.altitude_m is not None:
        rows.append(("Altitude", f"{_fmt(flow.altitude_m)} m"))
    return rows


def _flow_rows(result: RunResult) -> list[tuple[str, str]]:
    """Build the derived flow-state key/value rows."""
    state = result.flow_state
    if state is None:
        return []
    return [
        ("Reynolds (chord)", _fmt(state.reynolds_chord)),
        ("Mach", _fmt(state.mach)),
        ("Velocity", f"{_fmt(state.velocity_m_s)} m/s"),
        ("Density", f"{_fmt(state.density_kg_m3)} kg/m^3"),
        ("Temperature", f"{_fmt(state.temperature_k)} K"),
        ("Pressure", f"{_fmt(state.pressure_pa)} Pa"),
        ("Turbulence intensity", _fmt(state.turbulence_intensity)),
    ]


def _physics_bars(result: RunResult) -> list[_Bar]:
    """Build bar-chart entries for derived aerodynamic quantities."""
    state = result.flow_state
    if state is None:
        return []
    return [
        _Bar(label="Re (millions)", value=state.reynolds_chord / 1_000_000.0),
        _Bar(label="Mach", value=state.mach),
        _Bar(label="Turbulence intensity", value=state.turbulence_intensity),
    ]


_COEFF_LABELS: dict[str, str] = {"cl": "Cl", "cd": "Cd", "cm": "Cm", "cs": "Cs"}


def _coefficient_bars(result: RunResult) -> list[_Bar]:
    """Build bar-chart entries for solver force coefficients."""
    solve = result.solve_result
    if solve is None or not solve.coefficients:
        return []
    return [
        _Bar(label=_COEFF_LABELS.get(key, key.upper()), value=value)
        for key, value in sorted(solve.coefficients.items())
    ]


def _solver_rows(result: RunResult) -> list[tuple[str, str]]:
    """Build solver-summary key/value rows when a solve ran."""
    solve = result.solve_result
    if solve is None or not solve.ran:
        return []
    rows = [
        ("Converged", "yes" if solve.converged else "no"),
        ("Iterations", str(solve.iterations)),
    ]
    if solve.final_residual is not None:
        rows.append(("Final residual", _fmt(solve.final_residual)))
    return rows


def render_run_report(result: RunResult) -> str:
    """Render a standalone HTML report for ``result``.

    The report always includes the run header and a stage-duration bar chart;
    the intent summary and derived flow-state table are included only when the
    corresponding data was persisted.
    """
    stage_bars = [_Bar(label=stage.name, value=float(stage.duration_ms)) for stage in result.stages]
    sections: list[str] = [
        f"<section><h2>Stage durations</h2>{_bar_chart_svg(stage_bars, unit='ms')}</section>"
    ]
    intent_rows = _intent_rows(result)
    if intent_rows:
        sections.append(f"<section><h2>Design intent</h2>{_kv_table(intent_rows)}</section>")
    else:
        sections.append(
            "<section><h2>Design intent</h2><p class='empty'>Intent unavailable.</p></section>"
        )
    flow_rows = _flow_rows(result)
    if flow_rows:
        sections.append(f"<section><h2>Flow conditions</h2>{_kv_table(flow_rows)}</section>")
    else:
        sections.append(
            "<section><h2>Flow conditions</h2>"
            "<p class='empty'>Flow state unavailable.</p></section>"
        )
    physics_bars = _physics_bars(result)
    if physics_bars:
        sections.append(
            f"<section><h2>Derived aerodynamics</h2>"
            f"{_bar_chart_svg(physics_bars, unit='')}</section>"
        )
    coeff_bars = _coefficient_bars(result)
    if coeff_bars:
        sections.append(
            f"<section><h2>Force coefficients</h2>{_bar_chart_svg(coeff_bars, unit='')}</section>"
        )
    elif result.solve_result is not None and result.solve_result.ran:
        solver_rows = _solver_rows(result)
        sections.append(f"<section><h2>Solver results</h2>{_kv_table(solver_rows)}</section>")
    else:
        sections.append(
            "<section><h2>Solver results</h2>"
            "<p class='empty'>Solver not run (use --execute / execute=true).</p></section>"
        )
    return _DOCUMENT_TEMPLATE.format(
        run_id=_esc(result.run_id),
        status=_esc(result.status),
        status_class=_esc(result.status),
        intent_text=_esc(result.intent_text),
        body="".join(sections),
    )


_DOCUMENT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>AeroSynthX run {run_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1b1f24; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .intent {{ color: #444; margin-top: 0; }}
  .status {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px;
            font-size: 0.85rem; font-weight: 600; }}
  .status-completed {{ background: #e3f6e8; color: #1a7f37; }}
  .status-failed {{ background: #fde7e9; color: #b42318; }}
  section {{ margin-top: 1.75rem; }}
  h2 {{ font-size: 1.05rem; border-bottom: 1px solid #e1e4e8; padding-bottom: 0.25rem; }}
  table.kv {{ border-collapse: collapse; }}
  table.kv th {{ text-align: left; padding: 0.2rem 1rem 0.2rem 0; color: #555; font-weight: 500; }}
  table.kv td {{ padding: 0.2rem 0; font-variant-numeric: tabular-nums; }}
  .chart .bar {{ fill: #2f6feb; }}
  .chart .bar-label {{ font-size: 12px; fill: #1b1f24; }}
  .chart .bar-value {{ font-size: 12px; fill: #555; }}
  .empty {{ color: #888; font-style: italic; }}
</style>
</head>
<body>
<h1>Run <code>{run_id}</code>
<span class="status status-{status_class}">{status}</span></h1>
<p class="intent">{intent_text}</p>
{body}
</body>
</html>
"""
