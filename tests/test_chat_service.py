import pytest

from ragchatbot.chat.schemas import ChatRequest
from ragchatbot.chat.service import UNGROUNDED_ANSWER, ChatProviderError, ChatService
from ragchatbot.models import ChunkRecord, RetrievedChunk
from ragchatbot.providers.base import ChatMessage, ChatProvider
from ragchatbot.retrieval.pipeline import ContextPackage


class RecordingChatProvider(ChatProvider):
    def __init__(self, response: str = "Widget costs 19.5."):
        self.response = response
        self.received_messages: list[ChatMessage] | None = None

    async def generate(self, messages: list[ChatMessage]) -> str:
        self.received_messages = messages
        return self.response


def _grounded_context() -> ContextPackage:
    chunk = ChunkRecord(
        chunk_id="products:1::0",
        record_id="products:1",
        chunk_text="Widget costs 19.5.",
        chunk_index=0,
        metadata={"source_table": "products", "primary_key": "1"},
    )
    return ContextPackage(query="price?", results=[RetrievedChunk(chunk=chunk, similarity=0.9)])


@pytest.mark.asyncio
async def test_ungrounded_context_returns_fixed_answer_without_calling_provider():
    provider = RecordingChatProvider()
    service = ChatService(provider)

    response = await service.answer(ChatRequest(message="anything"), ContextPackage(query="q", results=[]))

    assert response.answer == UNGROUNDED_ANSWER
    assert response.grounded is False
    assert response.confidence == 0.0
    assert provider.received_messages is None


@pytest.mark.asyncio
async def test_grounded_context_calls_provider_and_returns_citations():
    provider = RecordingChatProvider()
    service = ChatService(provider)

    response = await service.answer(ChatRequest(message="price?"), _grounded_context())

    assert response.grounded is True
    assert response.answer == "Widget costs 19.5."
    assert response.confidence == pytest.approx(0.9)
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "products:1::0"


@pytest.mark.asyncio
async def test_history_is_threaded_into_messages_before_the_question():
    provider = RecordingChatProvider()
    service = ChatService(provider)
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello, how can I help?"},
    ]

    await service.answer(ChatRequest(message="price?"), _grounded_context(), history=history)

    assert provider.received_messages[0]["role"] == "system"
    assert provider.received_messages[1] == history[0]
    assert provider.received_messages[2] == history[1]
    assert provider.received_messages[-1]["role"] == "user"
    assert "price?" in provider.received_messages[-1]["content"]


class FailingChatProvider(ChatProvider):
    async def generate(self, messages: list[ChatMessage]) -> str:
        raise RuntimeError("Error code: 403 - {'error': {'code': '403', 'message': 'blocked'}}")


@pytest.mark.asyncio
async def test_provider_failure_is_wrapped_with_identifying_prefix():
    service = ChatService(FailingChatProvider())

    with pytest.raises(ChatProviderError, match="Chat provider call failed"):
        await service.answer(ChatRequest(message="price?"), _grounded_context())
