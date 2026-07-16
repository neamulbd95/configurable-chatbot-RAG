"""POST /chat — the documented chat endpoint contract (FR-4.1, FR-4.2),
wired for hybrid retrieval, reranking, RBAC, and multi-turn session context
(FR-6.6-6.13). Small talk (greetings, pleasantries) skips retrieval
entirely — see chat/small_talk.py."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ragchatbot.api.dependencies import get_session_engine, get_vector_table
from ragchatbot.chat.schemas import ChatRequest, ChatResponse
from ragchatbot.chat.service import ChatProviderError, ChatService
from ragchatbot.chat.small_talk import is_small_talk
from ragchatbot.db.session_store import append_message, get_or_create_session, get_recent_messages
from ragchatbot.providers.base import EmbeddingProviderError
from ragchatbot.retrieval.pipeline import retrieve

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    settings = request.app.state.settings
    session_engine = get_session_engine(request)
    session_id = get_or_create_session(session_engine, payload.session_id)
    history = get_recent_messages(
        session_engine,
        session_id,
        max_messages=settings.history_max_messages,
        max_chars=settings.history_max_chars,
    )
    service = ChatService(request.app.state.chat_provider)

    try:
        if is_small_talk(payload.message):
            # No retrieval at all — a greeting has no data to ground
            # against, and shouldn't cost an embedding call or require the
            # vector store to be reachable.
            response = await service.answer_small_talk(payload, history=history)
        else:
            vector_table = await get_vector_table(request)
            context = await retrieve(
                query=payload.message,
                embedding_provider=request.app.state.embedding_provider,
                vector_engine=request.app.state.vector_engine,
                vector_table=vector_table,
                top_k=settings.retrieval_top_k,
                similarity_threshold=settings.retrieval_similarity_threshold,
                keyword_weight=settings.retrieval_keyword_weight,
                caller_roles=payload.roles,
                reranker=request.app.state.reranker,
            )
            response = await service.answer(payload, context, history=history)
    except (EmbeddingProviderError, ChatProviderError) as exc:
        # Provider-side failure (network, auth, firewall/VNet rejection,
        # rate limit) — a 502 with the real cause, not a bare 500.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response.session_id = session_id

    append_message(session_engine, session_id, "user", payload.message)
    append_message(
        session_engine,
        session_id,
        "assistant",
        response.answer,
        citations=[c.model_dump() for c in response.citations],
    )

    return response
