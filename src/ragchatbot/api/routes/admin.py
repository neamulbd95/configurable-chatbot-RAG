"""Administrative endpoints for vector store lifecycle management: reset
ingested data and trigger/poll ingestion runs over HTTP, replacing manual
`python -m ragchatbot.ingestion.pipeline` shell access for operational use.
Gated by require_admin_key (see api/dependencies.py)."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from ragchatbot.api.dependencies import require_admin_key
from ragchatbot.config.tables import TableConfig, load_table_configs
from ragchatbot.db.job_store import (
    create_job,
    ensure_job_schema,
    get_job,
    mark_failed,
    mark_running,
    mark_succeeded,
)
from ragchatbot.db.vector_store import delete_chunks, reflect_existing_chunks_table
from ragchatbot.db.watermark_store import delete_watermarks, ensure_watermark_schema
from ragchatbot.ingestion.pipeline import run_ingestion_for_tables

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


class ResetRequest(BaseModel):
    tables: list[str] | None = None
    confirm: bool = False


class ResetResponse(BaseModel):
    deleted_chunks: int
    reset_tables: list[str] | None


class IngestRequest(BaseModel):
    tables: list[str] | None = None


class IngestStartResponse(BaseModel):
    job_id: str
    status: str


class IngestJobResponse(BaseModel):
    job_id: str
    status: str
    tables: list[str]
    stats: dict[str, int] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SourceDBStatusResponse(BaseModel):
    connected: bool
    engine: str
    host: str
    port: int
    database: str
    source_schema: str | None = None
    error: str | None = None


@router.get("/source-db/status", response_model=SourceDBStatusResponse)
async def source_db_status(request: Request) -> SourceDBStatusResponse:
    """Actual connectivity check (SELECT 1), not just app liveness — /health
    and /ready say the API process is up, not that the source RDBMS is
    reachable. Useful before triggering ingestion, and after moving the
    service to a machine where the source DB's host/schema differs."""
    settings = request.app.state.settings
    try:
        with request.app.state.source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        connected, error = True, None
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure, not just specific ones
        connected, error = False, str(exc)

    return SourceDBStatusResponse(
        connected=connected,
        engine=settings.source_db_engine,
        host=settings.source_db_host,
        port=settings.source_db_port,
        database=settings.source_db_name,
        source_schema=settings.source_db_schema,
        error=error,
    )


@router.post("/vector-store/reset", response_model=ResetResponse)
async def reset_vector_store(payload: ResetRequest, request: Request) -> ResetResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=400, detail="This deletes ingested data. Set confirm=true to proceed."
        )

    settings = request.app.state.settings
    vector_table = reflect_existing_chunks_table(request.app.state.vector_engine, settings.vector_table_name)
    if vector_table is None:
        return ResetResponse(deleted_chunks=0, reset_tables=payload.tables)

    deleted = delete_chunks(request.app.state.vector_engine, vector_table, payload.tables)
    delete_watermarks(request.app.state.vector_engine, payload.tables)
    logger.warning(
        "Vector store reset via admin API: tables=%s deleted_chunks=%s",
        payload.tables or "ALL",
        deleted,
    )
    return ResetResponse(deleted_chunks=deleted, reset_tables=payload.tables)


async def _run_ingestion_job(app: FastAPI, job_id: str, table_configs: list[TableConfig]) -> None:
    engine = app.state.vector_engine
    try:
        mark_running(engine, job_id)
        stats = await run_ingestion_for_tables(
            app.state.source_engine,
            app.state.vector_engine,
            app.state.embedding_provider,
            table_configs,
            app.state.settings.vector_table_name,
            app.state.settings.chunk_size,
            app.state.settings.chunk_overlap,
        )
        mark_succeeded(engine, job_id, stats)
    except Exception as exc:  # noqa: BLE001 - failures must be recorded on the job, not raised into the background task runner
        logger.exception("Ingestion job %s failed", job_id)
        mark_failed(engine, job_id, str(exc))


@router.post("/ingest", response_model=IngestStartResponse)
async def start_ingestion(
    payload: IngestRequest, request: Request, background_tasks: BackgroundTasks
) -> IngestStartResponse:
    app = request.app
    table_configs = load_table_configs(
        app.state.settings.tables_config_path, app.state.settings.source_db_schema
    )

    if payload.tables:
        requested = set(payload.tables)
        known = {t.qualified_name for t in table_configs}
        missing = requested - known
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown table(s): {sorted(missing)}")
        table_configs = [t for t in table_configs if t.qualified_name in requested]

    engine = app.state.vector_engine
    ensure_job_schema(engine)
    ensure_watermark_schema(engine)
    job_id = create_job(engine, [t.qualified_name for t in table_configs])

    background_tasks.add_task(_run_ingestion_job, app, job_id, table_configs)
    return IngestStartResponse(job_id=job_id, status="pending")


@router.get("/ingest/{job_id}", response_model=IngestJobResponse)
async def get_ingestion_job(job_id: str, request: Request) -> IngestJobResponse:
    job = get_job(request.app.state.vector_engine, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestJobResponse(**job)
