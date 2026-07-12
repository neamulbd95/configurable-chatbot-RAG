"""Chat orchestration (FR-4.2-4.4, FR-6.11): retrieval is always invoked
before generation by the caller; if it returns no grounded context, this
service returns a fixed non-answer instead of falling back to an ungrounded
LLM call. Prior turns from the session (FR-6.11) are threaded into the
message list ahead of the grounded question."""

from __future__ import annotations

import uuid

from ragchatbot.chat.schemas import ChatRequest, ChatResponse, Citation
from ragchatbot.providers.base import ChatMessage, ChatProvider, ChatProviderError
from ragchatbot.retrieval.pipeline import ContextPackage

__all__ = ["ChatProviderError", "ChatService"]

SYSTEM_PROMPT = (
    "You are a grounded assistant. Answer ONLY using the provided context. "
    "If the context does not contain the answer, say you don't have enough "
    "information rather than guessing. Do not invent facts."
)

UNGROUNDED_ANSWER = "I don't have enough information in the connected data to answer that."


class ChatService:
    def __init__(self, chat_provider: ChatProvider):
        self._chat_provider = chat_provider

    async def answer(
        self,
        request: ChatRequest,
        context: ContextPackage,
        history: list[dict[str, str]] | None = None,
    ) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())

        if not context.is_grounded:
            return ChatResponse(
                answer=UNGROUNDED_ANSWER,
                session_id=session_id,
                citations=[],
                grounded=False,
                confidence=0.0,
            )

        user_prompt = f"Context:\n{context.as_context_text()}\n\nQuestion: {request.message}"
        messages: list[ChatMessage] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history or []:
            messages.append({"role": turn["role"], "content": turn["content"]})  # type: ignore[typeddict-item]
        messages.append({"role": "user", "content": user_prompt})

        try:
            answer = await self._chat_provider.generate(messages)
        except Exception as exc:
            raise ChatProviderError(f"Chat provider call failed: {exc}") from exc

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            citations=[Citation(**c) for c in context.citations()],
            grounded=True,
            confidence=context.confidence,
        )
