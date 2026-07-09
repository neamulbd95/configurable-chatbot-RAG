"""Request/response contract for the chat API (FR-4.1, FR-4.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    # Integration point for a real auth layer (FR-6.9): until one exists
    # upstream, callers pass their roles directly. A chunk with no
    # access_tags is public regardless of what's passed here.
    roles: list[str] | None = None


class Citation(BaseModel):
    source_table: str | None = None
    primary_key: str | None = None
    chunk_id: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    session_id: str | None = None
    citations: list[Citation]
    grounded: bool
    confidence: float = 0.0
