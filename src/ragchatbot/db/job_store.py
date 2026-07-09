"""Ingestion job tracking, backing the admin ingestion API. A long-running
ingestion run is kicked off asynchronously (FastAPI BackgroundTasks) and
polled for status instead of blocking the triggering HTTP request. Persisted
in the vector-store database so any process/worker can serve a status read,
even though only the worker that received the POST executes the run."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, insert, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

_metadata = MetaData()

ingestion_jobs_table = Table(
    "ingestion_jobs",
    _metadata,
    Column("job_id", String, primary_key=True),
    Column("status", String, nullable=False),  # pending | running | succeeded | failed
    Column("tables", JSONB, nullable=False),
    Column("stats", JSONB, nullable=True),
    Column("error", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
)


def ensure_job_schema(engine: Engine) -> None:
    _metadata.create_all(engine, tables=[ingestion_jobs_table], checkfirst=True)


def create_job(engine: Engine, tables: list[str]) -> str:
    job_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            insert(ingestion_jobs_table).values(
                job_id=job_id,
                status="pending",
                tables=tables,
                created_at=datetime.now(timezone.utc),
            )
        )
    return job_id


def mark_running(engine: Engine, job_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(ingestion_jobs_table)
            .where(ingestion_jobs_table.c.job_id == job_id)
            .values(status="running", started_at=datetime.now(timezone.utc))
        )


def mark_succeeded(engine: Engine, job_id: str, stats: dict[str, int]) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(ingestion_jobs_table)
            .where(ingestion_jobs_table.c.job_id == job_id)
            .values(status="succeeded", stats=stats, finished_at=datetime.now(timezone.utc))
        )


def mark_failed(engine: Engine, job_id: str, error: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(ingestion_jobs_table)
            .where(ingestion_jobs_table.c.job_id == job_id)
            .values(status="failed", error=error, finished_at=datetime.now(timezone.utc))
        )


def get_job(engine: Engine, job_id: str) -> dict[str, object] | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(ingestion_jobs_table).where(ingestion_jobs_table.c.job_id == job_id)
        ).mappings().first()
    return dict(row) if row else None
