"""Phase 7 performance budget.

The offline parse -> case path must complete in well under a couple of
seconds on a typical CI runner. We assert a generous budget so the test
catches major regressions without flapping on slow machines.
"""

from __future__ import annotations

import time
from pathlib import Path

from aerosynthx.workflow.pipeline import Pipeline

_BUDGET_SECONDS = 2.0
_INTENT = "NACA 2412 at 50 m/s, alpha 3 deg, chord 1.0 m."


def test_pipeline_completes_within_budget(tmp_path: Path) -> None:
    pipe = Pipeline(out_root=tmp_path)
    start = time.perf_counter()
    result = pipe.run(_INTENT, resume=False)
    elapsed = time.perf_counter() - start
    assert result.status == "completed"
    assert elapsed < _BUDGET_SECONDS, f"pipeline took {elapsed:.2f}s (budget {_BUDGET_SECONDS}s)"
