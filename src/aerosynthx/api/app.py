"""FastAPI application factory for AeroSynthX."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from aerosynthx import __version__
from aerosynthx.api.ratelimit import RateLimitMiddleware, RateLimitSettings
from aerosynthx.api.schemas import PruneRequest, RunRequest, RunSummary, VersionInfo
from aerosynthx.api.security import ApiKeyStore, Scope, make_api_key_dependency
from aerosynthx.api.sse import run_event_stream
from aerosynthx.intent import LLMClient
from aerosynthx.observability import METRICS, bind_correlation_id, render_prometheus
from aerosynthx.optimizer import OptimizationRunner, OptimizationSpec
from aerosynthx.optimizer.report import render_optimization_report
from aerosynthx.study import StudyRunner, StudySpec
from aerosynthx.study.report import render_study_report
from aerosynthx.workflow.db import OptimizationRow, StudyRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.pipeline import Pipeline, load_run, query_runs
from aerosynthx.workflow.report import render_run_report

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
    study_runner = StudyRunner(pipeline)
    opt_runner = OptimizationRunner(study_runner)
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

    # -------- optimizations --------------------------------------------

    @app.post(
        "/api/v1/optimizations",
        tags=["optimizations"],
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth_run],
    )
    def create_optimization(body: OptimizationSpec) -> dict[str, Any]:
        result = opt_runner.run(body)
        return result.model_dump()

    @app.get("/api/v1/optimizations/{opt_id}", tags=["optimizations"], dependencies=[auth_read])
    def get_optimization(opt_id: str) -> dict[str, Any]:
        with open_session(pipeline.db_path) as session:
            opt_row = session.get(OptimizationRow, opt_id)
            if not opt_row:
                raise HTTPException(status_code=404, detail="Optimization not found")
            return opt_row.result_json

    # -------- studies --------------------------------------------------

    @app.post(
        "/api/v1/studies",
        tags=["studies"],
        status_code=status.HTTP_201_CREATED,
        dependencies=[auth_run],
    )
    def create_study(body: StudySpec) -> dict[str, Any]:
        result = study_runner.run(body)
        return result.model_dump()

    @app.get("/api/v1/studies/{study_id}", tags=["studies"], dependencies=[auth_read])
    def get_study(study_id: str) -> dict[str, Any]:
        with open_session(pipeline.db_path) as session:
            study_row = session.get(StudyRow, study_id)
            if not study_row:
                raise HTTPException(status_code=404, detail="Study not found")

            runs = [load_run(pipeline.db_path, run.id) for run in study_row.runs]
            spec = StudySpec.model_validate_json(study_row.spec_json)

            result = StudyResult(
                study_id=study_row.id,
                study_name=study_row.name,
                spec=spec,
                status=study_row.status,
                runs=[r for r in runs if r is not None],
            )
            return result.model_dump()

    @app.get(
        "/api/v1/studies/{study_id}/report",
        tags=["studies"],
        dependencies=[auth_read],
        response_class=HTMLResponse,
    )
    def get_study_report(study_id: str) -> HTMLResponse:
        with open_session(pipeline.db_path) as session:
            study_row = session.get(StudyRow, study_id)
            if not study_row:
                raise HTTPException(status_code=404, detail="Study not found")

            runs = [load_run(pipeline.db_path, run.id) for run in study_row.runs]
            spec = StudySpec.model_validate_json(study_row.spec_json)

            result = StudyResult(
                study_id=study_row.id,
                study_name=study_row.name,
                spec=spec,
                status=study_row.status,
                runs=[r for r in runs if r is not None],
            )
            return HTMLResponse(content=render_study_report(result))

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
            result = active.run(
                body.intent_text,
                resume=body.resume,
                execute=body.execute,
                timeout=body.timeout_seconds,
                analysis_mode=body.analysis_mode,
            )
        except StageError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"stage": exc.stage, "message": str(exc), "code": exc.code},
            ) from exc
        return result.to_json()

    @app.delete(
        "/api/v1/runs/{run_id}",
        tags=["runs"],
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[auth_run],
    )
    def delete_run(run_id: str) -> Response:
        if not pipeline.delete_run(run_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run with id {run_id!r}",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/runs",
        response_model=list[RunSummary],
        tags=["runs"],
        dependencies=[auth_read],
    )
    def list_runs(
        response: Response,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = Query(default=None, alias="status"),
        q: str | None = None,
    ) -> list[RunSummary]:
        page = query_runs(
            pipeline.db_path,
            limit=limit,
            offset=offset,
            status=status_filter,
            q=q,
        )
        response.headers["X-Total-Count"] = str(page.total)
        response.headers["X-Limit"] = str(page.limit)
        response.headers["X-Offset"] = str(page.offset)
        return [
            RunSummary(
                run_id=item.run_id,
                status=item.status,
                intent_text=item.intent_text,
                created_at_iso=item.created_at_iso,
                completed_at_iso=item.completed_at_iso,
            )
            for item in page.items
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

    @app.get(
        "/api/v1/runs/{run_id}/report",
        tags=["runs"],
        dependencies=[auth_read],
        response_class=HTMLResponse,
    )
    def get_run_report(run_id: str) -> HTMLResponse:
        result = load_run(pipeline.db_path, run_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run with id {run_id!r}",
            )
        return HTMLResponse(content=render_run_report(result))

    @app.get("/api/v1/runs/{run_id}/events", tags=["runs"], dependencies=[auth_read])
    def stream_run_events(run_id: str) -> StreamingResponse:
        result = load_run(pipeline.db_path, run_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run with id {run_id!r}",
            )
        return StreamingResponse(
            run_event_stream(result),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/store/stats", tags=["store"], dependencies=[auth_read])
    def store_stats() -> dict[str, int]:
        stats = pipeline.artifact_store.stats()
        return {"blobs": stats.blobs, "bytes": stats.bytes}

    @app.post("/api/v1/maintenance/prune", tags=["store"], dependencies=[auth_run])
    def prune_runs(body: PruneRequest) -> dict[str, int]:
        result = pipeline.prune_runs(max_age_days=body.max_age_days, max_count=body.max_count)
        collected = 0
        freed = 0
        if body.gc:
            gc = pipeline.collect_garbage()
            collected = gc.collected
            freed = gc.freed_bytes
        return {
            "pruned": result.count,
            "kept": result.kept,
            "collected": collected,
            "freed_bytes": freed,
        }

    @app.post("/api/v1/maintenance/relink", tags=["store"], dependencies=[auth_run])
    def relink_runs() -> dict[str, int]:
        result = pipeline.relink_runs()
        return {
            "linked": result.linked,
            "bytes_reclaimed": result.bytes_reclaimed,
            "skipped": result.skipped,
        }

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
