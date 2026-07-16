import pytest

from ragchatbot.chat.query_rewrite import rewrite_query
from ragchatbot.providers.base import ChatMessage, ChatProvider


class RecordingChatProvider(ChatProvider):
    def __init__(self, response: str = "rewritten question"):
        self.response = response
        self.received_messages: list[ChatMessage] | None = None

    async def generate(self, messages: list[ChatMessage]) -> str:
        self.received_messages = messages
        return self.response


class FailingChatProvider(ChatProvider):
    async def generate(self, messages: list[ChatMessage]) -> str:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_no_history_returns_message_unchanged_without_calling_provider():
    provider = RecordingChatProvider()

    result = await rewrite_query(provider, "who is the owner of this asset?", history=[])

    assert result == "who is the owner of this asset?"
    assert provider.received_messages is None


@pytest.mark.asyncio
async def test_with_history_calls_provider_and_returns_its_output():
    provider = RecordingChatProvider(response="Who is the owner of the ESG Factsheet?")
    history = [
        {"role": "user", "content": "give a short summary on ESG Factsheet"},
        {"role": "assistant", "content": "The ESG Factsheet is ..."},
    ]

    result = await rewrite_query(provider, "who is the owner of this asset?", history)

    assert result == "Who is the owner of the ESG Factsheet?"
    assert provider.received_messages[0]["role"] == "system"
    assert provider.received_messages[1] == history[0]
    assert provider.received_messages[2] == history[1]
    assert "who is the owner of this asset?" in provider.received_messages[-1]["content"]


@pytest.mark.asyncio
async def test_strips_surrounding_quotes_and_whitespace_from_rewrite():
    provider = RecordingChatProvider(response='  "Who owns the ESG Factsheet?"  ')
    history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]

    result = await rewrite_query(provider, "who owns it?", history)

    assert result == "Who owns the ESG Factsheet?"


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_original_message():
    history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]

    result = await rewrite_query(FailingChatProvider(), "who owns it?", history)

    assert result == "who owns it?"


@pytest.mark.asyncio
async def test_empty_rewrite_response_falls_back_to_original_message():
    provider = RecordingChatProvider(response="   ")
    history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]

    result = await rewrite_query(provider, "who owns it?", history)

    assert result == "who owns it?"
