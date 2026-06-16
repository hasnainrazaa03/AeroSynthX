"""Generates a summary report for a completed optimization study."""

import html

from aerosynthx.optimizer.schemas import OptimizationResult


def render_optimization_report(result: OptimizationResult) -> str:
    """
    Generates a standalone HTML report for an optimization study.
    """
    best_run = result.best_run_result
    best_cl_cd = "N/A"
    if best_run and best_run.get("xfoil_results"):
        res = best_run["xfoil_results"][0]
        if res["cd"] > 0:
            best_cl_cd = f"{res['cl'] / res['cd']:.4f}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>AeroSynthX Optimization Report</title>
        <style>
            body {{ font-family: sans-serif; margin: 2em; }}
            h1, h2 {{ color: #333; }}
            .summary {{ border: 1px solid #ddd; padding: 1em; margin-bottom: 2em; }}
        </style>
    </head>
    <body>
        <h1>Optimization Report</h1>
        <div class="summary">
            <p><strong>Optimization ID:</strong> {result.optimization_id}</p>
            <p><strong>Underlying Study ID:</strong> {result.study_id}</p>
            <h2>Optimal Candidate</h2>
            <p><strong>Best Run ID:</strong> {result.best_run_id}</p>
            <p><strong>Best Cl/Cd Ratio:</strong> {best_cl_cd}</p>
            <p><strong>Intent:</strong> {html.escape(best_run.get("intent_text", ""))}</p>
        </div>
    </body>
    </html>
    """
    return html_content
