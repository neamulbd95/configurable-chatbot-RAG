"""Chat session and message persistence (FR-6.11-6.13), matching PDR §5.4-5.5.
Stored in the vector-store database — our own infra, never the source
RDBMS — same rationale as db/watermark_store.py."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, func, insert, select
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.engine import Engine

_metadata = MetaData()

chat_sessions_table = Table(
    "chat_sessions",
    _metadata,
    Column("session_id", String, primary_key=True),
    Column("user_id", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("last_active_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

chat_messages_table = Table(
    "chat_messages",
    _metadata,
    Column("message_id", String, primary_key=True),
    Column("session_id", String, nullable=False, index=True),
    Column("role", String, nullable=False),
    Column("content", String, nullable=False),
    Column("citations", JSONB, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("seq", Integer, nullable=False),
)


def ensure_session_schema(engine: Engine) -> None:
    _metadata.create_all(engine, tables=[chat_sessions_table, chat_messages_table], checkfirst=True)


def get_or_create_session(engine: Engine, session_id: str | None, user_id: str | None = None) -> str:
    resolved_id = session_id or str(uuid.uuid4())
    stmt = pg_insert(chat_sessions_table).values(session_id=resolved_id, user_id=user_id)
    stmt = stmt.on_conflict_do_update(
        index_elements=[chat_sessions_table.c.session_id],
        set_={"last_active_at": datetime.now(timezone.utc)},
    )
    with engine.begin() as conn:
        conn.execute(stmt)
    return resolved_id


def append_message(
    engine: Engine,
    session_id: str,
    role: str,
    content: str,
    citations: list[dict[str, object]] | None = None,
) -> None:
    with engine.begin() as conn:
        next_seq = conn.execute(
            select(func.coalesce(func.max(chat_messages_table.c.seq), -1) + 1).where(
                chat_messages_table.c.session_id == session_id
            )
        ).scalar_one()
        conn.execute(
            insert(chat_messages_table).values(
                message_id=str(uuid.uuid4()),
                session_id=session_id,
                role=role,
                content=content,
                citations=citations or [],
                seq=next_seq,
            )
        )


def apply_history_budget(
    most_recent_first: list[dict[str, str]], max_chars: int
) -> list[dict[str, str]]:
    """Pure truncation logic (FR-6.13), split out from the DB query for
    testability: given messages ordered most-recent-first, keep as many as
    fit `max_chars` (always keeping at least the single most recent one),
    then return them in chronological order."""
    selected: list[dict[str, str]] = []
    total_chars = 0
    for row in most_recent_first:
        content = row["content"]
        if total_chars + len(content) > max_chars and selected:
            break
        selected.append({"role": row["role"], "content": content})
        total_chars += len(content)

    selected.reverse()  # chronological order for prompt construction
    return selected


def get_recent_messages(
    engine: Engine,
    session_id: str,
    max_messages: int,
    max_chars: int,
) -> list[dict[str, str]]:
    """Sliding-window truncation (FR-6.13): most recent messages first,
    trimmed by count and then by a total character budget so long sessions
    can't blow out the target model's context window."""
    stmt = (
        select(chat_messages_table.c.role, chat_messages_table.c.content)
        .where(chat_messages_table.c.session_id == session_id)
        .order_by(chat_messages_table.c.seq.desc())
        .limit(max_messages)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()  # most-recent-first

    return apply_history_budget([dict(row) for row in rows], max_chars)
