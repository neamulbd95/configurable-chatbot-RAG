"""Resolves ambiguous follow-up questions ("who is the owner of this
asset?") into standalone retrieval queries using recent conversation
history — the classic RAG "condense question" pattern.

Why this exists: retrieval (retrieval/pipeline.py::retrieve) only ever
embeds the literal current message. It has no access to conversation
history, so a pronoun-only follow-up has nothing distinctive to match
against the vector store — either it fails to retrieve anything (the
"ungrounded" false negative), or worse, it retrieves the wrong entity's
chunk via coincidental keyword overlap and answers confidently but
incorrectly. Rewriting the query *before* embedding closes that gap."""

from __future__ import annotations

import logging

from ragchatbot.providers.base import ChatMessage, ChatProvider

logger = logging.getLogger(__name__)

REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's latest message into a standalone question that can "
    "be understood without the conversation history. Resolve pronouns and "
    "vague references (e.g. \"it\", \"this\", \"that asset\") to the "
    "specific entity or subject they refer to, based on the conversation "
    "so far. Preserve the original intent and meaning exactly — do not "
    "answer the question, only rewrite it. If the message is already "
    "standalone and self-contained, return it unchanged. Output ONLY the "
    "rewritten question, with no preamble, quotes, or explanation."
)


async def rewrite_query(
    chat_provider: ChatProvider, message: str, history: list[dict[str, str]]
) -> str:
    """Returns a standalone version of `message`, or `message` unchanged if
    there's no history to resolve against or the rewrite call fails.
    Deliberately fails open: a broken rewrite step degrades to today's
    baseline behavior (raw-message retrieval) rather than blocking the
    request — a real provider outage still surfaces normally on the
    subsequent answer-generation call."""
    if not history:
        return message

    messages: list[ChatMessage] = [{"role": "system", "content": REWRITE_SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})  # type: ignore[typeddict-item]
    messages.append({"role": "user", "content": f"Rewrite this message: {message}"})

    try:
        rewritten = await chat_provider.generate(messages)
    except Exception:
        logger.warning("Query rewrite failed; falling back to the raw message", exc_info=True)
        return message

    rewritten = rewritten.strip().strip('"').strip()
    return rewritten or message
