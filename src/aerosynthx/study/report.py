"""Generates a comparative HTML report for a completed study."""

from __future__ import annotations

import html

from aerosynthx.study.schemas import StudyResult


def render_study_report(result: StudyResult) -> str:
    """
    Generates a standalone HTML report for a study.
    """
    # Basic HTML structure
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AeroSynthX Study Report: {html.escape(result.study_name)}</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            h1, h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 2em; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Study Report: {html.escape(result.study_name)}</h1>
        <p><strong>Study ID:</strong> {result.study_id}</p>
        <p><strong>Status:</strong> {result.status}</p>

        <h2>Summary of Runs</h2>
        <table>
            <tr>
                <th>Run ID</th>
                <th>Intent</th>
                <th>Status</th>
                <th>Result Highlights</th>
            </tr>
    """

    for run in result.runs:
        highlights = ""
        if run.xfoil_results:
            # Show Cl for the first and last point of the polar
            first = run.xfoil_results[0]
            last = run.xfoil_results[-1]
            highlights = f"Polar with {len(run.xfoil_results)} points. Cl: {first.cl:.4f} -> {last.cl:.4f}"

        html_content += f"""
            <tr>
                <td>{run.run_id}</td>
                <td>{html.escape(run.intent_text)}</td>
                <td>{run.status}</td>
                <td>{highlights}</td>
            </tr>
        """

    html_content += """
        </table>
    </body>
    </html>
    """
    return html_content
