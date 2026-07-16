"""FastAPI application entrypoint (FR-4.1, NFR-1.8). Wires config-selected
providers and database engines once at startup; exposes /health, /ready,
/chat, and /admin/* (vector store reset, ingestion trigger/status). No local
disk state — safe to run as a stateless microservice."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ragchatbot.api.routes.admin import router as admin_router
from ragchatbot.api.routes.chat import router as chat_router
from ragchatbot.config.settings import get_settings
from ragchatbot.db.source_adapter import build_engine
from ragchatbot.db.vector_store import build_vector_engine
from ragchatbot.providers.factory import build_chat_provider, build_embedding_provider
from ragchatbot.retrieval.reranker import build_reranker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app.state.settings = settings
    # SQLAlchemy engines are lazy — no connection is opened until first use,
    # so app startup does not require live source/vector databases.
    app.state.source_engine = build_engine(
        settings.source_db(), settings.source_db_connect_timeout_seconds
    )
    app.state.vector_engine = build_vector_engine(settings.vector_db())
    app.state.embedding_provider = build_embedding_provider(settings)
    app.state.chat_provider = build_chat_provider(settings)
    app.state.reranker = build_reranker(settings.rerank_enabled, settings.rerank_model)
    app.state.vector_table = None  # ensured lazily on first /chat request
    app.state.session_schema_ready = False  # ensured lazily on first /chat request

    if not settings.admin_api_key:
        logger.warning(
            "ADMIN_API_KEY is not set — /admin/* endpoints (vector store reset, "
            "ingestion trigger) are unauthenticated. Set ADMIN_API_KEY before "
            "exposing this service outside your own machine."
        )

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Chatbot Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    app.include_router(chat_router)
    app.include_router(admin_router)
    return app


app = create_app()
