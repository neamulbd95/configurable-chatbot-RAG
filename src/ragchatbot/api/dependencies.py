"""Shared FastAPI dependencies: lazy vector-table/session-schema
initialization (so app startup never requires a live database connection)
and admin-endpoint authentication."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from ragchatbot.db.session_store import ensure_session_schema
from ragchatbot.db.vector_store import ensure_schema


async def get_vector_table(request: Request):
    app = request.app
    if app.state.vector_table is None:
        # Embedding dimension is only known once the provider has run at
        # least once; this also lazily creates the pgvector extension/table.
        await app.state.embedding_provider.embed(["dimension probe"])
        app.state.vector_table = ensure_schema(
            app.state.vector_engine,
            app.state.settings.vector_table_name,
            app.state.embedding_provider.dimension,
        )
    return app.state.vector_table


def get_session_engine(request: Request):
    app = request.app
    if not app.state.session_schema_ready:
        ensure_session_schema(app.state.vector_engine)
        app.state.session_schema_ready = True
    return app.state.vector_engine


async def require_admin_key(
    request: Request, x_admin_api_key: str | None = Header(default=None)
) -> None:
    """Gates /admin/* endpoints. If ADMIN_API_KEY isn't configured, admin
    endpoints are unauthenticated — acceptable for local dev, not for
    anything reachable outside your own machine (a startup warning is
    logged in that case; see api/main.py)."""
    configured_key = request.app.state.settings.admin_api_key
    if not configured_key:
        return
    if x_admin_api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin API key"
        )
