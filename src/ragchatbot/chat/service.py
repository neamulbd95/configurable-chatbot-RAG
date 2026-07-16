"""Chat orchestration (FR-4.2-4.4, FR-6.11): retrieval is always invoked
before generation by the caller for anything that isn't small talk; if it
returns no grounded context, this service returns a fixed non-answer
instead of falling back to an ungrounded LLM call. Prior turns from the
session (FR-6.11) are threaded into the message list ahead of the
question. Small talk (see chat/small_talk.py) bypasses grounding entirely —
that gate exists to stop the service inventing answers about *data*, not
to make it refuse "good morning"."""

from __future__ import annotations

import uuid

from ragchatbot.chat.schemas import ChatRequest, ChatResponse, Citation
from ragchatbot.providers.base import ChatMessage, ChatProvider, ChatProviderError
from ragchatbot.retrieval.pipeline import ContextPackage

__all__ = ["ChatProviderError", "ChatService"]

SYSTEM_PROMPT = (
    "You are a grounded assistant. Using ONLY the facts in the provided "
    "context, write a clear, natural-language answer to the user's "
    "question in your own words — do not copy, quote, or repeat the "
    "context's raw field labels or structure (e.g. do not output lines "
    "like 'Title: ...' or 'Description: ...' verbatim). Synthesize a "
    "normal conversational sentence or short paragraph instead. If the "
    "context does not contain the answer, say you don't have enough "
    "information rather than guessing. Do not invent facts not present "
    "in the context."
)

SMALL_TALK_SYSTEM_PROMPT = (
    "You are the conversational front-end of a data chatbot service. "
    "Respond briefly and naturally to greetings, pleasantries, and small "
    "talk. If asked what you can do, explain that you can answer "
    "questions about the data connected to this service. Keep replies "
    "short — a sentence or two."
)

UNGROUNDED_ANSWER = "I don't have enough information in the connected data to answer that."


class ChatService:
    def __init__(self, chat_provider: ChatProvider):
        self._chat_provider = chat_provider

    async def answer_small_talk(
        self,
        request: ChatRequest,
        history: list[dict[str, str]] | None = None,
    ) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        messages = self._build_messages(SMALL_TALK_SYSTEM_PROMPT, request.message, history)
        answer = await self._generate(messages)

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            citations=[],
            grounded=False,
            confidence=0.0,
        )

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
        messages = self._build_messages(SYSTEM_PROMPT, user_prompt, history)
        answer = await self._generate(messages)

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            citations=[Citation(**c) for c in context.citations()],
            grounded=True,
            confidence=context.confidence,
        )

    @staticmethod
    def _build_messages(
        system_prompt: str, user_content: str, history: list[dict[str, str]] | None
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = [{"role": "system", "content": system_prompt}]
        for turn in history or []:
            messages.append({"role": turn["role"], "content": turn["content"]})  # type: ignore[typeddict-item]
        messages.append({"role": "user", "content": user_content})
        return messages

    async def _generate(self, messages: list[ChatMessage]) -> str:
        try:
            return await self._chat_provider.generate(messages)
        except Exception as exc:
            raise ChatProviderError(f"Chat provider call failed: {exc}") from exc
