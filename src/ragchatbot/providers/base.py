"""Provider adapter interfaces (FR-5.1-5.3). Every pipeline stage that talks
to an embedding or chat model goes through one of these, so switching
between Ollama and Azure OpenAI is a config change, never a code change.

ChatProvider takes a full message list (not separate system/user strings) so
multi-turn conversational context (FR-6.11) is a first-class input rather
than something bolted on via string concatenation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, same order as input."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector length, used for FR-2.3 dimension validation."""


class ChatProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[ChatMessage]) -> str:
        """Return a single completion for the given message history."""
