"""FastAPI application factory for AeroSynthX."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from aerosynthx import __version__
from aerosynthx.api.ratelimit import RateLimitMiddleware, RateLimitSettings
from aerosynthx.api.schemas import RunRequest, RunSummary, VersionInfo
from aerosynthx.api.security import ApiKeyStore, Scope, make_api_key_dependency
from aerosynthx.intent import LLMClient
from aerosynthx.observability import METRICS, bind_correlation_id, render_prometheus
from aerosynthx.workflow.db import RunRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.pipeline import Pipeline, load_run

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_HTTP_REQUESTS = METRICS.counter(
    "aerosynthx_http_requests_total",
    "Total HTTP requests, labelled by method, route, and status code.",
    label_names=("method", "route", "status"),
)
_HTTP_LATENCY = METRICS.histogram(
    "aerosynthx_http_request_duration_seconds",
    "HTTP request latency, labelled by method and route.",
    label_names=("method", "route"),
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Inject correlation IDs and record per-request metrics."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Wrap one request: bind a correlation id and record metrics."""
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        start = time.perf_counter()
        with bind_correlation_id(cid):
            response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Correlation-Id"] = cid
        _HTTP_REQUESTS.inc(
            method=request.method, route=route_path, status=str(response.status_code)
        )
        _HTTP_LATENCY.observe(elapsed, method=request.method, route=route_path)
        return response


def _safe_resolve(case_dir: Path, relative: str) -> Path:
    """Return ``case_dir / relative`` if it stays inside ``case_dir``.

    Raises :class:`HTTPException` 400 on any traversal attempt.
    """
    candidate = (case_dir / relative).resolve()
    base = case_dir.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path escapes case directory",
        ) from exc
    return candidate


def create_app(
    *,
    out_root: Path,
    llm_client: LLMClient | None = None,
    api_keys: Iterable[str] | None = None,
    rate_limit: int | None = None,
    rate_window_seconds: float | None = None,
    max_body_bytes: int | None = None,
) -> FastAPI:
    """Build a FastAPI app bound to ``out_root``.

    Args:
        out_root: Directory used by the underlying :class:`Pipeline`.
            Will be created on first use.
        llm_client: Optional LLM client enabling ``use_llm`` requests. When
            ``None``, ``use_llm=true`` requests transparently fall back to
            the deterministic offline parser.
        api_keys: Optional accepted API keys. When omitted, keys are read
            from ``AEROSYNTHX_API_KEYS``; an empty configuration leaves the
            data-plane endpoints open (backward compatible). Keys supplied
            here are granted all scopes.
        rate_limit: Max requests per window per principal. ``None`` reads
            ``AEROSYNTHX_RATE_LIMIT`` (``0``/unset disables throttling).
        rate_window_seconds: Token-bucket window. ``None`` reads
            ``AEROSYNTHX_RATE_WINDOW_SECONDS`` (default 60s).
        max_body_bytes: Reject larger request bodies with 413. ``None``
            reads ``AEROSYNTHX_MAX_BODY_BYTES`` (default 1 MiB; ``0``
            disables the check).
    """
    out_root.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline(out_root=out_root)
    llm_pipeline = (
        Pipeline(out_root=out_root, llm_client=llm_client) if llm_client is not None else pipeline
    )
    store = ApiKeyStore.from_keys(api_keys) if api_keys is not None else ApiKeyStore.from_env()
    auth_read = Depends(make_api_key_dependency(store, required_scope=Scope.READ))
    auth_run = Depends(make_api_key_dependency(store, required_scope=Scope.RUN))

    limits = RateLimitSettings.resolve(
        rate_limit=rate_limit,
        rate_window_seconds=rate_window_seconds,
        max_body_bytes=max_body_bytes,
    )

    app = FastAPI(
        title="AeroSynthX",
        version=__version__,
        description="HTTP API for the AeroSynthX workflow orchestrator.",
    )
    # Order matters: ObservabilityMiddleware is added last so it is the
    # outermost layer and still records correlation ids + metrics for
    # responses short-circuited by the rate/body guard.
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limits.build_limiter(),
        max_body_bytes=limits.max_body_bytes,
    )
    app.add_middleware(ObservabilityMiddleware)

    # -------- meta -----------------------------------------------------

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse, tags=["meta"])
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/api/v1/version", response_model=VersionInfo, tags=["meta"])
    def version() -> VersionInfo:
        return VersionInfo(name="aerosynthx", version=__version__)

    # -------- runs -----------------------------------------------------

    @app.post(
        "/api/v1/runs",
        tags=["runs"],
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth_run],
    )
    def create_run(body: RunRequest) -> dict[str, Any]:
        active = llm_pipeline if body.use_llm else pipeline
        try:
            result = active.run(body.intent_text, resume=body.resume, execute=body.execute)
        except StageError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"stage": exc.stage, "message": str(exc), "code": exc.code},
            ) from exc
        return result.to_json()

    @app.get(
        "/api/v1/runs",
        response_model=list[RunSummary],
        tags=["runs"],
        dependencies=[auth_read],
    )
    def list_runs(limit: int = 50) -> list[RunSummary]:
        limit = max(1, min(limit, 500))
        with open_session(pipeline.db_path) as session:
            stmt = select(RunRow).order_by(RunRow.created_at_iso.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [
                RunSummary(
                    run_id=r.id,
                    status=r.status,
                    intent_text=r.intent_text,
                    created_at_iso=r.created_at_iso,
                    completed_at_iso=r.completed_at_iso,
                )
                for r in rows
            ]

    @app.get("/api/v1/runs/{run_id}", tags=["runs"], dependencies=[auth_read])
    def get_run(run_id: str) -> dict[str, Any]:
        result = load_run(pipeline.db_path, run_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run with id {run_id!r}",
            )
        return result.to_json()

    @app.get("/api/v1/runs/{run_id}/files", tags=["runs"], dependencies=[auth_read])
    def list_run_files(run_id: str) -> dict[str, list[str]]:
        case_dir = _require_case_dir(pipeline, run_id)
        files = sorted(str(p.relative_to(case_dir)) for p in case_dir.rglob("*") if p.is_file())
        return {"files": files}

    @app.get(
        "/api/v1/runs/{run_id}/files/{file_path:path}",
        tags=["runs"],
        dependencies=[auth_read],
    )
    def get_run_file(run_id: str, file_path: str) -> FileResponse:
        case_dir = _require_case_dir(pipeline, run_id)
        target = _safe_resolve(case_dir, file_path)
        if not target.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no file {file_path!r} in run {run_id!r}",
            )
        return FileResponse(target, media_type="text/plain", filename=target.name)

    # -------- static UI ------------------------------------------------

    if _STATIC_DIR.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=str(_STATIC_DIR)),
            name="static",
        )

        @app.get("/", response_class=HTMLResponse, tags=["ui"])
        def index() -> HTMLResponse:
            html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
            return HTMLResponse(content=html)

    return app


def _require_case_dir(pipeline: Pipeline, run_id: str) -> Path:
    result = load_run(pipeline.db_path, run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no run with id {run_id!r}",
        )
    if result.case_dir is None or not result.case_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run {run_id!r} has no case directory",
        )
    return result.case_dir
