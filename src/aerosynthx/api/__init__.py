"""HTTP API and minimal web UI for AeroSynthX.

See :mod:`aerosynthx.api.app` for the FastAPI factory and
:mod:`aerosynthx.api.schemas` for the request / response DTOs.
"""

from __future__ import annotations

from aerosynthx.api.app import create_app
from aerosynthx.api.schemas import RunRequest, RunSummary, VersionInfo

__all__ = ["RunRequest", "RunSummary", "VersionInfo", "create_app"]
