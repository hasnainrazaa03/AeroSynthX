"""HTTP API and minimal web UI for AeroSynthX.

See :mod:`aerosynthx.api.app` for the FastAPI factory and
:mod:`aerosynthx.api.schemas` for the request / response DTOs.
"""

from __future__ import annotations

from aerosynthx.api.app import create_app
from aerosynthx.api.schemas import RunRequest, RunSummary, VersionInfo
from aerosynthx.api.security import ApiKeyStore, Scope

__all__ = ["ApiKeyStore", "RunRequest", "RunSummary", "Scope", "VersionInfo", "create_app"]
