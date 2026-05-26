"""FastAPI application factory for AeroSynthX."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from aerosynthx import __version__
from aerosynthx.api.schemas import RunRequest, RunSummary, VersionInfo
from aerosynthx.workflow.db import RunRow, open_session
from aerosynthx.workflow.errors import StageError
from aerosynthx.workflow.pipeline import Pipeline, load_run

_STATIC_DIR = Path(__file__).resolve().parent / "static"


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


def create_app(*, out_root: Path) -> FastAPI:
    """Build a FastAPI app bound to ``out_root``.

    Args:
        out_root: Directory used by the underlying :class:`Pipeline`.
            Will be created on first use.
    """
    out_root.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline(out_root=out_root)

    app = FastAPI(
        title="AeroSynthX",
        version=__version__,
        description="HTTP API for the AeroSynthX workflow orchestrator.",
    )

    # -------- meta -----------------------------------------------------

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/version", response_model=VersionInfo, tags=["meta"])
    def version() -> VersionInfo:
        return VersionInfo(name="aerosynthx", version=__version__)

    # -------- runs -----------------------------------------------------

    @app.post(
        "/api/v1/runs",
        tags=["runs"],
        status_code=status.HTTP_201_CREATED,
    )
    def create_run(body: RunRequest) -> dict[str, Any]:
        try:
            result = pipeline.run(body.intent_text, resume=body.resume)
        except StageError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"stage": exc.stage, "message": str(exc), "code": exc.code},
            ) from exc
        return result.to_json()

    @app.get("/api/v1/runs", response_model=list[RunSummary], tags=["runs"])
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

    @app.get("/api/v1/runs/{run_id}", tags=["runs"])
    def get_run(run_id: str) -> dict[str, Any]:
        result = load_run(pipeline.db_path, run_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run with id {run_id!r}",
            )
        return result.to_json()

    @app.get("/api/v1/runs/{run_id}/files", tags=["runs"])
    def list_run_files(run_id: str) -> dict[str, list[str]]:
        case_dir = _require_case_dir(pipeline, run_id)
        files = sorted(str(p.relative_to(case_dir)) for p in case_dir.rglob("*") if p.is_file())
        return {"files": files}

    @app.get("/api/v1/runs/{run_id}/files/{file_path:path}", tags=["runs"])
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
